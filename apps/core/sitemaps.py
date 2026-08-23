from django.contrib.auth import get_user_model
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.marketplace.models import Application, Category, Collection


class StaticViewSitemap(Sitemap):
    protocol = "https"

    def items(self):
        return [
            {
                "location": reverse("index"),
                "priority": 1.0,
                "changefreq": "daily",
            },
            {
                "location": reverse("help_center", query={"page": "faq"}),
                "priority": 0.6,
                "changefreq": "monthly",
            },
            {
                "location": reverse("help_center", query={"page": "privacy"}),
                "priority": 0.5,
                "changefreq": "monthly",
            },
            {
                "location": reverse("help_center", query={"page": "rules"}),
                "priority": 0.5,
                "changefreq": "monthly",
            },
            {
                "location": reverse("help_center", query={"page": "donate"}),
                "priority": 0.5,
                "changefreq": "monthly",
            },
            {
                "location": reverse("other_projects"),
                "priority": 0.5,
                "changefreq": "monthly",
            },
            {
                "location": reverse("collections"),
                "priority": 0.7,
                "changefreq": "daily",
            },
        ]

    def location(self, item):
        return item["location"]

    def priority(self, item):
        return item["priority"]

    def changefreq(self, item):
        return item["changefreq"]


class CategorySitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8
    protocol = "https"

    def items(self):
        return (
            Category.objects.filter(is_admin_only=False)
            .only("id")
            .order_by("name")
        )

    def location(self, obj):
        return reverse("category", query={"id": obj.id})


class ApplicationSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9
    protocol = "https"

    def items(self):
        return (
            Application.objects.filter(is_private=False, is_under_dmca=False)
            .only("id", "published")
            .order_by("-published")
        )

    def lastmod(self, obj):
        return obj.published

    def location(self, obj):
        return reverse("app", query={"id": obj.id})


class ApplicationDownloadSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = "https"

    def items(self):
        return (
            Application.objects.filter(
                is_private=False,
                is_under_dmca=False,
                distributions__isnull=False,
            )
            .only("id", "published")
            .distinct()
            .order_by("-published")
        )

    def lastmod(self, obj):
        return obj.published

    def location(self, obj):
        return reverse("download", query={"id": obj.id})


class CollectionSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7
    protocol = "https"

    def items(self):
        return (
            Collection.objects.filter(
                is_public=True,
                is_system=False,
                owner__is_active=True,
                items__isnull=False,
            )
            .only("id", "updated_at")
            .distinct()
            .order_by("-updated_at")
        )

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse("collections", query={"page": "view", "id": obj.id})


class AuthorProfileSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5
    protocol = "https"

    def items(self):
        user_model = get_user_model()
        return (
            user_model.objects.filter(
                is_active=True,
                applications__is_private=False,
                applications__deleted__isnull=True,
            )
            .only("id")
            .distinct()
            .order_by("id")
        )

    def location(self, obj):
        return reverse("profile", query={"id": obj.id})


sitemaps = {
    "static": StaticViewSitemap,
    "categories": CategorySitemap,
    "apps": ApplicationSitemap,
    "downloads": ApplicationDownloadSitemap,
    "collections": CollectionSitemap,
    "authors": AuthorProfileSitemap,
}
