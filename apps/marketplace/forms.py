from django import forms
from .models import Application, User, UserBan
from django.conf import settings
from django.utils.safestring import mark_safe
import os
import uuid



class app_screenshot(forms.ModelForm):
    screenshot1 = forms.ImageField(required=False, label='Скриншот 1')
    screenshot2 = forms.ImageField(required=False, label='Скриншот 2')
    screenshot3 = forms.ImageField(required=False, label='Скриншот 3')

    clear_screenshot1 = forms.BooleanField(required=False, label='Удалить скриншот 1')
    clear_screenshot2 = forms.BooleanField(required=False, label='Удалить скриншот 2')
    clear_screenshot3 = forms.BooleanField(required=False, label='Удалить скриншот 3')

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
            
            for i in range(1, 4):
                field_name = f'screenshot{i}'
                clear_field_name = f'clear_screenshot{i}'
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
        destination_dir = os.path.join(settings.BASE_DIR, 'staticfiles', 'ugc', 'screenshots')
        os.makedirs(destination_dir, exist_ok=True)

        # put current screenshots in a list
        current_paths = app_instance.screenshots if isinstance(app_instance.screenshots, list) else []
        # we will build the final paths list here
        final_paths = (current_paths + [None] * 3)[:3]

        for i in range(1, 4):
            clear_field_name = f'clear_screenshot{i}'
            upload_field_name = f'screenshot{i}'
            path_index = i - 1

            # get uploaded file
            uploaded_file = self.cleaned_data.get(upload_field_name)

            # if user wants to clear the screenshot
            if self.cleaned_data.get(clear_field_name):
                if path_to_delete := final_paths[path_index]:
                    full_path = os.path.join(settings.BASE_DIR, 'staticfiles', path_to_delete)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                final_paths[path_index] = None # <-- change to None
                continue 

            # upload new file
            if uploaded_file:
                # if there is an old file, delete it
                if old_path := final_paths[path_index]:
                    full_path = os.path.join(settings.BASE_DIR, 'staticfiles', old_path)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                
                # save new file
                ext = os.path.splitext(uploaded_file.name)[1]
                file_name = f"{uuid.uuid4().hex}{ext}" # hex to avoid dashes
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

class user_ban(forms.ModelForm):
    username = forms.CharField(label='Юзернейм', max_length=150)

    class Meta:
        model = UserBan
        fields = ['reason'] 

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.initial['username'] = self.instance.user.username
            self.fields['username'].disabled = True
            self.fields['username'].required = False

    def clean_username(self):
        username = self.cleaned_data.get('username')
        
        if not username:
             return None 
        
        try:
            user = User.objects.get(username=username)
            return user 
        except User.DoesNotExist:
            raise forms.ValidationError("Пользователь с таким юзернеймом не найден.")

    def save(self, commit=True):
        if not self.instance.pk:
            self.instance.user = self.cleaned_data['username']
        
        return super().save(commit=commit)