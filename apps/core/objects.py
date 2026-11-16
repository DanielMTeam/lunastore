from django.http import Http404
from django.shortcuts import get_object_or_404


def get_integer_object_or_404(queryset, **lookup):
    try:
        return get_object_or_404(queryset, **lookup)
    except (TypeError, ValueError, OverflowError) as exc:
        raise Http404 from exc
