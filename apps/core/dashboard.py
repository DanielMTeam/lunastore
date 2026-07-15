from apps.marketplace.models import AppCreateRequests, Application, AppEditRequests, AppReportRequests, ProblemReportRequests
from apps.user.models import User
from django.utils import timezone

# Why push away me, push away it could,
# Push away life, oh so
# Why push away me, push away it could,
# Push away life, oh so
# Why push away me
# Push away it could, push away life
#
# tr/st, shoom


def callback(request, context):
    context.update({
        # marketplace statistics
        "new_apps": AppCreateRequests.objects.filter(status="pending").count(),
        "total_apps": Application.objects.count(),

        # user statistics
        "total_users": User.objects.count(),
        "new_users_today": User.objects.filter(date_joined__gte=timezone.now().date()).count(),

        # requests
        "reports": AppReportRequests.objects.filter(status="pending").count(),
        "problem_reports": ProblemReportRequests.objects.filter(status="pending").count(),
        "edits_apps": AppEditRequests.objects.filter(status="pending").count(),
        "create_apps": AppCreateRequests.objects.filter(status="pending").count(),
    })
    return context
