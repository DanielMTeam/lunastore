from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class OIDCModel(OIDCAuthenticationBackend):
    def create_user(self, claims):
        user = super(OIDCModel, self).create_user(claims)
        user.is_staff = True
        user.save()
            
        return user

    
    def update_user(self, user, claims):
        user.first_name = claims.get('given_name', '')
        user.last_name = claims.get('family_name', '')
        user.save()
        return user