from django import forms
from .models import User, UserBan, UserActivityLog
from django.contrib.auth.forms import UserCreationForm
from captcha.fields import CaptchaField
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.models import Group
from django.contrib.auth import password_validation
from .middleware import get_client_ip, BlockBannedIP
from django.core.exceptions import ValidationError
from .validators import validate_username_blacklist
import os
from PIL import Image


class UserBanForm(forms.ModelForm):
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
        else:
            self.fields['username'].disabled = False
            self.fields['username'].required = True

    def clean_username(self):
        if self.instance and self.instance.pk:
            return self.instance.user
        
        username = self.cleaned_data['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError('user with this username does not exist')
        if UserBanForm.objects.filter(user=user).exists():
            raise forms.ValidationError('this user is already banned')
        latest_ip = UserActivityLog.objects.filter(user=user).order_by('-timestamp').first()
        if not latest_ip:
            raise forms.ValidationError('cannot ban user without activity log')
        
        self.found_ip = latest_ip.ip
        self.found_user = user
        return user

    def save(self, commit=True):
        if not self.instance.pk:
            user_to_ban = self.found_user
            ip_to_ban = self.found_ip
            
            user_to_ban.is_active = False
            user_to_ban.save()
            self.instance.user = user_to_ban
            self.instance.ip = ip_to_ban
        
        ban_instance = super().save(commit=commit)
        return ban_instance


class UserRegistrationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    def clean(self):
        if self.request:
            ip = get_client_ip(self.request)
            if ip in BlockBannedIP.get_banned_set():
                raise forms.ValidationError('Ваш IP-адрес заблокирован. Вы не можете зарегистрироваться (как и войти, лол)')
    username = forms.CharField(max_length=45, min_length=2)
    email = forms.EmailField(max_length=45)
    captcha = CaptchaField(label='Введите символы с картинки')
    agree_with_site_rules = forms.BooleanField(label='Я согласен с правилами сайта и осведомлён о последствиях их нарушения', widget=forms.CheckboxInput, required=True)
    agree_with_privacy_policy = forms.BooleanField(label='Я принимаю условия конфиденциальности', widget=forms.CheckboxInput, required=True)
        
    class Meta:
        model = User 
        fields = ['username', 'email']
        

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['telegram', 'website', 'description']
            
    username = forms.CharField(
        label="Имя пользователя",
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'input-text', 'readonly': 'readonly'})
    )
    telegram = forms.CharField(
        label="Telegram",
        required=False,
        widget=forms.TextInput(attrs={'class': 'input-text'})
    )
    website = forms.URLField(
        label="Веб-сайт",
        required=False,
        widget=forms.URLInput(attrs={'class': 'input-text'})
    )
    description = forms.CharField(
        label="Описание профиля",
        required=False,
        widget=forms.Textarea(attrs={'class': 'brief_intro', 'cols': 90})
    )


class PasswordChangeForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)
        
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input-text'})
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input-text'}),
        help_text=password_validation.password_validators_help_text_html()
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input-text'})
    )
    
    def clean_password(self):
        current_password = self.cleaned_data.get('current_password')
        if not self.user.check_password(current_password):
            raise ValidationError("Текущий пароль неверен.")
        return current_password
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_new_password = cleaned_data.get("confirm_new_password")

        if new_password and confirm_new_password:
            if new_password != confirm_new_password:
                raise ValidationError("Новые пароли не совпадают.")
            password_validation.validate_password(new_password, self.user)
        return cleaned_data

    
class AvatarUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['avatar']
    
    avatar = forms.ImageField(
        label="Выберите файл",
        widget=forms.FileInput(attrs={'class': 'action_button', 'id': 'file-upload'}), # Или кастомный стиль кнопки
        help_text="Рекомендуемый размер: 64x64. Форматы: PNG, JPG. Макс: 2 МБ."
    )
    
    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar:
            limit_mb = 2 # in megabytes
            if avatar.size > limit_mb * 1024 * 1024:
                raise ValidationError(f"Максимальный размер файла: {limit_mb} МБ.")

            ext = os.path.splitext(avatar.name)[1].lower()
            valid_extensions = ['.jpg', '.jpeg', '.png']
            if ext not in valid_extensions:
                raise ValidationError("Допустимые форматы: .JPG, .PNG")
            
            image = Image.open(avatar)
            if image.width > 64 or image.height > 64: 
                raise ValidationError("Изображение слишком большое по пикселям.")
                
        return avatar


class DevStatusForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['mail', 'github', 'about_you', 'why_you_choose_us', 'username'] 

    username = forms.CharField(
        label="Имя пользователя",
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'input-text', 'readonly': 'readonly'})
    )
    
    mail = forms.EmailField(
        label="Ваш Email",
        max_length=128,
        widget=forms.EmailInput(attrs={'class': 'input-text'}),
        help_text="Мы обязательно свяжемся с Вами. По крайней мере постараемся."
    )
    
    github = forms.URLField(
        label="Ссылка на ваш GitHub",
        max_length=128,
        widget=forms.URLInput(attrs={'class': 'input-text'}),
        help_text="А почему нет? Мы хотим посмотреть на ваши красивые разработки :3"
    )
    
    about_you = forms.CharField(
        label="Расскажите о себе (до 1000 символов)",
        max_length=1000,
        widget=forms.Textarea(attrs={'class': 'brief_intro', 'cols': 90})
    )
    
    why_you_choose_us = forms.CharField(
        label="Почему Вы решили выбрать нас? (до 250 символов)",
        max_length=250,
        widget=forms.Textarea(attrs={'class': 'brief_intro', 'cols': 90})
    )
    
    agree_with_site_rules = forms.BooleanField(label='Я согласен с правилами сайта и осведомлён о последствиях их нарушения', widget=forms.CheckboxInput, required=True)
    agree_with_privacy_policy = forms.BooleanField(label='Я принимаю условия конфиденциальности', widget=forms.CheckboxInput, required=True)
    
    captcha = CaptchaField(label='Введите символы с картинки')


# поскольку у django нет стандартного метода добавления пользователя в группу, я это сделал сам лмао (●'◡'●)
class AddToGroupForm(forms.ModelForm):
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
        super(AddToGroupForm, self).__init__(*args, **kwargs)
        # if it is a existing group
        if self.instance.pk:
            # populate the users field with current users in the group
            self.fields['users'].initial = self.instance.user_set.all()

    def save_m2m(self):
        # add the users to the group
        self.instance.user_set.set(self.cleaned_data['users'])

    def save(self, *args, **kwargs):
        # default save
        instance = super(AddToGroupForm, self).save()
        # save many-to-many data
        self.save_m2m()
        return instance
