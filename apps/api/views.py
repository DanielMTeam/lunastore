from rest_framework import viewsets
from apps.user.models import User 
from apps.marketplace.models import Application, Category, Distribution
from apps.marketplace.serializers import (
    ApplicationSerializer,
    CategorySerializer,
    DistributionSerializer,
)
from apps.user.models import User
from apps.user.serializers import UserSerializer

from .constants import ErrorCodes
from .exceptions import LunaException


class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer

    @extend_schema(
        summary="get user profile info",
        description="returns user info",
        parameters=[
            OpenApiParameter(
                name="id",
                description="User ID",
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="getProfileInfo")
    def get_profile(self, request):
        id = request.query_params.get("id")

        if not id:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'ID' field missing",
                status_code=400,
            )

        try:
            user = self.get_queryset().get(pk=id)
        except User.DoesNotExist:
            raise LunaException(
                code=ErrorCodes.USER_NOT_FOUND,
                message=f"User with id {id} was not found",
                status_code=404,
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
                name="id",
                description="Application ID",
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="getAppInfo")
    def get_app(self, request):
        id = request.query_params.get("id")

        if not id:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'ID' field missing",
                status_code=400,
            )
        try:
            app = self.get_queryset().get(pk=id)
        except Application.DoesNotExist:
            raise LunaException(
                code=ErrorCodes.APPLICATION_NOT_FOUND,
                message=f"Application with id {id} was not found",
                status_code=404,
            )
        if app.is_under_dmca:
            raise LunaException(
                code=ErrorCodes.APPLICATION_IS_UNDER_DMCA,
                message=f"Application (id: {id}) unavailable because his creators/uploaders received a DMCA strike",
                status_code=403,
            )

        serializer = self.get_serializer(app)
        return Response(serializer.data)

    @extend_schema(
        summary="get app or apps from name (e.g. search app method)",
        description="returns app, or list of apps",
        parameters=[
            OpenApiParameter(
                name="query",
                description="query data",
                required=True,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            )
        ],
        responses={200: ApplicationSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        query = request.query_params.get("query")

        if not query:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'query' field missing",
                status_code=400,
            )
        results = (
            Application.objects.annotate(
                similarity=TrigramSimilarity("title", query)
                + TrigramSimilarity("description", query)
                + TrigramSimilarity("slogan", query),
            )
            .filter(similarity__gt=0.1)
            .order_by("-similarity")
        )

        serializer = ApplicationSerializer(results, many=True)
        enumerated_data = {
            str(index + 1): results for index, results in enumerate(serializer.data)
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
                name="id",
                description="Category ID",
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            )
        ],
        responses={200: ApplicationSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="getAppList")
    def get_app_list(self, request):
        id = request.query_params.get("id")

        if not id:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'ID' field missing",
                status_code=400,
            )
        try:
            category = self.get_queryset().get(pk=id)
            apps = Application.objects.filter(category=category).order_by("-published")
        except Category.DoesNotExist:
            raise LunaException(
                code=ErrorCodes.CATEGORY_NOT_FOUND,
                message=f"Category with id {id} was not found",
                status_code=404,
            )

        serializer = ApplicationSerializer(apps, many=True)
        enumerated_data = {
            str(index + 1): apps for index, apps in enumerate(serializer.data)
        }
        return Response(enumerated_data)


class ServiceViewSet(viewsets.GenericViewSet):
    @extend_schema(
        summary="check API status",
        description="API method like 'heartbeat' type; returns current time, status and version",
        responses={
            200: inline_serializer(
                name="HeartbeatResponse",
                fields={
                    "status": serializers.CharField(),
                    "timestamp": serializers.DateTimeField(),
                    "version": serializers.CharField(),
                },
            )
        },
    )
    @action(detail=False, methods=["get"], url_path="heartbeat")
    def heartbeat(self, request):
        return Response(
            {"status": "ok", "timestamp": datetime.now(), "version": settings.VERSION}
        )

    @extend_schema(
        summary="returns list of LunaStore developers",
        description="returns list of LunaStore developers",
    )
    @action(detail=False, methods=["get"], url_path="developersList")
    def developers(self, request):
        return Response(
            {
                "creator": "Daniel Myslivets",
                "backend": "fayzetwin, synzr, filldor, zazios",
                "frontend": "Daniel Myslivets",
                "system-administration": "eversiege, thefoxmilya, rotama",
                "design": "chelka0",
                "special_thanks": "MondySpartan (logo), nocha3 (native client of LunaStore for Windows XP)",
            }
        )

    @extend_schema(
        summary="returns one cool thing",
        description="returns one cool thing",
    )
    @action(detail=False, methods=["get"], url_path="kunyakin")
    def kunyakin(self, request):
        return Response({"answer": "влад кунякин пробудил шаринган"})


class DistributionViewSet(viewsets.GenericViewSet):
    queryset = Distribution.objects.filter()
    serializer_class = DistributionSerializer

    @extend_schema(
        summary="get list of distributions from app",
        description="returns list of distributions from app",
        parameters=[
            OpenApiParameter(
                name="id",
                description="Application ID",
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            )
        ],
        responses={200: DistributionSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="getDistributionsList")
    def get_distributions_list(self, request):
        id = request.query_params.get("id")

        if not id:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'ID' field missing",
                status_code=400,
            )
        try:
            app = Application.objects.get(pk=id)
            distributions = self.get_queryset().filter(app=app)
        except Application.DoesNotExist:
            raise LunaException(
                code=ErrorCodes.APPLICATION_NOT_FOUND,
                message=f"Application with id {id} was not found",
                status_code=404,
            )

        serializer = DistributionSerializer(distributions, many=True)
        enumerated_data = {
            str(index + 1): distributions
            for index, distributions in enumerate(serializer.data)
        }
        return Response(enumerated_data)
