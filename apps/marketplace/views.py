import jwt
import logging
import os
import time
import urllib.parse
from constance import config
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import TrigramSimilarity
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_smart_ratelimit import ratelimit
from apps.analytics.services import (
    get_app_analytics,
    get_collection_analytics,
    track_app_download,
    track_app_rate,
    track_app_view,
    track_collection_favorite,
    track_collection_view,
)
from apps.core.utils import get_safe_redirect_url
from apps.user.decorators import developer_required, require_modern_browser
from .decorators import guard_private_app, user_is_owner
from .forms import AppCreateForm, AppEditForm, AppReportForm, CollectionForm, DistributionCreateForm, DistributionEditForm, ProblemReportForm
from django.db import transaction
from django.db.models import Avg, Count
from .models import AppCreateRequests, Application, Category, Collection, CollectionFavorite, CollectionItem, Distribution, AppEditRequests, DistributionCreateRequests, DistributionEditRequests, Review, get_or_create_likes_collection

logger = logging.getLogger(__name__)


def _format_legacy_date(value):
    return value.strftime("%d.%m.%Y %H:%M") if value else ""


# redirect to home (index.php) page from (/) page
def home_redirect(request):
    return redirect("/index.php")


# home page
def marketplace(request):
    categories = Category.objects.all()
    return render(request, "index.html", {"categories": categories})


def category(request):
    id = request.GET.get("id")
    page = request.GET.get("page")
    view_mode = request.GET.get("view", "tiles")

    # get model objects
    obj_category = get_object_or_404(Category, id=id)
    obj_apps = Application.objects.select_related("user").prefetch_related(
        "categories", "badges").annotate(
        cached_avg_rating=Avg('reviews__rating')).filter(
            categories=obj_category, is_private=False).order_by("-published")

    # paginator logic
    paginator = Paginator(obj_apps, 10)
    page_obj = paginator.get_page(page)
    page_range = paginator.get_elided_page_range(
        number=page_obj.number, on_each_side=2, on_ends=1
    )

    context = {
        "page_obj": page_obj,
        "page_range": page_range,
        "active_category": obj_category,
        "name": obj_category.name,
        "view_mode": view_mode,
        "description": obj_category.description,
        "count": obj_apps.count,
    }
    return render(request, "category.html", context)


@guard_private_app
def app(request):
    id = request.GET.get("id")
    obj = get_object_or_404(Application.objects.select_related("user"), id=id)
    first_cat_id = obj.categories.values_list("id", flat=True).first()
    track_app_view(request, app_id=obj.pk, category_id=first_cat_id)
    obj_dist = Distribution.objects.filter(
        app__id=id).order_by("-published").first()
    download_page_url = f"{reverse('download')}?id={obj.id}"

    # get all reviews for this app
    reviews = Review.objects.filter(application=obj).select_related(
        "user").order_by('-created_at')
    review_count = reviews.count()

    # calculate average rating
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
    avg_rating_display = round(avg_rating, 1) if avg_rating else "0,0"
    if avg_rating:
        avg_rating_display = str(avg_rating_display).replace(".", ",")

    # calculate css class for stars
    star_class = ""
    if avg_rating:
        rounded_val = round(avg_rating * 2) / 2
        star_class = "r" + str(rounded_val).replace(".5",
                                                    "_5").replace(".0", "")

    # get current user rating if logged in
    user_review = None
    if request.user.is_authenticated:
        user_review = Review.objects.filter(
            application=obj, user=request.user).first()

    # set up paginator for reviews list
    page = request.GET.get("page", 1)
    paginator = Paginator(reviews, 10)
    page_obj = paginator.get_page(page)
    page_range = paginator.get_elided_page_range(
        number=page_obj.number, on_each_side=2, on_ends=1
    )

    is_liked = False
    likes_count = CollectionItem.objects.filter(
        application=obj, collection__is_system=True
    ).count()
    if request.user.is_authenticated:
        likes_collection = Collection.objects.filter(
            owner=request.user, is_system=True
        ).first()
        if likes_collection is not None:
            is_liked = CollectionItem.objects.filter(
                collection=likes_collection, application=obj
            ).exists()

    context = {
        "app_id": obj.id,
        "is_demo": obj.is_demo,
        "is_dmca": obj.is_under_dmca,
        "is_under_dmca": obj.is_under_dmca,
        "price": obj.price,
        "original_author": obj.original_author,
        "developer_site": obj.developer_site,
        "allow_reviews": obj.allow_reviews,
        "developer_id": obj.user.id,
        "download_page_url": download_page_url,
        "is_translated_to_current_lang": obj.is_translated_to_current_lang,
        "latest_distribution": obj_dist,
        "badges": obj.badges.all(),
        "icon_url": obj.icon_url,
        "title": obj.title,
        "slogan": obj.slogan,
        "description": obj.description,
        "screenshot_urls": obj.screenshot_urls,
        "developer_name": obj.user.username,
        "icon_path": obj.icon_path,
        "requirements": obj.requirements,
        "review_count": review_count,
        "avg_rating_display": avg_rating_display,
        "star_class": star_class,
        "user_review": user_review,
        "page_obj": page_obj,
        "page_range": page_range,
        "collection_saves_count": CollectionItem.objects.filter(application=obj).count(),
        "likes_count": likes_count,
        "is_liked": is_liked,
        "is_app_page": True,
    }
    return render(request, "storepage.html", context)


@guard_private_app
def download_list(request):
    app_id = request.GET.get("id")
    if not app_id:
        return redirect("home")

    app_obj = get_object_or_404(Application, id=app_id)
    sort_field = request.GET.get("sort", "version")
    order = request.GET.get("order", "asc")

    valid_fields = {"version": "version", "published": "published"}
    db_sort_field = valid_fields.get(sort_field, "version")

    sort_prefix = "-" if order == "desc" else ""

    distributions = Distribution.objects.filter(app=app_obj).order_by(
        f"{sort_prefix}{db_sort_field}"
    )

    latest_dist = (
        Distribution.objects.filter(
            app=app_obj).order_by(
            "-published",
            "-id").first())
    latest_id = latest_dist.id if latest_dist else None

    dist_rows = []
    for dist in distributions:
        dist_rows.append(
            {
                "id": dist.id,
                "version": dist.version,
                "changelog": dist.changelog,
                "published": _format_legacy_date(dist.published),
                "is_latest": dist.id == latest_id,
                "link": dist.link,
                "has_download": dist.has_download,
                "is_external": dist.is_external,
            }
        )

    page_num = request.GET.get("page", 1)
    paginator = Paginator(dist_rows, 10)

    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    page_range = page_obj.paginator.get_elided_page_range(
        page_obj.number, on_each_side=1, on_ends=1
    )

    sort_links = {}
    for field in ("version", "published"):
        next_order = "desc" if sort_field == field and order == "asc" else "asc"
        sort_links[field] = (
            f"{reverse('download')}?id={app_obj.id}&sort={field}&order={next_order}"
        )

    dist_rows = []
    for dist in distributions:
        dist_rows.append(
            {
                "id": dist.id,
                "version": dist.version,
                "changelog": dist.changelog,
                "published": _format_legacy_date(dist.published),
                "is_latest": dist.id == latest_id,
                "link": dist.link,
                "has_download": dist.has_download,
            }
        )

    context = {
        "app": app_obj,
        "app_id": app_obj.id,
        "developer_id": app_obj.user.id,
        "is_download_page": True,
        # pass proxy flag to template
        "is_proxy_enabled": getattr(config, 'ENABLE_DISTRIBUTION_PROXY', False),
        "icon_url": app_obj.icon_url,
        "is_demo": app_obj.is_demo,
        "is_under_dmca": app_obj.is_under_dmca,
        "slogan": app_obj.slogan,
        "description": app_obj.description,
        "developer_site": app_obj.developer_site,
        "distributions": page_obj,
        "page_range": page_range,
        "page_obj": page_obj,
        "manage_url": f"{reverse('manage_distributions')}?id={app_obj.id}",
        "current_sort": sort_field,
        "current_order": order,
        "sort_links": sort_links,
        "owner_can_manage": request.user.is_authenticated
        and request.user == app_obj.user,
        "app_link": f"/app.php?id={app_obj.id}",
    }
    return render(request, "download_list.html", context)


@developer_required
@require_modern_browser
@ratelimit(key='ip', rate='10/5m', block=True)
def app_add(request):
    if request.method == "POST":
        form = AppCreateForm(request.POST, request.FILES)
        if form.is_valid():
            app_request = form.save(commit=False)
            app_request.user = request.user
            app_request.save()
            form.save_m2m()
            messages.success(request, _("PAGE_ADDAPP_SUCCESS"))
            return redirect("home")
        else:
            # print only system/global errors (e.g. if CDN token is invalid)
            for error in form.non_field_errors():
                messages.error(request, error)

            other_errors = {
                k: v for k,
                v in form.errors.items() if k not in [
                    '__all__',
                    'captcha']}

            if other_errors:
                messages.error(request, _("ERROR_CHECK_FORM"))
    else:
        form = AppCreateForm()

    return render(
        request,
        "app_add.html",
        {
            "form": form,
            # this will go to JS for file upload handling (cdn_upload_url &
            # token_upload_url)
            "cdn_upload_url": f"{getattr(request, 'geo_domains', {}).get('SPIRE_URL', settings.LUNASPIRE_URL)}/cdn/upload",
            "token_upload_url": "/method/user/getPublicUploadToken/",
        },
    )


@login_required
@require_modern_browser
def settings_apps(request):
    if getattr(request, 'limited', False):
        messages.error(request, _("ERROR_RATE_LIMIT_EXCEEDED"))
        return redirect(request.META.get('HTTP_REFERER', '/'))

    managed_apps = Application.objects.filter(user=request.user)
    app_requests = AppCreateRequests.objects.filter(user=request.user)
    total_app_requests = app_requests.count() + managed_apps.count()
    return render(
        request,
        "settings_apps.html",
        {
            "managed_apps": managed_apps,
            "app_requests": app_requests,
            "total_app_requests": total_app_requests,
        },
    )


@login_required
@require_modern_browser
@user_is_owner(Application)
@ratelimit(key='ip', rate='20/3m', block=True)
def application_edit_info(request, pk):
    if getattr(request, 'limited', False):
        messages.error(request, _("ERROR_RATE_LIMIT_EXCEEDED"))
        return redirect(request.META.get('HTTP_REFERER', '/'))

    obj = get_object_or_404(Application, pk=pk)

    if request.method == "POST":
        form = AppEditForm(
            target_app=obj,
            data=request.POST,
            files=request.FILES)

        if form.is_valid():
            # Apply allow_reviews immediately
            if 'allow_reviews' in form.cleaned_data:
                obj.allow_reviews = form.cleaned_data['allow_reviews']
                obj.save(update_fields=['allow_reviews'])

            edit_request = form.save(commit=False)
            edit_request.user = request.user
            edit_request.save()
            form.save_m2m()
            messages.success(request, _("PAGE_ADMIN_APP_MSG_SAVE_SUCCESS"))
            request.session.save()
            return redirect("edit_app_info", pk=obj.pk)
        else:
            messages.error(request, _("PAGE_ADMIN_APP_MSG_SAVE_ERROR"))
            request.session.save()
    else:
        form = AppEditForm(target_app=obj)

    return render(request,
                  "admin_app.html",
                  {"obj": obj,
                   "form": form,
                   "is_edit_page": True,
                   "app_id": obj.pk,
                   "developer_id": obj.user.pk,
                   "developer_site": obj.developer_site,
                   "cdn_upload_url": f"{getattr(request,
                                                'geo_domains',
                                                {}).get('SPIRE_URL',
                                                        settings.LUNASPIRE_URL)}/cdn/upload",
                   "cdn_token_url": "/method/user/getPublicUploadToken/",
                   },
                  )


@login_required
@require_modern_browser
@user_is_owner(Application)
@ratelimit(key='ip', rate='30/1m', block=True)
def application_stats(request, pk):
    if getattr(request, 'limited', False):
        messages.error(request, _("ERROR_RATE_LIMIT_EXCEEDED"))
        return redirect(request.META.get('HTTP_REFERER', '/'))

    obj = get_object_or_404(Application, pk=pk)
    stats = get_app_analytics(app_id=obj.pk, days=30, chart_days=14)

    return render(
        request,
        "admin_app_stats.html",
        {
            "obj": obj,
            "app": obj,
            "stats": stats,
            "is_stats_page": True,
            "app_id": obj.pk,
            "developer_id": obj.user.pk,
            "developer_site": obj.developer_site,
        },
    )


def search(request):
    query = request.GET.get("q")
    view_mode = request.GET.get("view", "tiles")

    f_author = request.GET.get("author", "")
    is_free = request.GET.get("is_free")
    f_category = request.GET.get("category", "")

    results = Application.objects.select_related("user").prefetch_related(
        "categories", "badges").annotate(
        cached_avg_rating=Avg('reviews__rating')).filter(
            is_private=False)
    categories = Category.objects.all()

    if f_category:
        results = results.filter(categories__id=f_category)

    if query:
        results = results.annotate(
            similarity=TrigramSimilarity("title", query)
            + TrigramSimilarity("description", query)
            + TrigramSimilarity("slogan", query),
        ).filter(similarity__gt=0.1)

    if f_author:
        results = results.filter(user_id=f_author)
    if is_free == "on":
        results = results.filter(price=0)

    if query:
        results = results.order_by("-similarity")
    else:
        results = results.order_by("-id")

    paginator = Paginator(results, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if "page" in query_params:
        del query_params["page"]
    url_params = query_params.urlencode()

    query_params_no_view = query_params.copy()
    if "view" in query_params_no_view:
        del query_params_no_view["view"]
    url_params_no_view = query_params_no_view.urlencode()

    context = {
        "results": page_obj,
        "query": query,
        "view_mode": view_mode,
        "url_params": url_params,
        "url_params_no_view": url_params_no_view,
        "categories": categories,
    }
    return render(request, "search.html", context)


@ratelimit(key='ip', rate='20/1m', block=True)
@login_required
def report_app(request):
    id = request.GET.get("id")
    obj = get_object_or_404(Application, id=id)

    if request.method == "POST":
        form = AppReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.app = obj
            report.save()
            messages.success(request, _("PAGE_REPORTAPP_SUCCESS_MSG"))
            return redirect("home")
    else:
        form = AppReportForm()
    context = {
        "form": form,
        "app_id": id,
        "name": obj.title,
        "developer_site": obj.developer_site,
        "developer_id": obj.user.id,
        "is_report_page": True,
        "slogan": obj.slogan,
        "icon": obj.icon_url,
    }
    return render(request, "report_app.html", context)


@ratelimit(key='ip', rate='20/1m', block=True)
@login_required
def report_problem(request):
    if request.method == "POST":
        form = ProblemReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.save()
            messages.success(request, _("PAGE_REPORTPROBLEM_SUCCESS_MSG"))
            return redirect("home")
    else:
        form = ProblemReportForm()
    context = {
        "form": form,
        "is_report_page": True,
    }
    return render(request, "report_problem.html", context)


@login_required
@require_modern_browser
@ratelimit(key='ip', rate='20/1m', block=True)
def manage_distributions(request):
    app_id = request.GET.get("id")
    app_obj = get_object_or_404(Application, id=app_id)

    if app_obj.user != request.user:
        raise PermissionDenied("ERROR_YOURE_NOT_OWNER_OF_APP")

    distributions = Distribution.objects.filter(
        app=app_obj).order_by("-published")

    pending_requests = DistributionCreateRequests.objects.filter(
        app=app_obj, status="pending").order_by("-created_at")
    pending_edits = DistributionEditRequests.objects.filter(
        target_distribution__app=app_obj,
        status="pending").order_by("-created_at")

    form = DistributionCreateForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        distribution = form.save(commit=False)
        distribution.app = app_obj
        distribution.user = request.user
        distribution.save()
        messages.success(request, _("PAGE_MANAGEDIST_CREATE_SUCCESS"))
        return redirect(reverse("manage_distributions") +
                        "?id=" + str(app_obj.id))
    elif request.method == "POST" and not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)

    dist_rows = []
    for dist in distributions:
        dist_rows.append({"id": dist.id,
                          "version": dist.version,
                          "published": _format_legacy_date(dist.published),
                          "changelog": dist.changelog,
                          "edit_url": reverse("distribution_edit",
                                              kwargs={"dist_pk": dist.pk}),
                          "delete_url": reverse("distribution_delete",
                                                kwargs={"dist_pk": dist.pk}),
                          })

    page_num = request.GET.get("page", 1)
    paginator = Paginator(dist_rows, 10)

    try:
        page_obj = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    page_range = page_obj.paginator.get_elided_page_range(
        page_obj.number, on_each_side=1, on_ends=1
    )

    context = {"app": app_obj,
               "form": form,
               "distributions": page_obj,
               "developer_site": app_obj.developer_site,
               "developer_id": app_obj.user.id,
               "app_id": app_obj.id,
               "page_obj": page_obj,
               "is_edit_page": True,
               "page_range": page_range,
               "pending_requests": pending_requests,
               "pending_edits": pending_edits,
               "get_token_url": "/method/user/getPrivateUploadToken/",
               "cdn_upload_url": f"{getattr(request,
                                            'geo_domains',
                                            {}).get('SPIRE_URL',
                                                    settings.LUNASPIRE_URL)}/cdn/upload",
               "download_list_url": reverse("download") + "?id=" + str(app_obj.id),
               }
    return render(request, "manage_distributions.html", context)


@login_required
@require_modern_browser
@ratelimit(key='ip', rate='20/1m', block=True)
def distribution_edit(request, dist_pk):
    distribution = get_object_or_404(Distribution, pk=dist_pk)
    if distribution.app.user != request.user:
        raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))

    # collect initial data (including changelog translations)
    initial_data = {
        "version": distribution.version,
        "url": distribution.url,
    }

    # automatically populate changelog translations
    for lang_code, lang_name in settings.LANGUAGES:
        lang_field = f"changelog_{lang_code}"
        short_lang_field = f"changelog_{lang_code.split('-')[0].lower()}"

        if hasattr(distribution, lang_field):
            initial_data[lang_field] = getattr(distribution, lang_field)
        elif hasattr(distribution, short_lang_field):
            initial_data[short_lang_field] = getattr(
                distribution, short_lang_field)

    # initialize form with initial data
    form = DistributionEditForm(
        request.POST or None,
        user=request.user,
        target_dist=distribution,
        initial=initial_data
    )

    if request.method == "POST" and form.is_valid():
        edit_req = form.save(commit=False)
        edit_req.app = distribution.app
        edit_req.save()

        messages.success(request, _("MSG_DIST_EDIT_REQ_SENT"))
        return redirect(
            reverse("manage_distributions") + "?id=" + str(distribution.app.id)
        )
    elif request.method == "POST" and not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)

    context = {
        "form": form,
        "app": distribution.app,
        "distribution": distribution,
        "developer_site": distribution.app.developer_site,
        "developer_id": distribution.app.user.id,
        "app_id": distribution.app.id,
        "is_edit_page": True,
        "get_token_url": "/method/user/getPrivateUploadToken/",
        "cdn_upload_url": f"{
            getattr(
                request,
                'geo_domains',
                {}).get(
                'SPIRE_URL',
                settings.LUNASPIRE_URL)}/cdn/upload",
        "download_list_url": reverse("download") +
        "?id=" +
        str(
            distribution.app.id),
    }
    return render(request, "distribution_form.html", context)


@login_required
@ratelimit(key='user', rate='5/1h', block=True)
@ratelimit(key='ip', rate='10/1h', block=True)
def rate_app(request):
    # save user rating here
    if request.method == "POST":
        app_id = request.GET.get("id") or request.POST.get("id")
        rating = request.POST.get("rating")

        # redirect if missing data
        if not app_id or not rating:
            return redirect("home")

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError
        except ValueError:
            return redirect(f"{reverse('app')}?id={app_id}")

        # get the app object
        obj = get_object_or_404(Application, id=app_id)

        if not obj.allow_reviews:
            messages.error(request, _("PAGE_APP_RATING_DISABLED"))
            return redirect(f"{reverse('app')}?id={app_id}")

        # create or update the rating
        review, created = Review.objects.update_or_create(
            application=obj,
            user=request.user,
            defaults={'rating': rating}
        )
        if not created:
            # update existing rating
            review.rating = rating
            review.save()

        track_app_rate(request, app_id=obj.pk, rating=rating)

        # go back to app page
        return redirect(f"{reverse('app')}?id={app_id}")
    return redirect("home")


@login_required
@require_POST
@ratelimit(key='user', rate='5/1h', block=True)
def delete_review(request):
    review_id = request.POST.get("id")
    if not review_id:
        return redirect("home")

    review = get_object_or_404(Review, id=review_id)
    if review.user != request.user and not request.user.has_perm(
            "marketplace.delete_review"):
        messages.error(request, _("PAGE_APP_RATING_DELETE_DENIED"))
        return redirect(f"{reverse('app')}?id={review.application.id}")

    app_id = review.application.id
    review.delete()
    messages.success(request, _("PAGE_APP_RATING_DELETE_SUCCESS"))

    next_url = get_safe_redirect_url(
        request,
        request.POST.get("next"),
        fallback=f"{reverse('app')}?id={app_id}",
    )
    return redirect(next_url)


@login_required
@require_modern_browser
def distribution_delete(request, dist_pk):
    distribution = get_object_or_404(Distribution, pk=dist_pk)
    if distribution.app.user != request.user:
        raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))

    if request.method == "POST":
        distribution.delete()
        messages.success(request, _("Дистрибуция удалена"))
    else:
        messages.warning(request, _("Нужно подтвердить удаление через POST"))

    return redirect(reverse("manage_distributions") +
                    "?id=" + str(distribution.app.id))


def distribution_list_page(request, app_id):
    app_obj = get_object_or_404(Application, id=app_id)
    distributions = app_obj.distributions.filter(
        deleted__isnull=True).order_by("-published")
    return render(
        request,
        "marketplace/download_list.html",
        {"app": app_obj, "distributions": distributions},
    )


def get_file_action(request, dist_pk):
    dist = get_object_or_404(Distribution.objects.select_related("app"), pk=dist_pk)
    app = dist.app

    # block private app downloads for non-owners
    if app.is_private:
        if not request.user.is_authenticated or app.user_id != request.user.id:
            raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))

    # track download analytics
    track_app_download(request, app_id=app.pk, distribution_id=dist.pk)

    if dist.cdn_file_id:
        payload = {
            "type": "cdn-download",
            "file_id": int(dist.cdn_file_id),
            "exp": int(time.time()) + 600,
            "app_id": int(app.id),
        }
        if request.user.is_authenticated:
            payload["user_id"] = int(request.user.id)
        try:
            download_token = jwt.encode(
                payload, settings.LUNASPIRE_SECRET_KEY, algorithm="HS256"
            )
        except Exception:
            logger.exception("failed to encode cdn download jwt")
            raise Http404("File not found")

        user_agent = request.META.get("HTTP_USER_AGENT", "")
        is_retro = any(
            sig in user_agent for sig in [
                "MSIE 5",
                "MSIE 6",
                "MSIE 7",
                "MSIE 8"])

        protocol = "http" if is_retro else "https"

        spire_url = getattr(
            request, 'geo_domains', {}).get(
            'SPIRE_URL', settings.LUNASPIRE_URL)
        domain = spire_url.replace('https://', '').replace('http://', '')
        cdn_url = f"{protocol}://{domain}/cdn/download?token={download_token}"
        return redirect(cdn_url)

    if dist.url:
        is_proxy_requested = request.GET.get('proxy') == '1'
        # proxy through nginx if enabled
        if is_proxy_requested and getattr(
                config, 'ENABLE_DISTRIBUTION_PROXY', False):
            parsed_url = urllib.parse.urlparse(dist.url)
            path = parsed_url.path
            _, ext = os.path.splitext(path)
            if not ext and parsed_url.fragment:
                _, ext = os.path.splitext(parsed_url.fragment)

            # sanitize names
            app_name = "".join([c for c in dist.app.title if c.isalnum() or c in (
                " ", "-", "_")]).strip().replace(" ", "_")
            version = "".join([c for c in dist.version if c.isalnum() or c in (
                " ", "-", ".", "_")]).strip().replace(" ", "_")

            # build filename
            if ext:
                if version:
                    filename = f"{app_name}_{version}{ext}"
                else:
                    filename = f"{app_name}{ext}"
            else:
                # fallback to basename
                basename = os.path.basename(path)
                filename = basename if basename else f"{app_name}.download"

            # set proxy headers
            response = HttpResponse()
            response['X-Accel-Redirect'] = f'/_px/{dist.url}'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        # fallback to direct download
        return redirect(dist.url)

    raise Http404("File not found")


def _user_can_view_collection(user, collection: Collection) -> bool:
    if collection.is_public:
        return True
    return bool(user.is_authenticated and user.id == collection.owner_id)


def _touch_collection(collection: Collection) -> None:
    try:
        collection.save(update_fields=["updated_at"])
    except Exception:
        logger.exception("failed to touch collection id=%s", collection.pk)


# dispatcher for collections.php (list/view/edit/delete/add/favorite)
def collections(request):
    page = request.GET.get("page")
    act = request.GET.get("act")

    if act == "add":
        return _collections_add(request)
    if act == "favorite":
        return _collections_favorite(request)
    if act == "remove_item":
        return _collections_remove_item(request)
    if act == "toggle_like":
        return _collections_toggle_like(request)

    if page == "view":
        return _collections_view(request)
    if page == "stats":
        return _collections_stats(request)
    if page in ("edit", "create"):
        return _collections_edit(request)
    if page == "delete":
        return _collections_delete(request)
    if page == "liked":
        return _collections_list(request, liked=True)
    if page == "my_likes":
        return _collections_my_likes(request)

    return _collections_list(request, liked=False)


@login_required
def _collections_list(request, liked: bool = False):
    if liked:
        favorites = (
            CollectionFavorite.objects.filter(user=request.user)
            .select_related("collection", "collection__owner")
            .order_by("-created_at")
        )
        collections_qs = [fav.collection for fav in favorites if fav.collection]
        title_key = "PAGE_COLLECTION_TAB_LIKED"
    else:
        # do not auto-create system likes here; hide empty system collection
        collections_qs = list(
            Collection.objects.filter(owner=request.user)
            .annotate(items_count=Count("items"))
            .order_by("-is_system", "-updated_at")
        )
        collections_qs = [
            col
            for col in collections_qs
            if not (col.is_system and col.items_count == 0)
        ]
        title_key = "PAGE_COLLECTION_TAB_MINE"

    items = []
    for col in collections_qs:
        apps_count = getattr(col, "items_count", None)
        if apps_count is None:
            apps_count = col.items.count()
        items.append(
            {
                "collection": col,
                "mosaic": col.mosaic_icons(4),
                "saves_count": col.favorites.count(),
                "apps_count": apps_count,
                "is_owner": col.owner_id == request.user.id,
            }
        )

    context = {
        "tab": "liked" if liked else "mine",
        "title_key": title_key,
        "collection_items": items,
        "collections_count": len(items),
    }
    return render(request, "collections.html", context)


@login_required
def _collections_my_likes(request):
    likes = get_or_create_likes_collection(request.user)
    return redirect(f"{reverse('collections')}?page=view&id={likes.id}")


def _collections_view(request):
    collection_id = request.GET.get("id")
    collection = get_object_or_404(
        Collection.objects.select_related("owner"), id=collection_id
    )
    if not _user_can_view_collection(request.user, collection):
        messages.error(request, _("PAGE_COLLECTION_ERROR_PRIVATE"))
        if request.user.is_authenticated:
            return redirect("collections")
        return redirect("login")

    apps = [
        item.application
        for item in collection.items.select_related("application", "application__user").order_by("-added_at")
    ]
    is_owner = request.user.is_authenticated and request.user.id == collection.owner_id
    is_favorited = False
    if request.user.is_authenticated and not is_owner:
        is_favorited = CollectionFavorite.objects.filter(
            user=request.user, collection=collection
        ).exists()

    track_collection_view(
        request,
        collection_id=collection.pk,
        owner_id=collection.owner_id,
    )

    context = {
        "collection": collection,
        "mosaic": collection.mosaic_icons(4),
        "apps": apps,
        "apps_count": len(apps),
        "saves_count": collection.favorites.count(),
        "is_owner": is_owner,
        "is_favorited": is_favorited,
        "tab": "view",
    }
    return render(request, "collections_view.html", context)


def _collections_stats(request):
    collection_id = request.GET.get("id")
    collection = get_object_or_404(
        Collection.objects.select_related("owner"), id=collection_id
    )
    if not _user_can_view_collection(request.user, collection):
        messages.error(request, _("PAGE_COLLECTION_ERROR_PRIVATE"))
        if request.user.is_authenticated:
            return redirect("collections")
        return redirect("login")

    is_owner = request.user.is_authenticated and (
        request.user.id == collection.owner_id or request.user.is_staff
    )
    if not is_owner:
        messages.error(request, _("ERROR_YOURE_NOT_OWNER_OF_APP"))
        return redirect(f"/collections.php?page=view&id={collection.id}")

    stats = get_collection_analytics(collection_id=collection.id, days=30, chart_days=14)

    context = {
        "collection": collection,
        "mosaic": collection.mosaic_icons(4),
        "stats": stats,
        "is_owner": is_owner,
        "tab": "stats",
    }
    return render(request, "collections_stats.html", context)


@login_required
def _collections_edit(request):
    collection_id = request.GET.get("id")
    collection = None
    if collection_id:
        collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
        if collection.is_system:
            messages.error(request, _("PAGE_COLLECTION_ERROR_EDIT_SYSTEM"))
            return redirect(f"{reverse('collections')}?page=view&id={collection.id}")

    if request.method == "POST":
        form = CollectionForm(request.POST, instance=collection)
        if form.is_valid():
            try:
                obj = form.save(commit=False)
                obj.owner = request.user
                if collection is None:
                    obj.is_system = False
                obj.save()
                messages.success(request, _("PAGE_COLLECTION_MSG_SAVED"))
                return redirect(f"{reverse('collections')}?page=view&id={obj.id}")
            except Exception:
                logger.exception("failed to save collection")
                messages.error(request, _("PAGE_COLLECTION_ERROR_SAVE"))
    else:
        form = CollectionForm(instance=collection)

    context = {
        "form": form,
        "collection": collection,
        "is_create": collection is None,
        "trans_fields": form.get_trans_fields(),
    }
    return render(request, "collections_form.html", context)


@login_required
def _collections_delete(request):
    collection_id = request.GET.get("id")
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    if collection.is_system:
        messages.error(request, _("PAGE_COLLECTION_ERROR_DELETE_SYSTEM"))
        return redirect("collections")

    if request.method == "POST":
        try:
            collection.delete()
            messages.success(request, _("PAGE_COLLECTION_MSG_DELETED"))
        except Exception:
            logger.exception("failed to delete collection id=%s", collection_id)
            messages.error(request, _("PAGE_COLLECTION_ERROR_DELETE"))
        return redirect("collections")

    context = {"collection": collection}
    return render(request, "collections_delete.html", context)


@login_required
def _collections_add(request):
    # sync app membership in custom collections (likes toggled separately)
    app_id = request.GET.get("appid") or request.POST.get("appid")
    application = get_object_or_404(Application, id=app_id)
    user_collections = list(
        Collection.objects.filter(owner=request.user, is_system=False).order_by("title")
    )
    selected_ids = set(
        CollectionItem.objects.filter(
            application=application,
            collection__owner=request.user,
            collection__is_system=False,
        ).values_list("collection_id", flat=True)
    )

    if request.method == "POST":
        posted_ids = set()
        for raw_id in request.POST.getlist("collection_ids"):
            try:
                posted_ids.add(int(raw_id))
            except (TypeError, ValueError):
                continue
        allowed_ids = {col.id for col in user_collections}
        posted_ids &= allowed_ids
        try:
            to_add = posted_ids - selected_ids
            to_remove = selected_ids - posted_ids
            with transaction.atomic():
                for collection in user_collections:
                    if collection.id in to_add:
                        CollectionItem.objects.get_or_create(
                            collection=collection, application=application
                        )
                        _touch_collection(collection)
                    elif collection.id in to_remove:
                        CollectionItem.objects.filter(
                            collection=collection, application=application
                        ).delete()
                        _touch_collection(collection)
            messages.success(request, _("PAGE_COLLECTION_MSG_SAVED"))
        except Exception:
            logger.exception(
                "failed to sync collections for app %s user %s",
                app_id,
                getattr(request.user, "pk", None),
            )
            messages.error(request, _("PAGE_COLLECTION_ERROR_ADD_APP"))
        return redirect(f"{reverse('app')}?id={application.id}")

    context = {
        "application": application,
        "user_collections": user_collections,
        "selected_ids": selected_ids,
    }
    return render(request, "collections_add.html", context)


@login_required
def _collections_favorite(request):
    collection_id = request.GET.get("id") or request.POST.get("id")
    collection = get_object_or_404(Collection, id=collection_id)
    if collection.owner_id == request.user.id:
        messages.error(request, _("PAGE_COLLECTION_ERROR_FAVORITE_OWN"))
        return redirect(f"{reverse('collections')}?page=view&id={collection.id}")
    if not collection.is_public:
        messages.error(request, _("PAGE_COLLECTION_ERROR_PRIVATE"))
        return redirect("collections")

    try:
        fav, created = CollectionFavorite.objects.get_or_create(
            user=request.user, collection=collection
        )
        if not created:
            fav.delete()
            track_collection_favorite(request, collection_id=collection.pk, is_favorite=False)
            messages.success(request, _("PAGE_COLLECTION_MSG_UNFAVORITED"))
        else:
            track_collection_favorite(request, collection_id=collection.pk, is_favorite=True)
            messages.success(request, _("PAGE_COLLECTION_MSG_FAVORITED"))
    except Exception:
        logger.exception("failed to toggle favorite for collection %s", collection_id)
        messages.error(request, _("PAGE_COLLECTION_ERROR_FAVORITE"))
    return redirect(f"{reverse('collections')}?page=view&id={collection.id}")


@login_required
@require_POST
def _collections_remove_item(request):
    collection_id = request.POST.get("collection_id")
    app_id = request.POST.get("appid")
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    try:
        deleted_count, _deleted_by_model = CollectionItem.objects.filter(
            collection=collection, application_id=app_id
        ).delete()
        if deleted_count:
            _touch_collection(collection)
            messages.success(request, _("PAGE_COLLECTION_MSG_APP_REMOVED"))
        else:
            messages.info(request, _("PAGE_COLLECTION_MSG_APP_NOT_IN"))
    except Exception:
        logger.exception(
            "failed to remove app %s from collection %s", app_id, collection_id
        )
        messages.error(request, _("PAGE_COLLECTION_ERROR_REMOVE_APP"))
    return redirect(f"{reverse('collections')}?page=view&id={collection.id}")


@login_required
@require_POST
def _collections_toggle_like(request):
    # toggle app in the system likes collection only (csrf-protected post)
    app_id = request.POST.get("appid") or request.GET.get("appid")
    application = get_object_or_404(Application, id=app_id)
    try:
        likes = get_or_create_likes_collection(request.user)
        existing = CollectionItem.objects.filter(
            collection=likes, application=application
        ).first()
        if existing is not None:
            existing.delete()
            _touch_collection(likes)
            messages.success(request, _("PAGE_COLLECTION_MSG_APP_REMOVED"))
        else:
            CollectionItem.objects.get_or_create(
                collection=likes, application=application
            )
            _touch_collection(likes)
            messages.success(request, _("PAGE_COLLECTION_MSG_APP_ADDED"))
    except Exception:
        logger.exception(
            "failed to toggle like for app %s user %s",
            app_id,
            getattr(request.user, "pk", None),
        )
        messages.error(request, _("PAGE_COLLECTION_ERROR_ADD_APP"))
    return redirect(f"{reverse('app')}?id={application.id}")
