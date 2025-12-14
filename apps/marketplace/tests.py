from django.test import TestCase
from apps.marketplace.models import Category, Application
from apps.user.models import User
from django.urls import reverse
import logging

logger = logging.getLogger('marketplace')


class CategoryModelTest(TestCase):
    @classmethod
    def setUpTestData(self):
        logger.info('[Marketplace APP; Category MODEL] Creating test data in DB...')
        self.category = Category.objects.create(
            name='TestCategory',
            description='TestCategory description',
            shortcode='testcategory'
        )
    
    def test_category_name_content(self):
        logger.info('[Marketplace APP; Category MODEL] Testing "name" field...')
        obj = Category.objects.get(id=1)
        self.assertEqual(obj.name, 'TestCategory')
        
    def test_str_method(self):
        category = self.category
        self.assertEqual(str(category), 'TestCategory')


class ApplicationModelTest(TestCase):
    @classmethod
    def setUpTestData(self):
        logger.info('[Marketplace APP; Application MODEL] Creating test data in DB...')
        self.application = Application.objects.create(
            title='TestApplication',
            description='TestDescription',
            slogan='TestSlogan',
            price='0',
            developer_site='https://fayzetwin.xyz'
        )

    def test_application_name_content(self):
        logger.info('[Marketplace APP; Application MODEL] Testing "title" field...')
        obj = Application.objects.get(id=1)
        self.assertEqual(obj.title, 'TestApplication')
    
    def test_str_method(self):
        application = self.application
        self.assertEqual(str(application), 'TestApplication')

class HomePageTest(TestCase):
    def test_url_by_url(self):
        logger.info('[Marketplace APP; Home PAGE] Testing URL by direct path...')
        resp = self.client.get('/index.php')
        self.assertEqual(resp.status_code, 200)
    
    def test_url_by_name(self):
        logger.info('[Marketplace APP; Home PAGE] Testing URL by name...')
        resp = self.client.get(reverse('index'))
        self.assertEqual(resp.status_code, 200)
