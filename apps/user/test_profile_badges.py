from django.conf import settings
from django.template import Context, Engine
from django.test import SimpleTestCase, override_settings

from .models import User


class ProfileBadgeTests(SimpleTestCase):
    def test_supporter_badge_follows_flag_without_changing_manual_badges(self):
        user = User(badges="team; tester")
        self.assertEqual(user.badge_list, ["team", "tester"])
        user.is_supporter = True
        self.assertEqual(user.badge_list, ["team", "tester", "supporter"])
        user.is_supporter = False
        self.assertEqual(user.badge_list, ["team", "tester"])
        self.assertEqual(user.badges, "team; tester")

    def test_supporter_without_manual_badges(self):
        self.assertEqual(User(is_supporter=True).badge_list, ["supporter"])
        self.assertEqual(User().badge_list, [])

    def test_manual_supporter_is_not_duplicated(self):
        user = User(badges="team; supporter", is_supporter=True)
        self.assertEqual(user.badge_list, ["team", "supporter"])

    @override_settings(STORAGES={
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_profile_renders_supporter_image_and_existing_badges(self):
        engine = Engine(
            dirs=[settings.BASE_DIR / "templates"],
            loaders=[
                ("django.template.loaders.locmem.Loader", {
                    "base.html": "{% block content %}{% endblock %}",
                }),
                "django.template.loaders.filesystem.Loader",
            ],
            libraries={
                "static": "django.templatetags.static",
                "i18n": "django.templatetags.i18n",
            },
        )
        user = User(username="Supporter", badges="team", is_supporter=True)
        html = engine.get_template("profile.html").render(Context({
            "obj": user,
            "badges": user.badge_list,
            "act": "show_collections",
            "profile_collections_count": 0,
        }))
        self.assertIn("img/badges/donates.png", html)
        self.assertIn('alt="supporter"', html)
        self.assertIn("img/badges/team.png", html)
        self.assertNotIn("img/badges/supporter.png", html)
