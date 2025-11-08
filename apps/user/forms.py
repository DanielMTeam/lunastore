from django import forms
from .models import User, UserBan
from django.utils.safestring import mark_safe
from django.contrib.auth.forms import UserCreationForm


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
    
class user_registration(UserCreationForm):
    username = forms.CharField(max_length=45, min_length=2)
    email = forms.EmailField(max_length=45)
    agree_with_site_rules = forms.BooleanField(label='Я согласен с правилами сайта и осведомлён о последствиях их нарушения', widget=forms.CheckboxInput, required=True)
    agree_with_privacy_policy = forms.BooleanField(label='Я принимаю условия конфиденциальности', widget=forms.CheckboxInput, required=True)
    
    class Meta:
        model = User 
        fields = ['username', 'email']
        