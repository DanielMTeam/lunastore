from rest_framework import serializers
from apps.user.serializers import UserSerializer
from apps.user.models import User

class Serializer(serializers.ModelSerializer):
    users = UserSerializer(many=True, read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'telegram', 'discord', 'description', 'website', 'avatar', 'users']