from datetime import UTC

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers
from rest_framework.reverse import reverse

from apps.api.media import absolute_media_url, public_api_url
from apps.marketplace.models import Application, Platform
from apps.marketplace.serializers import (
    ApplicationSerializer as BaseApplicationSerializer,
    CategorySerializer as BaseCategorySerializer,
    CollectionSerializer as BaseCollectionSerializer,
    DistributionSerializer as BaseDistributionSerializer,
)
from apps.user.serializers import UserSerializer as BaseUserSerializer


@extend_schema_serializer(component_name="V3Platform")
class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = ("id", "code", "name")


@extend_schema_serializer(component_name="V3User")
class UserSerializer(BaseUserSerializer):
    avatar_url = serializers.SerializerMethodField()

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_avatar_url(self, obj):
        return absolute_media_url(obj.avatar_url)


@extend_schema_serializer(component_name="V3Category")
class CategorySerializer(BaseCategorySerializer):
    banner_url = serializers.SerializerMethodField()

    class Meta(BaseCategorySerializer.Meta):
        fields = ("id", "name", "description", "icon_url", "banner_url")

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_banner_url(self, obj):
        return absolute_media_url(obj.banner_url)


@extend_schema_serializer(component_name="V3Application")
class ApplicationSerializer(BaseApplicationSerializer):
    user = UserSerializer(read_only=True)
    platforms = PlatformSerializer(many=True, read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    icon_url = serializers.SerializerMethodField()
    screenshot_urls = serializers.SerializerMethodField()

    class Meta(BaseApplicationSerializer.Meta):
        model = Application
        fields = (*BaseApplicationSerializer.Meta.fields, "platforms", "categories")

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_icon_url(self, obj):
        return absolute_media_url(obj.icon_url)

    @extend_schema_field(serializers.ListField(child=serializers.URLField()))
    def get_screenshot_urls(self, obj):
        return [absolute_media_url(url) for url in obj.screenshot_urls if url]


@extend_schema_serializer(component_name="V3Distribution")
class DistributionSerializer(BaseDistributionSerializer):
    platform = PlatformSerializer(read_only=True)
    platforms = PlatformSerializer(source="display_platforms", many=True, read_only=True)
    download_url = serializers.SerializerMethodField()
    published = serializers.DateTimeField(read_only=True, default_timezone=UTC)

    class Meta(BaseDistributionSerializer.Meta):
        fields = (
            "id", "app", "version", "download_url", "has_download", "published",
            "lunabox_manifest", "platform", "platforms",
        )

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_download_url(self, obj):
        if obj.has_download:
            return public_api_url(reverse(
                "v3-distribution-download", kwargs={"pk": obj.pk}, request=self.context["request"],
            ))
        return None


@extend_schema_serializer(component_name="V3Collection")
class CollectionSerializer(BaseCollectionSerializer):
    owner = UserSerializer(read_only=True)
    created_at = serializers.DateTimeField(read_only=True, default_timezone=UTC)
    updated_at = serializers.DateTimeField(read_only=True, default_timezone=UTC)

    @extend_schema_field(serializers.ListField(child=serializers.URLField()))
    def get_mosaic_icons(self, obj):
        return [absolute_media_url(item.application.icon_url) for item in obj.visible_icon_items]


class PageParams(serializers.Serializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100)
    offset = serializers.IntegerField(required=False, min_value=0)


class UserParams(PageParams):
    q = serializers.CharField(required=False, max_length=200)


class ApplicationParams(UserParams):
    category = serializers.IntegerField(required=False, min_value=1, max_value=9223372036854775807)
    author = serializers.IntegerField(required=False, min_value=1, max_value=9223372036854775807)
    is_free = serializers.BooleanField(default=False)
    platform = serializers.SlugField(required=False, max_length=64)


class CollectionParams(PageParams):
    user_id = serializers.IntegerField(required=False, min_value=1, max_value=9223372036854775807)


class SuggestionParams(serializers.Serializer):
    q = serializers.CharField(max_length=200, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=20, default=8)
    type = serializers.ChoiceField(choices=("all", "apps", "users"), default="all")


class AppSuggestionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    icon_url = serializers.URLField(allow_null=True)


class UserSuggestionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    avatar_url = serializers.URLField(allow_null=True)


class SuggestionSerializer(serializers.Serializer):
    apps = AppSuggestionSerializer(many=True)
    users = UserSuggestionSerializer(many=True)


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
