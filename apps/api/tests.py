from rest_framework.test import APITestCase
from rest_framework import status
from django.test import override_settings
from unittest.mock import patch
from apps.user.models import User
from apps.marketplace.models import Application, Category, Collection, CollectionItem
from apps.core.search import SearchUnavailableError
import logging

logger = logging.getLogger('api_tests')


@override_settings(ROOT_URLCONF='lunastore.urls_api')
class APIViewsTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info('[API] Creating test data for API endpoints...')
        cls.user = User.objects.create(
            username='ApiUser',
            password='ApiPassword123!',
            is_active=True
        )

        cls.category = Category.objects.create(
            name='Utilities',
            description='System utilities'
        )

        cls.app = Application.objects.create(
            user=cls.user,
            title='SuperCleaner',
            description='Cleans your system beautifully.',
            slogan='Clean fast',
            price=0,
            is_under_dmca=False
        )
        cls.app.categories.add(cls.category)

        cls.dmca_app = Application.objects.create(
            user=cls.user,
            title='PirateApp',
            description='This app is under DMCA',
            is_under_dmca=True
        )
        cls.dmca_app.categories.add(cls.category)

    def test_get_profile_info_success(self):
        url = '/method/user/getProfileInfo/'
        response = self.client.get(url, {'id': self.user.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'ApiUser')

    def test_get_profile_info_missing_id(self):
        url = '/method/user/getProfileInfo/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        self.assertEqual(response.data['error_code'], 2)

    def test_get_profile_info_not_found(self):
        url = '/method/user/getProfileInfo/'
        response = self.client.get(url, {'id': 9999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_app_info_success(self):
        url = '/method/marketplace/getAppInfo/'
        response = self.client.get(url, {'id': self.app.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'SuperCleaner')

    def test_get_app_info_dmca(self):
        url = '/method/marketplace/getAppInfo/'
        response = self.client.get(url, {'id': self.dmca_app.id})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['status'], 'error')
        self.assertEqual(response.data['error_code'], 2001)

    def test_heartbeat(self):
        url = '/method/service/heartbeat/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')
        self.assertIn('version', response.data)

    def test_kunyakin_easter_egg(self):
        url = '/method/service/kunyakin/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['answer'],
            'влад кунякин пробудил шаринган')


@override_settings(
    ROOT_URLCONF='lunastore.urls_api',
    MEILISEARCH_ENABLED=True,
    RATELIMIT_BACKEND='memory',
)
class SearchAPITest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        with override_settings(MEILISEARCH_ENABLED=False):
            cls.user = User.objects.create(
                username='SearchApiUser',
                password='ApiPassword123!',
                email='searchapi@example.com',
                is_active=True,
            )
            cls.app = Application.objects.create(
                user=cls.user,
                title='SearchableCleaner',
                description='Cleans via search API',
                slogan='Find me',
                price=0,
                is_private=False,
                is_under_dmca=False,
            )

    @patch('apps.api.views.SearchService.search_application_ids')
    def test_v1_marketplace_search_enumerated(self, mock_search):
        mock_search.return_value = ([self.app.id], 1)
        response = self.client.get(
            '/method/marketplace/search/', {'query': 'Searchable'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('1', response.data)
        self.assertEqual(response.data['1']['title'], 'SearchableCleaner')
        mock_search.assert_called_once()
        self.assertEqual(mock_search.call_args.kwargs.get('limit'), 1000)

    @patch('apps.api.views.SearchService.search_user_ids')
    def test_v1_user_search_enumerated(self, mock_search):
        mock_search.return_value = ([self.user.id], 1)
        response = self.client.get('/method/user/search/', {'query': 'SearchApi'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('1', response.data)
        self.assertEqual(response.data['1']['username'], 'SearchApiUser')

    def test_v1_marketplace_search_missing_query(self):
        response = self.client.get('/method/marketplace/search/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error_code'], 2)

    @patch('apps.api.views.SearchService.search_application_ids')
    def test_v1_marketplace_search_unavailable(self, mock_search):
        mock_search.side_effect = SearchUnavailableError('down')
        response = self.client.get(
            '/method/marketplace/search/', {'query': 'Searchable'}
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['error_code'], 1)

    @patch('apps.api.v2.views.SearchService.search_user_ids')
    def test_v2_user_search_paginated(self, mock_search):
        mock_search.return_value = ([self.user.id], 1)
        response = self.client.get('/v2/user/search/', {'query': 'SearchApi'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['results'][0]['username'], 'SearchApiUser')

    @patch('apps.api.v2.views.SearchService.search_application_ids')
    def test_v2_marketplace_search_paginated(self, mock_search):
        mock_search.return_value = ([self.app.id], 1)
        response = self.client.get(
            '/v2/marketplace/search/', {'query': 'Searchable'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'SearchableCleaner')

    def test_v2_marketplace_search_missing_query(self):
        response = self.client.get('/v2/marketplace/search/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Query parameter is required')

    @patch('apps.api.v2.views.SearchService.search_application_ids')
    def test_v2_marketplace_search_unavailable(self, mock_search):
        mock_search.side_effect = SearchUnavailableError('down')
        response = self.client.get(
            '/v2/marketplace/search/', {'query': 'Searchable'}
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['error'], 'Search service unavailable')

    @patch('apps.api.v2.views.SearchService.suggest')
    def test_v2_search_suggest(self, mock_suggest):
        mock_suggest.return_value = {
            'apps': [{'id': self.app.id, 'title': 'SearchableCleaner',
                      'icon_url': '', 'url': f'/app.php?id={self.app.id}'}],
            'users': [],
        }
        response = self.client.get('/v2/search/suggest/', {'query': 'Search'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['apps']), 1)
        self.assertEqual(response.data['users'], [])


@override_settings(ROOT_URLCONF='lunastore.urls_api')
class CollectionV2APITest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info('[API] Creating collection test data...')
        cls.user = User.objects.create(
            username='ColApiUser', password='ApiPassword123!', is_active=True,
            email='colapi@example.com'
        )
        cls.other = User.objects.create(
            username='ColApiOther', password='ApiPassword123!', is_active=True,
            email='colapiother@example.com'
        )
        cls.app = Application.objects.create(
            user=cls.user,
            title='ColApiApp',
            description='Desc',
            slogan='Slogan',
            price=0,
            is_under_dmca=False,
        )
        cls.public_col = Collection.objects.create(
            owner=cls.user,
            title='Public API Col',
            description='Public',
            is_public=True,
        )
        cls.private_col = Collection.objects.create(
            owner=cls.user,
            title='Private API Col',
            description='Private',
            is_public=False,
        )
        CollectionItem.objects.create(
            collection=cls.public_col, application=cls.app
        )

    def test_list_public(self):
        response = self.client.get('/v2/collection/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data.get('results', response.data)]
        self.assertIn(self.public_col.id, ids)
        self.assertNotIn(self.private_col.id, ids)

    def test_retrieve_public(self):
        response = self.client.get(f'/v2/collection/{self.public_col.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.public_col.id)

    def test_retrieve_private_forbidden(self):
        request_logger = logging.getLogger("django.request")
        previous_level = request_logger.level
        request_logger.setLevel(logging.ERROR)
        try:
            response = self.client.get(f'/v2/collection/{self.private_col.id}/')
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            self.assertEqual(response.data.get('error_code'), 5001)
        finally:
            request_logger.setLevel(previous_level)

    def test_apps_action(self):
        response = self.client.get(f'/v2/collection/{self.public_col.id}/apps/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        titles = [item['title'] for item in results]
        self.assertIn('ColApiApp', titles)

    def test_by_user(self):
        response = self.client.get(
            '/v2/collection/by_user/', {'user_id': self.user.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        ids = [item['id'] for item in results]
        self.assertIn(self.public_col.id, ids)
        self.assertNotIn(self.private_col.id, ids)

    def test_execute_collection_methods(self):
        response = self.client.post(
            '/v2/execute/',
            {
                'code': [
                    {'method': 'collection.list', 'params': {}},
                    {
                        'method': 'collection.retrieve',
                        'params': {'pk': self.public_col.id},
                    },
                    {
                        'method': 'collection.apps',
                        'params': {'pk': self.public_col.id},
                    },
                    {
                        'method': 'collection.by_user',
                        'params': {'user_id': self.user.id},
                    },
                ]
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        responses = response.data['responses']
        self.assertEqual(len(responses), 4)
        for item in responses:
            self.assertNotEqual(item.get('error_code'), 4005)

    def test_execute_unknown_method(self):
        response = self.client.post(
            '/v2/execute/',
            {'code': [{'method': 'collection.unknown', 'params': {}}]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['responses'][0]['error_code'], 4005)
