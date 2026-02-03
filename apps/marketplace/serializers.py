from rest_framework import serializers
from .models import Application, Category, Distribution

class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['id','title','description','slogan','icon','price','screenshots','developer_site','is_demo']
        

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id','name','description']
        

class DistributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distribution
        fields = ['id','app','version','file','url','changelog','published']