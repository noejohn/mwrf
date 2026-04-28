from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from .models import TblUsers


class TblUsersJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user_id = validated_token.get("user_id")
        if not user_id:
            raise AuthenticationFailed("Token contained no recognizable user identification.")
        try:
            user = TblUsers.objects.get(userid=user_id)
        except TblUsers.DoesNotExist as exc:
            raise AuthenticationFailed("User not found.") from exc

        if (user.userstatus or "").upper() != "ACTIVE":
            raise AuthenticationFailed("User is inactive.")

        # DRF permission checks expect these auth flags.
        setattr(user, "is_authenticated", True)
        setattr(user, "is_anonymous", False)
        return user

