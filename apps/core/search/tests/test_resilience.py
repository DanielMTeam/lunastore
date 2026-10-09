from io import StringIO
from queue import Queue
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections, transaction
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from safedelete.config import HARD_DELETE

from apps.core.search.client import SearchUnavailableError
from apps.core.search.indexes import APPLICATIONS_INDEX, USERS_INDEX
from apps.core.search.locks import index_write_lock
from apps.core.search.service import SearchService, _ensure_index, _wait_for_task
from apps.core.search.tasks import sync_application_task, sync_user_task
from apps.marketplace.models import Application, Category
from apps.user.models import User


@override_settings(MEILISEARCH_ENABLED=False, RATELIMIT_BACKEND="memory")
class DatabaseFallbackTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(
            username="FallbackDeveloper", email="fallback@example.com", description="Retro engineer", is_active=True,
        )
        cls.category = Category.objects.create(name="Tools")
        cls.apps = []
        for title in ("Fallback Browser", "Fallback Editor", "Fallback Player"):
            cls.apps.append(Application.objects.create(user=cls.user, title=title, price=0))
        cls.apps[0].categories.add(cls.category)
        for flags in ({"is_private": True}, {"is_under_dmca": True}, {}):
            app = Application.objects.create(user=cls.user, title="Fallback Hidden", **flags)
            if not flags:
                app.delete()
        User.objects.create(username="FallbackInactive", email="inactive@example.com", is_active=False)
        deleted = User.objects.create(username="FallbackDeleted", email="deleted@example.com", is_active=True)
        deleted.delete()

    def test_application_ids_count_and_slice_are_bounded(self):
        with self.assertNumQueries(2):
            ids, total = SearchService.search_application_ids("fallback", limit=1, offset=1)
        self.assertEqual(ids, [self.apps[1].pk])
        self.assertEqual(total, 3)

    def test_out_of_range_offset_returns_count_without_sql_slice(self):
        for offset in (3, 9223372036854775808, 10 ** 100):
            with self.subTest(offset=offset), self.assertNumQueries(1):
                self.assertEqual(SearchService.search_application_ids("fallback", offset=offset), ([], 3))
            with self.subTest(user_offset=offset), self.assertNumQueries(1):
                self.assertEqual(SearchService.search_user_ids("Fallback", offset=offset), ([], 1))

    def test_empty_results_skip_sql_slice(self):
        with self.assertNumQueries(1):
            self.assertEqual(SearchService.search_application_ids("absent", offset=10 ** 100), ([], 0))

    def test_huge_page_does_not_overflow_postgresql_offset(self):
        response = self.client.get("/search.php", {"q": "Fallback", "page": str(10 ** 100)})
        self.assertEqual(response.status_code, 200)

    def test_filters_and_visibility(self):
        ids, total = SearchService.search_application_ids(
            "fallback", category_id=str(self.category.pk), author_id=str(self.user.pk), is_free=True,
        )
        self.assertEqual((ids, total), ([self.apps[0].pk], 1))
        Application.objects.filter(pk=self.apps[0].pk).update(price=10)
        self.assertEqual(SearchService.search_application_ids("fallback", is_free=True)[1], 2)
        self.assertEqual(SearchService.search_application_ids("fallback", author_id=-1), ([], 0))

    def test_translations_slogan_and_original_author(self):
        for field in ("title_ru", "description_en", "slogan_uk", "title_be", "description_kk", "original_author"):
            with self.subTest(field=field):
                Application.objects.filter(pk=self.apps[0].pk).update(**{field: "UniqueNeedle"})
                self.assertEqual(SearchService.search_application_ids("uniqueneedle")[0], [self.apps[0].pk])
                Application.objects.filter(pk=self.apps[0].pk).update(**{field: ""})

    def test_users_search_public_fields_only(self):
        self.assertEqual(SearchService.search_user_ids("Fallback"), ([self.user.pk], 1))
        self.assertEqual(SearchService.search_user_ids("engineer"), ([self.user.pk], 1))

    @override_settings(MEILISEARCH_ENABLED=True)
    @patch("apps.core.search.service.get_meili_client")
    def test_connection_error_falls_back(self, get_client):
        get_client.return_value.index.return_value.search.side_effect = SearchUnavailableError("down")
        self.assertEqual(SearchService.search_application_ids("fallback")[1], 3)
        self.assertEqual(SearchService.search_user_ids("Fallback")[1], 1)
        get_client.return_value.multi_search.side_effect = TimeoutError("down")
        data = SearchService.suggest("Fallback", limit=4)
        self.assertEqual(len(data["apps"]), 2)
        self.assertEqual(len(data["users"]), 1)

    def test_short_queries_empty_queries_and_suggestions(self):
        self.assertEqual(SearchService.search_application_ids(" "), ([], 0))
        self.assertEqual(SearchService.search_user_ids(None), ([], 0))
        self.assertEqual(SearchService.search_application_ids("F")[1], 3)
        self.assertEqual(SearchService.suggest("F"), {"apps": [], "users": []})
        data = SearchService.suggest("Fallback", limit=2, search_type="apps")
        self.assertEqual(len(data["apps"]), 2)
        self.assertEqual(data["users"], [])
        self.assertEqual(data["apps"][0]["url"], f"/app.php?id={self.apps[0].pk}")

    def test_web_page_and_suggest_fallback(self):
        response = self.client.get("/search.php", {"q": "Fallback"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["results"].paginator.count, 3)
        response = self.client.get("/search.php", {"q": "Fallback", "mode": "suggest"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["apps"]), 3)

    @override_settings(MEILISEARCH_ENABLED=True)
    @patch("apps.core.search.service.get_meili_client")
    def test_stale_suggest_hits_are_filtered_by_current_database_state(self, get_client):
        app_ids = list(Application.objects.all_with_deleted().values_list("pk", flat=True))
        user_ids = list(User.objects.all_with_deleted().values_list("pk", flat=True))
        # Preserve Meilisearch ranking while ignoring its stale metadata.
        app_ids.reverse()
        app_ids.append(99999999)
        user_ids.append(99999999)
        get_client.return_value.multi_search.return_value = {"results": [
            {"indexUid": "applications", "hits": [
                {"id": pk, "title": "Outdated title", "icon_url": "//old/icon.png"} for pk in app_ids
            ]},
            {"indexUid": "users", "hits": [
                {"id": pk, "username": "Outdated name", "avatar_url": "//old/avatar.png"} for pk in user_ids
            ]},
        ]}
        with self.assertNumQueries(2):
            data = SearchService.suggest("Fallback", limit=20)
        self.assertEqual([app["id"] for app in data["apps"]], [app.pk for app in reversed(self.apps)])
        self.assertEqual([app["title"] for app in data["apps"]], [app.title for app in reversed(self.apps)])
        self.assertEqual([user["id"] for user in data["users"]], [self.user.pk])
        self.assertEqual(data["users"][0]["username"], self.user.username)

    @override_settings(MEILISEARCH_ENABLED=True)
    @patch("apps.core.search.service.get_meili_client")
    def test_web_suggest_hides_newly_private_app_before_index_update(self, get_client):
        get_client.return_value.multi_search.return_value = {"results": [{
            "indexUid": "applications", "hits": [{"id": self.apps[0].pk, "title": "Previously public"}],
        }]}
        Application.objects.filter(pk=self.apps[0].pk).update(is_private=True)
        response = self.client.get("/search.php", {"q": "Fallback", "mode": "suggest"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"apps": [], "users": []})


@override_settings(MEILISEARCH_ENABLED=True)
class IndexSignalsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        with override_settings(MEILISEARCH_ENABLED=False):
            cls.user = User.objects.create(username="signal_user")
            cls.app = Application.objects.create(user=cls.user, title="Before")
            cls.category = Category.objects.create(name="Tools")
            cls.app.categories.add(cls.category)

    def test_save_only_enqueues_after_commit(self):
        with patch("apps.core.search.signals.sync_application_task") as queued:
            enqueue = queued.enqueue
            with patch("apps.core.search.service.get_meili_client") as client:
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    self.app.title = "After"
                    self.app.save()
                    enqueue.assert_not_called()
                    client.assert_not_called()
                self.assertEqual(len(callbacks), 1)
                enqueue.assert_called_once_with(self.app.pk, using="default")

    def test_rollback_does_not_enqueue(self):
        with patch("apps.core.search.signals.sync_application_task") as queued:
            enqueue = queued.enqueue
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        self.app.save()
                        raise ValueError("rollback")
                except ValueError:
                    pass
            enqueue.assert_not_called()

    def test_enqueue_failure_keeps_save_successful(self):
        with patch("apps.core.search.signals.sync_application_task") as queued:
            queued.enqueue.side_effect = ConnectionError("redis")
            with self.assertLogs("apps.core.search.signals", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    self.app.title = "Committed"
                    self.app.save()
        self.app.refresh_from_db()
        self.assertEqual(self.app.title, "Committed")

    def test_soft_delete_restore_and_hard_delete_enqueue(self):
        with patch("apps.core.search.signals.sync_application_task") as queued:
            enqueue = queued.enqueue
            app_id = self.app.pk
            for operation in (self.app.delete, self.app.undelete, lambda: self.app.delete(force_policy=HARD_DELETE)):
                with self.captureOnCommitCallbacks(execute=True):
                    operation()
                self.assertEqual(enqueue.call_args.args, (app_id,))
            self.assertEqual(enqueue.call_count, 3)

    def test_forward_categories_changes(self):
        with patch("apps.core.search.signals.sync_application_task") as queued:
            enqueue = queued.enqueue
            for operation in (
                lambda: self.app.categories.remove(self.category),
                lambda: self.app.categories.add(self.category),
                self.app.categories.clear,
            ):
                with self.captureOnCommitCallbacks(execute=True):
                    operation()
                self.assertEqual(enqueue.call_args.args, (self.app.pk,))
            self.assertEqual(enqueue.call_count, 3)

    def test_reverse_categories_changes_and_clear(self):
        # Locate the reverse manager without depending on the relation's label.
        accessor = Application._meta.get_field("categories").remote_field.get_accessor_name()
        reverse = getattr(self.category, accessor)
        with patch("apps.core.search.signals.sync_application_task") as queued:
            enqueue = queued.enqueue
            for operation in (lambda: reverse.remove(self.app), lambda: reverse.add(self.app), reverse.clear):
                with self.captureOnCommitCallbacks(execute=True):
                    operation()
                self.assertEqual(enqueue.call_args.args, (self.app.pk,))
            self.assertEqual(enqueue.call_count, 3)

    def test_user_save_enqueues_id_and_database(self):
        with patch("apps.core.search.signals.sync_user_task") as queued:
            enqueue = queued.enqueue
            with self.captureOnCommitCallbacks(execute=True):
                self.user.save()
            enqueue.assert_called_once_with(self.user.pk, using="default")


@override_settings(MEILISEARCH_ENABLED=True)
class IndexWorkerTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        with override_settings(MEILISEARCH_ENABLED=False):
            cls.user = User.objects.create(username="worker_user")
            cls.app = Application.objects.create(user=cls.user, title="Before")

    def setUp(self):
        self.meili = MagicMock()
        self.meili.get_tasks.return_value.results = []
        client_patch = patch("apps.core.search.tasks.get_meili_client", return_value=self.meili)
        client_patch.start()
        self.addCleanup(client_patch.stop)

    @patch("apps.core.search.tasks.sync_application_task")
    @patch("apps.core.search.tasks.SearchService.index_application")
    def test_pending_swap_defers_until_finished_then_reads_latest_state(self, index, queued):
        self.meili.get_tasks.return_value.results = [SimpleNamespace(status="processing")]
        sync_application_task.func(self.app.pk)
        index.assert_not_called()
        queued.using.return_value.enqueue.assert_called_once_with(self.app.pk, using="default")
        Application.objects.filter(pk=self.app.pk).update(title="Changed after timeout")
        self.meili.get_tasks.return_value.results = []
        sync_application_task.func(self.app.pk)
        self.assertEqual(index.call_args.args[0].title, "Changed after timeout")

    @patch("apps.core.search.tasks.time.sleep")
    @patch("apps.core.search.tasks.SearchService.index_application")
    def test_unknown_swap_status_fails_without_writing(self, index, sleep):
        self.meili.get_tasks.side_effect = ConnectionError("unknown swap status")
        with self.assertLogs("apps.core.search.tasks", level="ERROR"):
            with self.assertRaises(SearchUnavailableError):
                sync_application_task.func(self.app.pk)
        index.assert_not_called()
        self.assertEqual(self.meili.get_tasks.call_count, 3)

    @patch("apps.core.search.tasks.SearchService.index_application")
    def test_worker_reads_latest_state_and_can_repeat(self, index):
        Application.objects.filter(pk=self.app.pk).update(title="After")
        sync_application_task.func(self.app.pk)
        sync_application_task.func(self.app.pk)
        self.assertEqual(index.call_count, 2)
        self.assertEqual(index.call_args.args[0].title, "After")
        self.assertEqual(index.call_args.kwargs, {"wait": True})

    @patch("apps.core.search.tasks.SearchService.delete_application")
    def test_missing_and_soft_deleted_application_removed(self, delete):
        self.app.delete()
        sync_application_task.func(self.app.pk)
        sync_application_task.func(99999999)
        self.assertEqual(delete.call_count, 2)

    @patch("apps.core.search.tasks.SearchService.index_user")
    @patch("apps.core.search.tasks.SearchService.delete_user")
    def test_user_sync_and_removal(self, delete, index):
        sync_user_task.func(self.user.pk)
        index.assert_called_once()
        self.user.delete()
        sync_user_task.func(self.user.pk)
        delete.assert_called_once_with(self.user.pk, wait=True)

    @patch("apps.core.search.tasks.time.sleep")
    @patch("apps.core.search.tasks.SearchService.index_application")
    def test_failed_indexing_retries_then_raises(self, index, sleep):
        index.side_effect = SearchUnavailableError("down")
        with self.assertLogs("apps.core.search.tasks", level="ERROR"):
            with self.assertRaises(SearchUnavailableError):
                sync_application_task.func(self.app.pk)
        self.assertEqual(index.call_count, 3)
        self.assertEqual([call.args for call in sleep.call_args_list], [(1,), (2,)])
        # The lock was released even though every attempt failed.
        index.side_effect = None
        sync_application_task.func(self.app.pk)


class IndexTaskStatusTest(SimpleTestCase):
    def test_failed_or_pending_task_never_counts_as_success(self):
        for status in ("failed", "canceled", "enqueued", "processing"):
            client = MagicMock()
            client.get_task.return_value = SimpleNamespace(status=status, error="problem")
            with self.subTest(status=status), self.assertRaises(SearchUnavailableError):
                _wait_for_task(client, SimpleNamespace(task_uid=42))

    def test_timeout_checks_final_status(self):
        client = MagicMock()
        client.wait_for_task.side_effect = TimeoutError()
        client.get_task.return_value = SimpleNamespace(status="succeeded")
        _wait_for_task(client, SimpleNamespace(task_uid=42))
        client.get_task.return_value = SimpleNamespace(status="processing")
        with self.assertRaises(SearchUnavailableError):
            _wait_for_task(client, SimpleNamespace(task_uid=42))

    def test_connection_failure_does_not_create_replacement_live_index(self):
        client = MagicMock()
        client.get_index.side_effect = ConnectionError("down")
        with self.assertRaises(SearchUnavailableError):
            _ensure_index(client, "applications", {})
        client.create_index.assert_not_called()

    def test_invalid_batch_size_rejected_by_command(self):
        with self.assertRaises(CommandError):
            call_command("reindex_search", batch_size=0, stdout=StringIO())


@override_settings(MEILISEARCH_ENABLED=False)
class IndexSwapTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="swap_user")
        cls.app = Application.objects.create(user=cls.user, title="Swap App")

    def setUp(self):
        self.client_mock = MagicMock()
        self.client_mock.get_tasks.return_value.results = []
        self.client_mock.get_task.return_value = SimpleNamespace(status="succeeded")
        self.client_mock.swap_indexes.return_value = SimpleNamespace(task_uid=999)
        self.client_patches = [
            patch("apps.core.search.reindex.get_meili_client", return_value=self.client_mock),
            patch("apps.core.search.service.get_meili_client", return_value=self.client_mock),
        ]
        for client_patch in self.client_patches:
            client_patch.start()
            self.addCleanup(client_patch.stop)

    def test_reindex_builds_temp_and_swaps_without_clearing_live_index(self):
        count = SearchService.reindex_applications(batch_size=1)
        self.assertEqual(count, 1)
        temp_uid = self.client_mock.create_index.call_args.args[0]
        self.assertTrue(temp_uid.startswith("applications_rebuild_"))
        self.client_mock.swap_indexes.assert_called_once_with([{"indexes": ["applications", temp_uid]}])
        self.client_mock.index.return_value.delete_all_documents.assert_not_called()
        self.client_mock.delete_index.assert_called_once_with(temp_uid)
        calls = [call[0] for call in self.client_mock.mock_calls]
        self.assertLess(calls.index("index().add_documents"), calls.index("swap_indexes"))

    def test_failed_settings_or_batch_keeps_live_index(self):
        self.client_mock.get_task.return_value = SimpleNamespace(status="failed", error="bad settings")
        with self.assertLogs("apps.core.search.reindex", level="ERROR"):
            with self.assertRaises(SearchUnavailableError):
                SearchService.reindex_applications()
        self.client_mock.swap_indexes.assert_not_called()
        self.client_mock.index.return_value.delete_all_documents.assert_not_called()

    def test_batch_failure_does_not_swap(self):
        self.client_mock.index.return_value.add_documents.side_effect = ConnectionError("batch")
        with self.assertRaises(SearchUnavailableError):
            SearchService.reindex_applications()
        self.client_mock.swap_indexes.assert_not_called()

    def test_uncertain_swap_retains_temporary_index(self):
        self.client_mock.swap_indexes.side_effect = TimeoutError("swap response lost")
        with self.assertLogs("apps.core.search.reindex", level="ERROR"):
            with self.assertRaises(SearchUnavailableError):
                SearchService.reindex_applications()
        self.client_mock.delete_index.assert_not_called()

    def test_swap_task_still_pending_retains_temporary_index(self):
        def finished(uid):
            return SimpleNamespace(status="processing" if uid == 999 else "succeeded")

        self.client_mock.get_task.side_effect = finished
        with self.assertLogs("apps.core.search.reindex", level="ERROR"):
            with self.assertRaises(SearchUnavailableError):
                SearchService.reindex_applications()
        self.client_mock.delete_index.assert_not_called()

    def test_pending_previous_swap_blocks_another_rebuild(self):
        self.client_mock.get_tasks.return_value.results = [SimpleNamespace(status="processing")]
        with self.assertRaises(SearchUnavailableError):
            SearchService.reindex_applications()
        self.client_mock.create_index.assert_not_called()

    def test_empty_index_still_swapped(self):
        self.assertEqual(SearchService.reindex_applications(queryset=Application.objects.none()), 0)
        self.client_mock.swap_indexes.assert_called_once()

    def test_users_use_separate_index(self):
        self.assertEqual(SearchService.reindex_users(), 1)
        self.assertEqual(self.client_mock.swap_indexes.call_args.args[0][0]["indexes"][0], "users")

    def test_cleanup_failure_does_not_fail_successful_swap(self):
        self.client_mock.delete_index.side_effect = ConnectionError("cleanup")
        with self.assertLogs("apps.core.search.reindex", level="ERROR"):
            self.assertEqual(SearchService.reindex_applications(), 1)


@override_settings(MEILISEARCH_ENABLED=False)
class ConcurrentIndexWritesTest(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create(username="concurrent", email="concurrent@example.com")
        self.app = Application.objects.create(user=self.user, title="Before rebuild")
        meili = MagicMock()
        meili.get_tasks.return_value.results = []
        client_patch = patch("apps.core.search.tasks.get_meili_client", return_value=meili)
        client_patch.start()
        self.addCleanup(client_patch.stop)

    def _start_worker(self, work):
        started = Event()
        finished = Event()
        errors = Queue()

        def run():
            try:
                started.set()
                work()
            except Exception as exc:
                errors.put(exc)
            finally:
                connections.close_all()
                finished.set()

        thread = Thread(target=run, daemon=True)
        thread.start()
        self.assertTrue(started.wait(5))
        return thread, finished, errors

    @override_settings(MEILISEARCH_ENABLED=True)
    @patch("apps.core.search.tasks.sync_application_task")
    @patch("apps.core.search.tasks.SearchService.index_application")
    def test_worker_defers_during_rebuild_then_reads_committed_change(self, index, queued):
        with index_write_lock(APPLICATIONS_INDEX):
            thread, finished, errors = self._start_worker(lambda: sync_application_task.func(self.app.pk))
            self.assertTrue(finished.wait(5))
            index.assert_not_called()
            queued.using.assert_called_once()
            self.assertGreater(queued.using.call_args.kwargs["run_after"], timezone.now())
            queued.using.return_value.enqueue.assert_called_once_with(self.app.pk, using="default")
            Application.objects.filter(pk=self.app.pk).update(title="Changed during rebuild")
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertTrue(errors.empty())
        sync_application_task.func(self.app.pk)
        self.assertEqual(index.call_args.args[0].title, "Changed during rebuild")
        queued.using.assert_called_once()

    @override_settings(MEILISEARCH_ENABLED=True)
    @patch("apps.core.search.tasks.sync_application_task")
    @patch("apps.core.search.tasks.SearchService.delete_application")
    def test_delete_during_rebuild_is_reconciled_after_unlock(self, delete, queued):
        with index_write_lock(APPLICATIONS_INDEX):
            thread, finished, errors = self._start_worker(lambda: sync_application_task.func(self.app.pk))
            self.assertTrue(finished.wait(5))
            delete.assert_not_called()
            queued.using.return_value.enqueue.assert_called_once_with(self.app.pk, using="default")
            Application.objects.filter(pk=self.app.pk).update(deleted=timezone.now())
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertTrue(errors.empty())
        sync_application_task.func(self.app.pk)
        delete.assert_called_once_with(self.app.pk, wait=True)

    @override_settings(MEILISEARCH_ENABLED=True)
    @patch("apps.core.search.tasks.sync_user_task")
    @patch("apps.core.search.tasks.SearchService.index_user")
    def test_user_task_defers_when_its_index_is_locked(self, index, queued):
        with index_write_lock(USERS_INDEX):
            thread, finished, errors = self._start_worker(lambda: sync_user_task.func(self.user.pk))
            self.assertTrue(finished.wait(5))
            index.assert_not_called()
            queued.using.return_value.enqueue.assert_called_once_with(self.user.pk, using="default")
        thread.join(5)
        self.assertTrue(errors.empty())
        sync_user_task.func(self.user.pk)
        index.assert_called_once()

    @override_settings(MEILISEARCH_ENABLED=True)
    @patch("apps.core.search.tasks.sync_application_task")
    @patch("apps.core.search.tasks.SearchService.index_application")
    def test_failed_deferred_enqueue_is_not_silently_discarded(self, index, queued):
        queued.using.return_value.enqueue.side_effect = ConnectionError("redis down")
        with index_write_lock(APPLICATIONS_INDEX):
            thread, finished, errors = self._start_worker(lambda: sync_application_task.func(self.app.pk))
            self.assertTrue(finished.wait(5))
            index.assert_not_called()
        thread.join(5)
        self.assertIsInstance(errors.get_nowait(), ConnectionError)

    @override_settings(MEILISEARCH_ENABLED=True)
    @patch("apps.core.search.tasks.SearchService.index_user")
    def test_users_can_sync_while_applications_are_rebuilding(self, index):
        with index_write_lock(APPLICATIONS_INDEX):
            thread, finished, errors = self._start_worker(lambda: sync_user_task.func(self.user.pk))
            self.assertTrue(finished.wait(5))
        thread.join(5)
        self.assertTrue(errors.empty())
        index.assert_called_once()
