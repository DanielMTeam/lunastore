from rest_framework import serializers
from .models import Application

class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['title','description','slogan','icon','price','screenshots','developer_site','is_demo']