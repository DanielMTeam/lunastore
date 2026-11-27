from django.test import SimpleTestCase
from django.urls import resolve


class V2RoutingContractTests(SimpleTestCase):
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
