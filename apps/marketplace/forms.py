from django import forms
from .models import Application
from django.core.files.storage import default_storage
from django.conf import settings
import os

class app_screenshot(forms.ModelForm):
    screenshot1 = forms.ImageField(required=False)
    screenshot2 = forms.ImageField(required=False)
    screenshot3 = forms.ImageField(required=False)

    class Meta:
        model = Application
        fields = '__all__'
    
    def save(self, commit=True):
        app_instance = super().save(commit=False)
        destination_dir = os.path.join(settings.BASE_DIR, 'staticfiles', 'ugc', 'screenshots')
        os.makedirs(destination_dir, exist_ok=True)



        screenshot_paths = []

        for i in range (1,4):
            field_name = f'screenshot{i}'
            uploaded_file = self.cleaned_data.get(field_name)

            if uploaded_file:
                file_path = os.path.join(destination_dir, uploaded_file.name)
                with open(file_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                    path_for_json = f'ugc/screenshots/{uploaded_file.name}'
                    screenshot_paths.append(path_for_json)
            if screenshot_paths:
                app_instance.screenshots = screenshot_paths

            if commit:
                app_instance.save()

            return app_instance