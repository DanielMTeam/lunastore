import re 
from django.core.exceptions import ValidationError
from .models import BlacklistedUsername

def validate_username_blacklist(value):
    low_value = value.lower()
    blacklist = BlacklistedUsername.objects.all()
    
    for item in blacklist:
        if item.is_regex:
            if re.search(item.word, low_value):
                raise ValidationError(f'Nickname containce ban-pattern: {item.word}')
        elif item.word.lower() in low_value:
            raise ValidationError('Nickname containcs ban-word(-s)')
        