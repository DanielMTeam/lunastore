from apps.marketplace.services.visibility import public_app_filter
from django.db.models import OuterRef, Subquery
from django.templatetags.static import static
from drf_spectacular.utils import extend_schema_field

from rest_framework import serializers

from .models import Application, Category, Collection, Distribution
from apps.api.media import absolute_media_url
from apps.user.serializers import UserSerializer


def annotate_app_last_version(queryset):
    # annotate each app with the version of its most recent published distribution
    last_dist = Distribution.objects.filter(app_id=OuterRef("pk")).order_by(
        "-published"
    )
    return queryset.annotate(
        last_dist_version=Subquery(last_dist.values("version")[:1])
    )


class ApplicationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    version = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id",
            "title",
            "description",
            "original_author",
            "slogan",
            "price",
            "requirements",
            "screenshot_urls",
            "developer_site",
            "is_demo",
            "is_under_dmca",
            "icon_url",
            "user",
            "version",
        ]

    def get_version(self, obj) -> str | None:
        if hasattr(obj, "last_dist_version"):
            return obj.last_dist_version
        last_dist = obj.distributions.order_by("-published").first()
        return last_dist.version if last_dist else None


class CategorySerializer(serializers.ModelSerializer):
    icon_url = serializers.SerializerMethodField()

    ICONS = frozenset((
        "myhome", "top", "updates", "entertainment", "util", "media", "office",
        "internet", "other", "themes", "setup", "alert", "newbie", "notify",
        "settings", "web", "mypc", "paint", "emuvm",
    ))

    class Meta:
        model = Category
        fields = ["id", "name", "description", "icon", "icon_url", "banner_url"]

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_icon_url(self, obj):
        if obj.icon in self.ICONS:
            return absolute_media_url(static(f"img/category-icons/{obj.icon}.png"))
        return None


class DistributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distribution
        fields = [
            "id",
            "app",
            "version",
            "link",
            "url",
            "has_download",
            "published",
            "lunabox_manifest",
        ]


class CollectionSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    items_count = serializers.SerializerMethodField()
    mosaic_icons = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = [
            "id",
            "title",
            "description",
            "owner",
            "is_system",
            "is_public",
            "created_at",
            "updated_at",
            "items_count",
            "mosaic_icons",
        ]

    def get_items_count(self, obj: Collection) -> int:
        if hasattr(obj, "items_count"):
            return obj.items_count
        return obj.items.filter(public_app_filter("application__")).count()

    def get_mosaic_icons(self, obj: Collection) -> list:
        return obj.mosaic_icons(4)
