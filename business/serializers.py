from rest_framework import serializers
from .models import Business


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'address',
            'logo',
            'tax_rate',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
