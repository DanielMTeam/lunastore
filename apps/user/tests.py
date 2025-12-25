from django.test import TestCase
from apps.user.models import User, UserBan, UserActivityLog
from django.urls import reverse
import logging

logger = logging.getLogger('user')


class UserModelTest(TestCase):
    @classmethod
    def setUpTestData(self):
        logger.info('[User APP; User MODEL] Creating test data in DB...')
        self.user = User.objects.create(
            username='TestUser',
            password='TestPassword',
            first_name='TestFirstName',
            last_name='TestLastName',
            email='fayzetwin.xd@gmail.com',
            telegram='@TestTelegram',
            discord='TestDiscord#1234',
            website='https://fayzetwin.xyz',
            description='This is a test user'
        )

    
    def test_category_name_content(self):
        logger.info('[User APP; User MODEL] Testing "username" field...')
        obj = User.objects.get(id=1)
        self.assertEqual(obj.username, 'TestUser')


class UserBanModelTest(TestCase):
    @classmethod
    def setUpTestData(self):
        logger.info('[User APP; UserBan MODEL] Creating test data in DB...')
        obj = User.objects.create(
            username='BannedUser',
            password='BannedPassword')
        self.userban = UserBan.objects.create(
            user = obj,
            ip = '127.0.0.1',
            reason = 'Test reason for ban')
    
    def test_application_name_content(self):
        logger.info('[User APP; UserBan MODEL] Testing "reason" field...')
        obj = UserBan.objects.get(id=1)
        self.assertEqual(obj.reason, 'Test reason for ban')


class UserActivityModelTest(TestCase):
    @classmethod
    def setUpTestData(self):
        logger.info('[User APP; UserActivityLog MODEL] Creating test data in DB...')
        obj = User.objects.create(
            username='ActiveUser',
            password='ActivePassword')
        self.useractivity = UserActivityLog.objects.create(
            user = obj,
            ip = '127.0.0.1',
            action = 'Logged In')
    
    def test_application_name_content(self):
        logger.info('[User APP; UserActivityLog MODEL] Testing "action" field...')
        obj = UserActivityLog.objects.get(id=1)
        self.assertEqual(obj.action, 'Logged In')
        

class LogoutPageTest(TestCase):
    def test_url_by_url(self):
        logger.info('[User APP; Logout PAGE] Testing URL by direct path...')
        resp = self.client.get('/logout.php')  
        self.assertEqual(resp.status_code, 302)
    
    
    def test_url_by_name(self):
        logger.info('[User APP; Logout PAGE] Testing URL by name...')
        resp = self.client.get(reverse('logout'))
        self.assertEqual(resp.status_code, 302)


class RegisterPageTest(TestCase):
    def test_url_by_url(self):
        logger.info('[User APP; Register PAGE] Testing URL by direct path...')
        resp = self.client.get('/register.php')  
        self.assertEqual(resp.status_code, 200)
    
    
    def test_url_by_name(self):
        logger.info('[User APP; Register PAGE] Testing URL by name...')
        resp = self.client.get(reverse('register'))
        self.assertEqual(resp.status_code, 200)
