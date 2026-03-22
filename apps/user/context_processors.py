from django.conf import settings


def motd_processor(request):
    return {"motds": getattr(settings, "MOTD_LIST", ["Windows XP Professional"])}
