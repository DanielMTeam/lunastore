import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import Ticket
from .storage import validate_upload


def eligible_staff():
    permission = Permission.objects.filter(content_type__app_label='support',
                                           codename='process_ticket').first()
    users = get_user_model().objects.filter(is_active=True, is_staff=True)
    if permission is None:
        return users.filter(is_superuser=True)
    view_permission = Permission.objects.get(content_type__app_label='support', codename='view_ticket')
    return users.filter(Q(is_superuser=True) | Q(user_permissions=permission)
                        | Q(groups__permissions=permission)).filter(
        Q(is_superuser=True) | Q(user_permissions=view_permission) | Q(groups__permissions=view_permission)).distinct()


class MessageForm(forms.Form):
    body = forms.CharField(label=_('FORM_SUPPORT_MESSAGE'), max_length=10000,
                           widget=forms.Textarea(attrs={'rows': 7, 'cols': 60}))
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    file1 = forms.FileField(label=_('FORM_SUPPORT_ATTACHMENT_1'), required=False)
    file2 = forms.FileField(label=_('FORM_SUPPORT_ATTACHMENT_2'), required=False)
    file3 = forms.FileField(label=_('FORM_SUPPORT_ATTACHMENT_3'), required=False)

    def clean(self):
        data = super().clean()
        files = {key: self.files.getlist(key) if hasattr(self.files, 'getlist') else [self.files[key]]
                 for key in self.files}
        # Reject extra multipart files instead of silently ignoring them.
        if sum(len(items) for items in files.values()) > 3:
            raise forms.ValidationError(_('ERROR_SUPPORT_ATTACHMENT_COUNT'))
        for key in files:
            if key not in ('file1', 'file2', 'file3') or len(files[key]) != 1:
                raise forms.ValidationError(_('ERROR_SUPPORT_INVALID_ATTACHMENTS'))
        for name in ('file1', 'file2', 'file3'):
            upload = data.get(name)
            if upload:
                try:
                    validate_upload(upload)
                except forms.ValidationError as exc:
                    self.add_error(name, exc)
        return data

    def uploads(self):
        return [self.cleaned_data[name] for name in ('file1', 'file2', 'file3') if self.cleaned_data.get(name)]


class TicketForm(MessageForm):
    subject = forms.CharField(label=_('FORM_SUPPORT_SUBJECT'), max_length=200)
    category = forms.ChoiceField(label=_('FORM_SUPPORT_CATEGORY'), choices=Ticket.Category)
    urgency = forms.ChoiceField(label=_('FORM_SUPPORT_URGENCY'), choices=Ticket.Urgency)
    field_order = ['subject', 'category', 'urgency', 'body', 'file1', 'file2', 'file3', 'request_key']


class StaffTicketForm(forms.Form):
    status = forms.ChoiceField(label=_('FORM_SUPPORT_STATUS'), choices=Ticket.Status)
    priority = forms.TypedChoiceField(label=_('FORM_SUPPORT_PRIORITY'), choices=Ticket.Priority, coerce=int)
    assignee = forms.ModelChoiceField(label=_('FORM_SUPPORT_ASSIGNEE'), queryset=None, required=False, empty_label=_('FORM_SUPPORT_UNASSIGNED'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = eligible_staff()
