from django.test import TestCase, override_settings
from django.urls import reverse
from apps.user.models import User, UserBan, UserActivityLog
import logging

logger = logging.getLogger('user')


class UserModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info('[User APP; User MODEL] Creating test data in DB...')
        cls.user = User.objects.create(
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
    
    def test_username_content(self):
        logger.info('[User APP; User MODEL] Testing "username" field...')
        obj = User.objects.get(id=self.user.id)
        self.assertEqual(obj.username, 'TestUser')


class UserBanModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info('[User APP; UserBan MODEL] Creating test data in DB...')
        cls.user = User.objects.create(
            username='BannedUser',
            password='BannedPassword'
        )
        cls.userban = UserBan.objects.create(
            user=cls.user,
            ip='127.0.0.1',
            reason='Test reason for ban'
        )
    
    def test_ban_reason_content(self):
        logger.info('[User APP; UserBan MODEL] Testing "reason" field...')
        obj = UserBan.objects.get(id=self.userban.id)
        self.assertEqual(obj.reason, 'Test reason for ban')


class UserActivityModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info('[User APP; UserActivityLog MODEL] Creating test data in DB...')
        cls.user = User.objects.create(
            username='ActiveUser',
            password='ActivePassword'
        )
        cls.useractivity = UserActivityLog.objects.create(
            user=cls.user,
            ip='127.0.0.1',
            action='Logged In'
        )
    
    def test_activity_action_content(self):
        logger.info('[User APP; UserActivityLog MODEL] Testing "action" field...')
        obj = UserActivityLog.objects.get(id=self.useractivity.id)
        self.assertEqual(obj.action, 'Logged In')


class AuthPagesTest(TestCase):
    def test_logout_url_by_path(self):
        logger.info('[User APP; Logout PAGE] Testing URL by direct path...')
        resp = self.client.get('/logout.php')  
        self.assertEqual(resp.status_code, 302)
    
    def test_logout_url_by_name(self):
        logger.info('[User APP; Logout PAGE] Testing URL by name...')
        resp = self.client.get(reverse('logout'))
        self.assertEqual(resp.status_code, 302)

    @override_settings(INVITES_ON_REGISTER=False)
    def test_register_url_without_invites(self):
        logger.info('[User APP; Register PAGE] Testing URL (Invites Disabled)...')
        resp = self.client.get(reverse('register'))
        self.assertEqual(resp.status_code, 200)

    @override_settings(INVITES_ON_REGISTER=True)
    def test_register_url_with_invites(self):
        logger.info('[User APP; Register PAGE] Testing URL (Invites Enabled)...')
        resp = self.client.get(reverse('register'))
        self.assertEqual(resp.status_code, 302)