from rest_framework import viewsets
from apps.user.models import User 
from .serializers import Serializer
from rest_framework.response import Response
from rest_framework.decorators import action
from .exceptions import LunaException
from .constants import ErrorCodes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = Serializer

    @extend_schema(
        summary="get user profile info",
        description="returns user info",
        parameters=[
            OpenApiParameter(
                name='id',             
                description='ID of user',
                required=True,         
                type=OpenApiTypes.INT,  
                location=OpenApiParameter.QUERY
            )
        ]
    )
    @action(detail=False, methods=['get'], url_path='getProfileInfo')
    def get_profile(self, request):
        id = request.query_params.get('id')
        
        if not id:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'ID' field missing",
                status_code=400
            )
            
        try:
            user = self.get_queryset().get(pk=id)
        except User.DoesNotExist: 
            raise LunaException(
                code=ErrorCodes.USER_NOT_FOUND,
                message=f"User with id {id} was not found",
                status_code=404
            )

        serializer = self.get_serializer(user)
        return Response(serializer.data)