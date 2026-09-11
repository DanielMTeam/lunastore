from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.core.search.documents import application_is_indexable, application_to_document, user_to_document
from apps.core.search.pagination import MeilisearchPaginator
from apps.core.search.service import (
    SearchService,
    _build_app_filters,
    _join_filters,
    is_query_too_short,
    normalize_query,
    parse_is_free,
    parse_optional_int,
)
from apps.marketplace.models import Application, Category

User = get_user_model()


@override_settings(MEILISEARCH_ENABLED=False)
class SearchDocumentsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="search_dev",
            password="password123",
            email="search_dev@example.com",
            is_active=True,
        )
        cls.category = Category.objects.create(name="Games", description="Games desc")
        cls.app = Application.objects.create(
            user=cls.user,
            title="Luna Browser",
            title_en="Luna Browser EN",
            description="Fast retro browser",
            slogan="Browse the web",
            price=0,
            is_private=False,
        )
        cls.app.categories.add(cls.category)

    def test_application_document_contains_localized_fields(self):
        doc = application_to_document(self.app)
        self.assertEqual(doc["id"], self.app.pk)
        self.assertEqual(doc["title"], "Luna Browser")
        self.assertEqual(doc["title_en"], "Luna Browser EN")
        self.assertIn(self.category.id, doc["category_ids"])
        self.assertFalse(doc["is_private"])
        self.assertFalse(doc["is_under_dmca"])

    def test_private_application_excluded_from_indexable(self):
        private_app = Application.objects.create(
            user=self.user,
            title="Hidden",
            description="Hidden app",
            is_private=True,
        )
        self.assertFalse(application_is_indexable(private_app))

    def test_dmca_application_excluded_from_indexable(self):
        dmca_app = Application.objects.create(
            user=self.user,
            title="Blocked",
            description="Blocked app",
            is_under_dmca=True,
        )
        self.assertFalse(application_is_indexable(dmca_app))

    def test_user_document_contains_public_fields_only(self):
        doc = user_to_document(self.user)
        self.assertEqual(doc["username"], "search_dev")
        self.assertIn("description", doc)
        self.assertNotIn("email", doc)
        self.assertTrue(doc["is_active"])


class SearchFiltersTest(TestCase):
    def test_build_app_filters_with_all_options(self):
        filters = _build_app_filters(category_id="3", author_id="9", is_free=True)
        self.assertEqual(
            _join_filters(filters),
            "is_private = false AND is_under_dmca = false AND category_ids = 3 AND user_id = 9 AND price = 0",
        )

    def test_build_app_filters_ignores_invalid_ids(self):
        filters = _build_app_filters(category_id="bad", author_id="")
        self.assertEqual(_join_filters(filters), "is_private = false AND is_under_dmca = false")

    def test_normalize_query_strips_and_limits(self):
        self.assertEqual(normalize_query("  hello  "), "hello")
        self.assertEqual(normalize_query("x" * 300), "x" * 200)
        self.assertEqual(normalize_query(None), "")

    def test_is_query_too_short(self):
        self.assertTrue(is_query_too_short("a"))
        self.assertTrue(is_query_too_short(" "))
        self.assertFalse(is_query_too_short("ab"))

    def test_parse_is_free(self):
        self.assertTrue(parse_is_free("on"))
        self.assertTrue(parse_is_free("1"))
        self.assertTrue(parse_is_free("true"))
        self.assertFalse(parse_is_free("yes"))
        self.assertFalse(parse_is_free(""))

    def test_parse_optional_int(self):
        self.assertEqual(parse_optional_int("9"), 9)
        self.assertIsNone(parse_optional_int("bad"))
        self.assertIsNone(parse_optional_int(""))
        self.assertIsNone(parse_optional_int(None))


class MeilisearchPaginatorTest(TestCase):
    def test_paginator_reports_total_and_pages(self):
        paginator = MeilisearchPaginator(["a", "b"], 2, 25)
        page = paginator.get_page(2)
        self.assertEqual(paginator.count, 25)
        self.assertEqual(paginator.num_pages, 13)
        self.assertEqual(page.number, 2)
        self.assertTrue(page.has_previous())
        self.assertTrue(page.has_other_pages())


@override_settings(
    MEILISEARCH_ENABLED=True,
    MEILISEARCH_MASTER_KEY="test",
    RATELIMIT_BACKEND="memory",
)
class SearchServiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # avoid real meilisearch during fixture create (signals)
        with override_settings(MEILISEARCH_ENABLED=False):
            cls.user = User.objects.create_user(
                username="api_search_user",
                password="password123",
                email="api_search_user@example.com",
                is_active=True,
            )
            cls.app = Application.objects.create(
                user=cls.user,
                title="Searchable App",
                description="Description",
                is_private=False,
            )

    @patch("apps.core.search.service.get_meili_client")
    def test_search_application_ids_returns_ordered_ids(self, mock_get_client):
        mock_index = MagicMock()
        mock_index.search.return_value = {
            "hits": [{"id": self.app.id}],
            "estimatedTotalHits": 1,
        }
        mock_client = MagicMock()
        mock_client.index.return_value = mock_index
        mock_get_client.return_value = mock_client

        ids, total = SearchService.search_application_ids("Searchable")
        self.assertEqual(ids, [self.app.id])
        self.assertEqual(total, 1)
        search_args = mock_index.search.call_args[0][1]
        self.assertEqual(search_args["filter"], "is_private = false AND is_under_dmca = false")
        self.assertEqual(search_args["limit"], 10)
        self.assertEqual(search_args["offset"], 0)

    @patch("apps.core.search.service.get_meili_client")
    def test_search_application_ids_supports_offset(self, mock_get_client):
        mock_index = MagicMock()
        mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 30}
        mock_client = MagicMock()
        mock_client.index.return_value = mock_index
        mock_get_client.return_value = mock_client

        ids, total = SearchService.search_application_ids("Searchable", limit=10, offset=20)
        self.assertEqual(ids, [])
        self.assertEqual(total, 30)
        search_args = mock_index.search.call_args[0][1]
        self.assertEqual(search_args["offset"], 20)

    @patch("apps.core.search.service.get_meili_client")
    def test_suggest_returns_lightweight_payload(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.multi_search.return_value = {
            "results": [
                {
                    "indexUid": "applications",
                    "hits": [{"id": 1, "title": "App", "icon_url": "//cdn/icon.png"}],
                },
                {
                    "indexUid": "users",
                    "hits": [{"id": 2, "username": "dev", "avatar_url": "//cdn/avatar.png"}],
                },
            ]
        }
        mock_get_client.return_value = mock_client

        data = SearchService.suggest("app", limit=4, search_type="all")
        self.assertEqual(len(data["apps"]), 1)
        self.assertEqual(data["apps"][0]["url"], "/app.php?id=1")
        self.assertEqual(data["users"][0]["url"], "/profile.php?id=2")

    @patch("apps.core.search.service.get_meili_client")
    def test_search_view_uses_meilisearch(self, mock_get_client):
        mock_index = MagicMock()
        mock_index.search.return_value = {
            "hits": [{"id": self.app.id}],
            "estimatedTotalHits": 1,
        }
        mock_client = MagicMock()
        mock_client.index.return_value = mock_index
        mock_get_client.return_value = mock_client

        response = self.client.get("/search.php", {"q": "Searchable"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Searchable App")

    @patch("apps.core.search.service.get_meili_client")
    def test_search_view_pagination_uses_offset(self, mock_get_client):
        mock_index = MagicMock()
        mock_index.search.return_value = {
            "hits": [{"id": self.app.id}],
            "estimatedTotalHits": 25,
        }
        mock_client = MagicMock()
        mock_client.index.return_value = mock_index
        mock_get_client.return_value = mock_client

        response = self.client.get("/search.php", {"q": "Searchable", "page": "3"})
        self.assertEqual(response.status_code, 200)
        search_args = mock_index.search.call_args[0][1]
        self.assertEqual(search_args["offset"], 20)

    @patch("apps.core.search.service.get_meili_client")
    def test_search_suggest_endpoint(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.multi_search.return_value = {
            "results": [
                {"indexUid": "applications", "hits": []},
                {"indexUid": "users", "hits": []},
            ]
        }
        mock_get_client.return_value = mock_client

        response = self.client.get("/search.php", {"mode": "suggest", "q": "lu"})
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"apps": [], "users": []})

        short = self.client.get("/search.php", {"mode": "suggest", "q": "l"})
        self.assertJSONEqual(short.content, {"apps": [], "users": []})

    @patch("apps.core.search.service._add_documents")
    @patch("apps.core.search.service._ensure_indexes_once")
    def test_new_application_triggers_index_sync(self, mock_ensure, mock_add):
        SearchService.index_application(self.app)
        mock_ensure.assert_called_once()
        mock_add.assert_called_once()
        self.assertFalse(mock_add.call_args.kwargs.get("wait"))
