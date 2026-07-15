from django import forms


class BroadcastNotificationForm(forms.Form):
    title = forms.CharField(
        label="Заголовок",
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'custom-input'})
    )
    content = forms.CharField(
        label="Текст уведомления",
        widget=forms.Textarea(attrs={'class': 'custom-input', 'rows': 4})
    )
    level = forms.ChoiceField(
        label="Важность",
        choices=[
            ('normal', 'Обычное'),
            ('important', 'Важное'),
            ('critical', 'Критическое')
        ],
        widget=forms.Select(attrs={'class': 'custom-input'})
    )
    user_id = forms.IntegerField(
        label="ID пользователя (Опционально)",
        required=False,
        help_text="Оставь пустым для рассылки ВСЕМ пользователям, или напиши ID для отправки конкретному человеку.",
        widget=forms.NumberInput(
            attrs={
                'class': 'custom-input'}))
