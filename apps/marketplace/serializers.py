from rest_framework import serializers

from .models import Application, Category, Collection, Distribution
from apps.user.serializers import UserSerializer


class ApplicationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

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
        ]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description"]


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
            "release_description",
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
        return obj.items.count()

    def get_mosaic_icons(self, obj: Collection) -> list:
        return obj.mosaic_icons(4)

