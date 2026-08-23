# views for collections management, discovery and statistics
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.analytics.services import (
    get_collection_analytics,
    track_app_collection_add,
    track_app_collection_remove,
    track_collection_favorite,
    track_collection_item_change,
    track_collection_view,
)
from .forms import CollectionForm
from .models import (
    Application,
    Collection,
    CollectionFavorite,
    CollectionItem,
    get_or_create_likes_collection,
)

logger = logging.getLogger(__name__)


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


@login_required
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
                        track_collection_item_change(
                            request,
                            collection_id=collection.pk,
                            app_id=application.pk,
                            is_added=True,
                            owner_id=collection.owner_id,
                        )
                        track_app_collection_add(
                            request,
                            app_id=application.pk,
                            collection_id=collection.pk,
                        )
                    elif collection.id in to_remove:
                        CollectionItem.objects.filter(
                            collection=collection, application=application
                        ).delete()
                        _touch_collection(collection)
                        track_collection_item_change(
                            request,
                            collection_id=collection.pk,
                            app_id=application.pk,
                            is_added=False,
                            owner_id=collection.owner_id,
                        )
                        track_app_collection_remove(
                            request,
                            app_id=application.pk,
                            collection_id=collection.pk,
                        )
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
            track_collection_item_change(
                request,
                collection_id=collection.pk,
                app_id=int(app_id),
                is_added=False,
                owner_id=collection.owner_id,
            )
            track_app_collection_remove(
                request,
                app_id=int(app_id),
                collection_id=collection.pk,
            )
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
            track_collection_item_change(
                request,
                collection_id=likes.pk,
                app_id=application.pk,
                is_added=False,
                owner_id=likes.owner_id,
            )
            track_app_collection_remove(
                request,
                app_id=application.pk,
                collection_id=likes.pk,
            )
            messages.success(request, _("PAGE_COLLECTION_MSG_APP_REMOVED"))
        else:
            CollectionItem.objects.get_or_create(
                collection=likes, application=application
            )
            _touch_collection(likes)
            track_collection_item_change(
                request,
                collection_id=likes.pk,
                app_id=application.pk,
                is_added=True,
                owner_id=likes.owner_id,
            )
            track_app_collection_add(
                request,
                app_id=application.pk,
                collection_id=likes.pk,
            )
            messages.success(request, _("PAGE_COLLECTION_MSG_APP_ADDED"))
    except Exception:
        logger.exception(
            "failed to toggle like for app %s user %s",
            app_id,
            getattr(request.user, "pk", None),
        )
        messages.error(request, _("PAGE_COLLECTION_ERROR_ADD_APP"))
    return redirect(f"{reverse('app')}?id={application.id}")
