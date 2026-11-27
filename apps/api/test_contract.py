from django.test import SimpleTestCase, override_settings
from django.urls import Resolver404, resolve

from apps.marketplace.models import Category
from apps.marketplace.serializers import CategorySerializer


class V2RoutingContractTests(SimpleTestCase):
    def test_v1_rpc_routes_are_gone_from_all_services(self):
        for urlconf in ("lunastore.urls_api", "lunastore.urls", "lunastore.urls_private"):
            for route in (
                "/method/", "/method/user/getProfileInfo/", "/method/user/getPublicUploadToken/",
                "/method/marketplace/search/", "/method/category/getAppList/",
                "/method/distribution/getDistributionsList/", "/method/service/heartbeat/",
            ):
                with self.subTest(urlconf=urlconf, route=route), self.assertRaises(Resolver404):
                    resolve(route, urlconf=urlconf)

    def test_v2_legacy_aliases_resolve_to_the_same_operations(self):
        routes = (
            ("user/", "v2-user-list"),
            ("marketplace/1/", "v2-marketplace-detail"),
            ("category/1/apps/", "v2-category-apps"),
            ("distribution/by_app/", "v2-distribution-by-app"),
            ("collection/by_user/", "v2-collection-by-user"),
            ("platform/", "v2-platform-list"),
            ("auth/token/refresh/", "token_refresh"),
            ("execute/", "v2-execute"),
        )
        for route, name in routes:
            with self.subTest(route=route):
                canonical = resolve(f"/v2/{route}", urlconf="lunastore.urls_api")
                self.assertEqual(canonical.url_name, name)
                for urlconf in ("lunastore.urls_api", "lunastore.urls", "lunastore.urls_private"):
                    alias = resolve(f"/method/v2/{route}", urlconf=urlconf)
                    self.assertEqual(alias.url_name, name)
                    self.assertIs(alias.func.cls, canonical.func.cls)


class CategoryIconContractTests(SimpleTestCase):
    @override_settings(API_MEDIA_BASE_URL="https://assets.example.test/")
    def test_v2_keeps_legacy_icon_and_adds_absolute_url(self):
        for icon, expected in (
            ("util", "https://assets.example.test/staticfiles/img/category-icons/util.png"),
            ("emuvm", "https://assets.example.test/staticfiles/img/category-icons/emuvm.png"),
            ("", None),
            (None, None),
            ("missing", None),
        ):
            with self.subTest(icon=icon):
                result = CategorySerializer(Category(icon=icon)).data
                self.assertEqual(result["icon"], icon)
                self.assertEqual(result["icon_url"], expected)
