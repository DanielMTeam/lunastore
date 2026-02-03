from rest_framework import viewsets
from apps.user.models import User 
from apps.marketplace.models import Application, Category
from apps.user.serializers import UserSerializer
from apps.marketplace.serializers import ApplicationSerializer, CategorySerializer
from rest_framework.response import Response
from rest_framework.decorators import action
from .exceptions import LunaException
from .constants import ErrorCodes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.contrib.postgres.search import TrigramSimilarity

class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer

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


class MarketplaceViewSet(viewsets.GenericViewSet):
    queryset = Application.objects.filter()
    serializer_class = ApplicationSerializer

    @extend_schema(
        summary="get app info",
        description="returns app info",
        parameters=[
            OpenApiParameter(
                name='id',             
                description='ID of application',
                required=True,         
                type=OpenApiTypes.INT,  
                location=OpenApiParameter.QUERY
            )
        ]
    )
    @action(detail=False, methods=['get'], url_path='getAppInfo')
    def get_app(self, request):
        id = request.query_params.get('id')
        
        if not id:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'ID' field missing",
                status_code=400
            )
        try:
            app = self.get_queryset().get(pk=id)
        except Application.DoesNotExist: 
            raise LunaException(
                code=ErrorCodes.APPLICATION_NOT_FOUND,
                message=f"Application with id {id} was not found",
                status_code=404
            )
        if app.is_under_dmca:
            raise LunaException(
                code=ErrorCodes.APPLICATION_IS_UNDER_DMCA,
                message=f"Application with id {id} is under DMCA strike",
                status_code=403
            )

        serializer = self.get_serializer(app)
        return Response(serializer.data)
    
    @extend_schema(
        summary="get app or apps from name (e.g. search app method)",
        description="returns app, or list of apps",
        parameters=[
            OpenApiParameter(
                name='query',             
                description='query data',
                required=True,         
                type=OpenApiTypes.STR,  
                location=OpenApiParameter.QUERY
            )
        ],
        responses={200: ApplicationSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        query = request.query_params.get('query')
        
        if not query:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'query' field missing",
                status_code=400
            )
        results = Application.objects.annotate(similarity=TrigramSimilarity('title', query) + TrigramSimilarity('description', query) + TrigramSimilarity('slogan', query),).filter(similarity__gt=0.1).order_by('-similarity')

        serializer = ApplicationSerializer(results, many=True)
        enumerated_data = {
            str(index + 1): results
            for index, results in enumerate(serializer.data)
        }
        return Response(enumerated_data)



class CategoryViewSet(viewsets.GenericViewSet):
    queryset = Category.objects.filter()
    serializer_class = CategorySerializer
    
    @extend_schema(
        summary="get app list from category",
        description="returns app list from category",
        parameters=[
            OpenApiParameter(
                name='id',             
                description='ID of category',
                required=True,         
                type=OpenApiTypes.INT,  
                location=OpenApiParameter.QUERY
            )
        ],
        responses={200: ApplicationSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='getAppList')
    def get_app_list(self, request):
        id = request.query_params.get('id')
        
        if not id:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'ID' field missing",
                status_code=400
            )
        try:
            category = self.get_queryset().get(pk=id)
            apps = Application.objects.filter(category=category).order_by('-published')
        except Category.DoesNotExist: 
            raise LunaException(
                code=ErrorCodes.CATEGORY_NOT_FOUND,
                message=f"Category with id {id} was not found",
                status_code=404
            )

        serializer = ApplicationSerializer(apps, many=True)
        enumerated_data = {
            str(index + 1): apps
            for index, apps in enumerate(serializer.data)
        }
        return Response(enumerated_data)