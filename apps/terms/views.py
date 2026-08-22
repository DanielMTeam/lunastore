from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render
from django.utils import translation

from .models import LegalDocument

# Create your views here.


def help_center(request):
    current_page = request.GET.get("page", "faq")
    context = {
        "current_page": current_page,
    }
    if current_page == "privacy":
        current_lang = translation.get_language()
        doc = LegalDocument.objects.filter(
            doc_type="privacy", language=current_lang
        ).first()
        if not doc:
            doc = LegalDocument.objects.filter(
                doc_type="privacy", language="en"
            ).first()

        context["privacy_doc"] = doc
    if current_page == "rules":
        current_lang = translation.get_language()
        doc = LegalDocument.objects.filter(
            doc_type="rules", language=current_lang
        ).first()
        if not doc:
            doc = LegalDocument.objects.filter(
                doc_type="rules", language="en"
            ).first()

        context["rules_doc"] = doc
    if current_page == "donate":
        current_lang = translation.get_language()
        doc = LegalDocument.objects.filter(
            doc_type="donate", language=current_lang
        ).first()
        if not doc:
            doc = LegalDocument.objects.filter(
                doc_type="donate", language="en"
            ).first()

        context["donate_doc"] = doc
    if current_page == "client":
        return render(request, "client_download.html")

    return render(request, "help_center.html", context)


def other_projects(request):
    return render(request, "other_projects.html")
