from django import forms
from .models import User, UserBan
from django.contrib.auth.forms import UserCreationForm
from captcha.fields import CaptchaField
from django.contrib.admin.widgets import FilteredSelectMultiple    
from django.contrib.auth.models import Group

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
    captcha = CaptchaField(label='Введите символы с картинки')
    agree_with_site_rules = forms.BooleanField(label='Я согласен с правилами сайта и осведомлён о последствиях их нарушения', widget=forms.CheckboxInput, required=True)
    agree_with_privacy_policy = forms.BooleanField(label='Я принимаю условия конфиденциальности', widget=forms.CheckboxInput, required=True)
    
    class Meta:
        model = User 
        fields = ['username', 'email']

# поскольку у django нет стандартного метода добавления пользователя в группу, я это сделал сам лмао (●'◡'●)
class add_user_to_group(forms.ModelForm):
    class Meta:
        model = Group
        exclude = []

    # add user field
    users = forms.ModelMultipleChoiceField(
         queryset=User.objects.all(), 
         required=False,
         # use more normal widget lol
         widget=FilteredSelectMultiple('users', False)
    )

    def __init__(self, *args, **kwargs):
        super(add_user_to_group, self).__init__(*args, **kwargs)
        # if it is a existing group
        if self.instance.pk:
            # populate the users field with current users in the group
            self.fields['users'].initial = self.instance.user_set.all()

    def save_m2m(self):
        # add the users to the group
        self.instance.user_set.set(self.cleaned_data['users'])

    def save(self, *args, **kwargs):
        # default save
        instance = super(add_user_to_group, self).save()
        # save many-to-many data
        self.save_m2m()
        return instance
