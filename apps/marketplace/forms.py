from django import forms
from .models import Application, AppCreateRequests, AppEditRequests
from django.core.validators import FileExtensionValidator
from django.conf import settings
from django.utils.safestring import mark_safe
from captcha.fields import CaptchaField
from django.forms.models import model_to_dict
import os
import uuid
from django.utils.translation import gettext_lazy as _

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def to_python(self, data):
        return data 

    def clean(self, data, initial=None):
        if not data and not self.required:
            return None
        return data

class AppScreenshotForm(forms.ModelForm):

    class Meta:
        model = Application
        fields = [
            'title', 'category', 'description', 'slogan', 'icon', 
            'developer_site', 'is_demo', 'is_under_dmca', 'price'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # check existing screenshots
        if self.instance and self.instance.pk:
            # get screenshots list
            screenshots = self.instance.screenshots or []
            
            for i in range(1, settings.SCREENSHOT_COUNT + 1):
                field_name = f'screenshot_{i}'
                clear_field_name = f'clear_screenshot_{i}'
                list_index = i - 1

                # check if screenshot exists
                if len(screenshots) > list_index and screenshots[list_index]:
                    path = screenshots[list_index]
                    url = f'/staticfiles/{path}'
                    self.fields[field_name].help_text = mark_safe(
                        f'<a href="{url}" target="_blank">'
                        f'<img src="{url}" style="max-width: 150px; max-height: 150px; border: 1px solid #ccc;"/>'
                        f'</a>'
                    )
                else:
                    # if no screenshot, hide clear checkbox
                    self.fields[clear_field_name].widget = forms.HiddenInput()
                    self.fields[clear_field_name].label = ''

    def save(self, commit=True):
        app_instance = super().save(commit=False)
        destination_dir = os.path.join(settings.MEDIA_ROOT, 'ugc', 'screenshots')
        os.makedirs(destination_dir, exist_ok=True)

        # put current screenshots in a list
        current_paths = app_instance.screenshots if isinstance(app_instance.screenshots, list) else []
        # we will build the final paths list here
        final_paths = (current_paths + [None] * settings.SCREENSHOT_COUNT)[:settings.SCREENSHOT_COUNT]

        for i in range(1, settings.SCREENSHOT_COUNT + 1):
            clear_field_name = f'clear_screenshot_{i}'
            upload_field_name = f'screenshot_{i}'
            path_index = i - 1

            # get uploaded file
            uploaded_file = self.cleaned_data.get(upload_field_name)

            # if user wants to clear the screenshot
            if self.cleaned_data.get(clear_field_name):
                if path_to_delete := final_paths[path_index]:
                    full_path = os.path.join(settings.MEDIA_ROOT, path_to_delete)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                final_paths[path_index] = None  # <-- change to None
                continue 

            # upload new file
            if uploaded_file:
                # if there is an old file, delete it
                if old_path := final_paths[path_index]:
                    full_path = os.path.join(settings.MEDIA_ROOT, old_path)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                
                # save new file
                ext = os.path.splitext(uploaded_file.name)[1]
                file_name = f"{uuid.uuid4().hex}{ext}"  # hex to avoid dashes
                file_path = os.path.join(destination_dir, file_name)

                with open(file_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                
                path_for_json = f'ugc/screenshots/{file_name}'
                final_paths[path_index] = path_for_json

        # save final paths back to the instance (in JSONfield)
        # remove trailing None values
        while final_paths and final_paths[-1] is None:
            final_paths.pop()
        
        app_instance.screenshots = final_paths

        if commit:
            app_instance.save()
        
        return app_instance


for i in range(1, settings.SCREENSHOT_COUNT + 1):
    AppScreenshotForm.declared_fields[f'screenshot_{i}'] = forms.ImageField(required=False, label=f'Скриншот {i}')
    AppScreenshotForm.declared_fields[f'clear_screenshot_{i}'] = forms.BooleanField(required=False, label='Удалить')

class AppCreateForm(forms.ModelForm):
    upload_screenshots = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'multiple': True, 
            'id': 'inp_scr', 
            'class': 'action_button',
            'accept': 'image/png, image/jpeg',
            'onchange': 'previewScreenshots(this)' # for js
        }),
        label=_("FORM_SCREENSHOTS"),
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])]
    )
    
    icon = forms.ImageField( 
        widget=forms.FileInput(attrs={
            'id': 'inp_icon', 
            'class': 'action_button', 
            'accept': 'image/png, image/jpeg', 
            'onchange': 'previewIcon(this)'
        }),
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])]
    )
    
    agree_with_site_rules = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'id':'inp_agree'}),
        label=_('FORM_AGREE_RULES')
    )
    
    captcha = CaptchaField(label=_('FORM_CAPTCHA'))
    
    class Meta:
        model = AppCreateRequests
        fields = ['category', 'title', 'slogan', 'icon', 'developer_site', 'description']

        widgets = {
            'category': forms.Select(attrs={
                'class': 'input-text',
                'style': 'width: 100%; margin-bottom: 10px;' 
            }),
            'title': forms.TextInput(attrs={
                'id': 'inp_name', # for js  
                'class': 'input-text',
                'placeholder': _('FORM_APPCREATE_TITLE_EXAMPLE')
            }),
            'slogan': forms.Textarea(attrs={
                'id': 'inp_slogan', # for js
                'class': 'brief_intro',
                'cols': 140,
                'rows': 3,
                'style': 'resize: none;'
            }),
            'icon': forms.FileInput(attrs={
                'id': 'inp_icon', # for js
                'class': 'action_button',
                'accept': 'image/png, image/jpeg',
                'onchange': 'previewIcon(this)'
            }),
            'developer_site': forms.TextInput(attrs={
                'id': 'inp_site', # for js
                'class': 'input-text'
            }),
            'description': forms.Textarea(attrs={
                'id': 'inp_desc', # for js
                'class': 'brief_intro',
                'cols': 100,
                'style': 'height: 150px;'
            }),
        }
    
    def clean_upload_screenshots(self):
        files = self.files.getlist('upload_screenshots')
        limit = getattr(settings, 'SCREENSHOT_COUNT', 3)
        if len(files) > limit:
            raise forms.ValidationError(_("FORM_APPCREATE_MAXIMUM_SCREENSHOTS"))
        return files

    def save(self, commit=True):
        app_instance = super().save(commit=False)
        files = self.files.getlist('upload_screenshots')
        
        if files:
            if app_instance.pk and app_instance.screenshots:
                for old_path in app_instance.screenshots:
                    full_old_path = os.path.join(settings.MEDIA_ROOT, old_path)
                    try:
                        if os.path.isfile(full_old_path):
                            os.remove(full_old_path)
                    except OSError as e:
                        print(f"Error while delete {full_old_path}: {e}")
            destination_dir = os.path.join(settings.MEDIA_ROOT, 'ugc', 'screenshots')
            os.makedirs(destination_dir, exist_ok=True)
            
            final_paths = []
            
            for uploaded_file in files:
                ext = os.path.splitext(uploaded_file.name)[1]
                file_name = f"{uuid.uuid4().hex}{ext}"
                file_path = os.path.join(destination_dir, file_name)
                
                with open(file_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                path_for_json = f'ugc/screenshots/{file_name}'
                final_paths.append(path_for_json)
            
            limit = getattr(settings, 'SCREENSHOT_COUNT', 3)
            app_instance.screenshots = final_paths[:limit]
        
        else:
            if not app_instance.screenshots:
                app_instance.screenshots = []
                
        if commit:
            app_instance.save()
            
        return app_instance
    
class AppEditForm(AppCreateForm):
    class Meta:
        model = AppEditRequests
        fields = ['category', 'title', 'slogan', 'icon', 'developer_site', 'description']
        
    def __init__(self, target_app=None, *args, **kwargs):
        if target_app:
            initial_data = model_to_dict(target_app)
            kwargs['initial'] = initial_data
            self.target_app = target_app
        super().__init__(*args, **kwargs)
        if 'captcha' in self.fields: del self.fields['captcha']
        if 'agree_with_site_rules' in self.fields: del self.fields['agree_with_site_rules']
        
    def save(self, commit=True):
        submission = super().save(commit=False)
        if hasattr(self, 'target_app'):
            submission.target_application = self.target_app
            if not submission.icon and self.target_app.icon:
                submission.icon = self.target_app.icon
            if not submission.screenshots and self.target_app.screenshots:
                submission.screenshots = self.target_app.screenshots
        if commit:
            submission.save()
        return submission