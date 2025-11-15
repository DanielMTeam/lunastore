from django import forms
from .models import User, UserBanForm, UserActivityLog
from django.contrib.auth.forms import UserCreationForm
from captcha.fields import CaptchaField
from django.contrib.admin.widgets import FilteredSelectMultiple    
from django.contrib.auth.models import Group
from .middleware import get_client_ip, BlockBannedIP
class UserBanForm(forms.ModelForm):
    username = forms.CharField(label='Юзернейм', max_length=150)

    class Meta:
        model = UserBanForm
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
        cleaned_data = super().clean()
        
        if self.request:
            ip = get_client_ip(self.request)
            if ip in BlockBannedIP._banned_ips:
                raise forms.ValidationError('Ваш IP-адрес заблокирован. Вы не можете зарегистрироваться (как и войти, лол)')
    
    username = forms.CharField(max_length=45, min_length=2)
    email = forms.EmailField(max_length=45)
    captcha = CaptchaField(label='Введите символы с картинки')
    agree_with_site_rules = forms.BooleanField(label='Я согласен с правилами сайта и осведомлён о последствиях их нарушения', widget=forms.CheckboxInput, required=True)
    agree_with_privacy_policy = forms.BooleanField(label='Я принимаю условия конфиденциальности', widget=forms.CheckboxInput, required=True)
    
    
    class Meta:
        model = User 
        fields = ['username', 'email']
        
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
