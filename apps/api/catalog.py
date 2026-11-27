from django.db.models import Q

from apps.core.search import SearchService
from apps.marketplace.models import Application, Distribution
from apps.marketplace.serializers import annotate_app_last_version
from apps.marketplace.services.access import accessible_app_ids


def application_queryset(user, *, include_private=False):
    queryset = Application.objects.filter(is_under_dmca=False)
    if include_private:
        return queryset.filter(Q(is_private=False) | Q(pk__in=accessible_app_ids(user)))
    return queryset.filter(is_private=False)


def distribution_queryset(user):
    queryset = Distribution.objects.select_related("platform").prefetch_related("platforms").filter(
        app__deleted__isnull=True, app__is_under_dmca=False,
    )
    if user.is_authenticated:
        return queryset.filter(Q(app__is_private=False) | Q(app_id__in=accessible_app_ids(user)))
    return queryset.filter(app__is_private=False)


def paginated_search(view, request, queryset, search):
    paginator = view.paginator
    paginator.limit = paginator.get_limit(request)
    paginator.offset = paginator.get_offset(request)
    ids, paginator.count = search(limit=paginator.limit, offset=paginator.offset)
    results = SearchService.order_queryset_by_ids(queryset, ids)
    paginator.request = request
    return paginator.get_paginated_response(view.get_serializer(results, many=True).data)


def with_application_cards(queryset):
    return annotate_app_last_version(queryset.select_related("user").prefetch_related("platforms", "categories"))
