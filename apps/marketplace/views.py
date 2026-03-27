import jwt
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import TrigramSimilarity
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.user.decorators import developer_required

from .decorators import user_is_owner
from .forms import AppCreateForm, AppEditForm, AppReportForm, DistributionForm
from .models import AppCreateRequests, Application, Category, Distribution


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
    obj_apps = Application.objects.filter(category__name=obj_category.name).order_by(
        "-published"
    )

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


def app(request):
    id = request.GET.get("id")
    obj = get_object_or_404(Application, id=id)
    obj_dist = Distribution.objects.filter(app__id=id).order_by("-published").first()
    download_page_url = f"{reverse('download')}?id={obj.id}"

    context = {
        "app_id": obj.id,
        "is_demo": obj.is_demo,
        "is_dmca": obj.is_under_dmca,
        "is_under_dmca": obj.is_under_dmca,
        "price": obj.price,
        "original_author": obj.original_author,
        "developer_site": obj.developer_site,
        "developer_id": obj.user.id,
        "download_page_url": download_page_url,
        "latest_distribution": obj_dist,
        "icon_url": obj.icon_url,
        "title": obj.title,
        "slogan": obj.slogan,
        "description": obj.description,
        "screenshot_urls": obj.screenshot_urls,
        "developer_name": obj.user.username,
        "icon_path": obj.icon_path,
        "requirements": obj.requirements,
    }
    return render(request, "storepage.html", context)


def download_list(request):
    app_id = request.GET.get("id")
    if not app_id:
        return redirect("home")

    app_obj = get_object_or_404(Application, id=app_id)
    distributions = list(Distribution.objects.filter(app=app_obj))
    sort_field = request.GET.get("sort", "version")
    order = request.GET.get("order", "asc")

    def sort_key(dist):
        if sort_field == "published":
            return dist.published or dist.pk
        return dist.version or ""

    is_desc = order == "desc"
    distributions.sort(key=sort_key, reverse=is_desc)

    latest_dist = (
        Distribution.objects.filter(app=app_obj).order_by("-published", "-id").first()
    )
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
        "icon_url": app_obj.icon_url,
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
def app_add(request):
    if request.method == "POST":
        form = AppCreateForm(request.POST, request.FILES)
        if form.is_valid():
            app_request = form.save(commit=False)
            app_request.user = request.user
            app_request.save()
            messages.success(request, _("PAGE_ADDAPP_SUCCESS"))
            return redirect("home")
    else:
        form = AppCreateForm()

    return render(
        request,
        "app_add.html",
        {
            "form": form,
            "cdn_upload_url": f"{settings.LUNASPIRE_URL}/cdn/upload",
            "token_upload_url": f"{settings.API_URL}/method/user/getPubUploadToken",
        },
    )


@login_required
def settings_apps(request):
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
@user_is_owner(Application)
def application_edit_info(request, pk):
    obj = get_object_or_404(Application, pk=pk)

    if request.method == "POST":
        form = AppEditForm(target_app=obj, data=request.POST, files=request.FILES)

        if form.is_valid():
            edit_request = form.save(commit=False)
            edit_request.user = request.user
            edit_request.save()
            messages.success(request, _("PAGE_ADMIN_APP_MSG_SAVE_SUCCESS"))
            request.session.save()
            return redirect("edit_app_info", pk=obj.pk)
        else:
            messages.error(request, _("PAGE_ADMIN_APP_MSG_SAVE_ERROR"))
            request.session.save()
    else:
        form = AppEditForm(target_app=obj)

    return render(
        request,
        "admin_app.html",
        {
            "obj": obj,
            "form": form,
            "cdn_upload_url": f"{settings.LUNASPIRE_URL}/cdn/upload",
            "cdn_token_url": f"{settings.API_URL}/method/user/getPubUploadToken",
        },
    )


def search(request):
    query = request.GET.get("q")
    view_mode = request.GET.get("view", "tiles")

    f_author = request.GET.get("author", "")
    is_free = request.GET.get("is_free")
    f_category = request.GET.get("category", "")

    results = Application.objects.all()
    categories = Category.objects.all()

    if f_category:
        results = results.filter(category_id=f_category)

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

    context = {
        "results": page_obj,
        "query": query,
        "view_mode": view_mode,
        "url_params": url_params,
        "categories": categories,
    }
    return render(request, "search.html", context)


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
        "name": obj.title,
        "slogan": obj.slogan,
        "icon": obj.icon_url,
    }
    return render(request, "report_app.html", context)


@login_required
def manage_distributions(request):
    app_id = request.GET.get("id")
    app_obj = get_object_or_404(Application, id=app_id)

    if app_obj.user != request.user:
        raise PermissionDenied("ERROR_YOURE_NOT_OWNER_OF_APP")

    distributions = Distribution.objects.filter(app=app_obj).order_by("-published")
    form = DistributionForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        distribution = form.save(commit=False)
        distribution.app = app_obj
        distribution.save()
        messages.success(request, _("PAGE_MANAGEDIST_CREATE_SUCCESS"))
        return redirect(reverse("manage_distributions") + "?id=" + str(app_obj.id))
    elif request.method == "POST" and not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)

    dist_rows = []
    for dist in distributions:
        dist_rows.append(
            {
                "id": dist.id,
                "version": dist.version,
                "published": _format_legacy_date(dist.published),
                "changelog": dist.changelog,
                "edit_url": reverse("distribution_edit", kwargs={"dist_pk": dist.pk}),
                "delete_url": reverse(
                    "distribution_delete", kwargs={"dist_pk": dist.pk}
                ),
            }
        )

    page_num = request.GET.get("page", 1)
    paginator = Paginator(dist_rows, 10)

    try:
        page_obj = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    page_range = page_obj.paginator.get_elided_page_range(
        page_obj.number, on_each_side=1, on_ends=1
    )

    context = {
        "app": app_obj,
        "form": form,
        "distributions": page_obj,
        "page_obj": page_obj,
        "page_range": page_range,
        "get_token_url": f"{settings.API_URL}/method/user/getPrivUploadToken",
        "cdn_upload_url": f"{settings.LUNASPIRE_URL}/cdn/upload",
        "download_list_url": reverse("download") + "?id=" + str(app_obj.id),
    }
    return render(request, "manage_distributions.html", context)


@login_required
def distribution_edit(request, dist_pk):
    distribution = get_object_or_404(Distribution, pk=dist_pk)
    if distribution.app.user != request.user:
        raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))

    form = DistributionForm(
        request.POST or None, request.FILES or None, instance=distribution
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("PAGE_DIST_FORM_SAVED"))
        return redirect(
            reverse("manage_distributions") + "?id=" + str(distribution.app.id)
        )

    context = {
        "form": form,
        "app": distribution.app,
        "distribution": distribution,
        "get_token_url": f"{settings.API_URL}/method/user/getPrivUploadToken",
        "cdn_upload_url": f"{settings.LUNASPIRE_URL}/cdn/upload",
        "download_list_url": reverse("download") + "?id=" + str(distribution.app.id),
    }
    return render(request, "distribution_form.html", context)


@login_required
def distribution_delete(request, dist_pk):
    distribution = get_object_or_404(Distribution, pk=dist_pk)
    if distribution.app.user != request.user:
        raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))

    if request.method == "POST":
        distribution.delete()
        messages.success(request, _("Дистрибуция удалена"))
    else:
        messages.warning(request, _("Нужно подтвердить удаление через POST"))

    return redirect(reverse("manage_distributions") + "?id=" + str(distribution.app.id))


def distribution_list_page(request, app_id):
    app_obj = get_object_or_404(Application, id=app_id)
    distributions = app_obj.distributions.filter(deleted__isnull=True).order_by(
        "-published"
    )
    return render(
        request,
        "marketplace/download_list.html",
        {"app": app_obj, "distributions": distributions},
    )


def get_file_action(request, dist_pk):
    dist = get_object_or_404(Distribution, pk=dist_pk)

    if dist.cdn_file_id:
        payload = {"type": "cdn-download", "file_id": int(dist.cdn_file_id)}
        download_token = jwt.encode(
            payload, settings.LUNASPIRE_SECRET_KEY, algorithm="HS256"
        )

        user_agent = request.META.get("HTTP_USER_AGENT", "")
        is_retro = any(
            sig in user_agent for sig in ["MSIE 5", "MSIE 6", "MSIE 7", "MSIE 8"]
        )

        protocol = "http" if is_retro else "https"

        domain = settings.LUNASPIRE_URL_WITHOUT_PROTO
        cdn_url = f"{protocol}://{domain}/cdn/download?token={download_token}"
        print(cdn_url)
        return redirect(cdn_url)

    if dist.url:
        return redirect(dist.url)

    raise Http404("File not found")
