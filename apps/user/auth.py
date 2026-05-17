from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth.models import Group


class OIDCModel(OIDCAuthenticationBackend):
    def create_user(self, claims):
        # creates a user using the base class
        user = super(OIDCModel, self).create_user(claims)

        # sets staff status (to allow access to admin panel in general)
        user.is_staff = True

        # sets name and surname (optional)
        user.first_name = claims.get('given_name', '')
        user.last_name = claims.get('family_name', '')

        # saves the user before adding to group
        user.save()

        # adds user to moderator group (if it exists)
        try:
            moderator_group = Group.objects.get(name='Модераторы')
            user.groups.add(moderator_group)
        except Group.DoesNotExist:
            # protects against failure: if the moderator group doesn't exist,
            # the code will not break the authentication process.
            print("warning: moderator group not found in database")

        return user


    def update_user(self, user, claims):
        user.first_name = claims.get('given_name', '')
        user.last_name = claims.get('family_name', '')
        user.save()

        try:
            moderator_group = Group.objects.get(name='Модераторы')
            user.groups.add(moderator_group)
        except Group.DoesNotExist:
            pass

        return user
