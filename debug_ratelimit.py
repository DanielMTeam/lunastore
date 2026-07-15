import re
from django.core.cache import cache
from apps.user.models import User
from django.test import Client
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lunastore.settings")
django.setup()

cache.clear()
c = Client()
u, _ = User.objects.get_or_create(
    username='test_debug', is_superuser=True, is_staff=True)
u.set_password('test_debug')
u.save()
c.login(username='test_debug', password='test_debug')

# Make a request
print("Fetching admin page...")
response = c.get('/lunas-office/user/user/')

print("RateLimit Remaining Header:", response.get('X-RateLimit-Remaining'))

html = response.content.decode('utf-8')
links = re.findall(r'(?:src|href)="(/[^"]+)"', html)
print(f"Found {len(links)} internal links.")

for link in links:
    if 'staticfiles' not in link:
        print("Fetching:", link)
        res = c.get(link)
        print(
            "  -> Status:",
            res.status_code,
            "Remaining:",
            res.get('X-RateLimit-Remaining'))
