from rest_framework import serializers

from .models import Application, Category, Distribution


class ApplicationSerializer(serializers.ModelSerializer):
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
        ]
