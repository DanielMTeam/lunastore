from rest_framework.test import APITestCase
from rest_framework import status
from django.test import override_settings
from apps.user.models import User
from apps.marketplace.models import Application, Category
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
            category=cls.category,
            title='SuperCleaner',
            description='Cleans your system beautifully.',
            slogan='Clean fast',
            price=0,
            is_under_dmca=False
        )
        
        cls.dmca_app = Application.objects.create(
            user=cls.user,
            category=cls.category,
            title='PirateApp',
            description='This app is under DMCA',
            is_under_dmca=True
        )

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
        self.assertEqual(response.data['answer'], 'влад кунякин пробудил шаринган')