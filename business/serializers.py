from rest_framework import serializers
from .models import Business


class BusinessSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='name')
    phone = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Business
        fields = [
            'id',
            'business_name',
            'email',
            'phone',
            'address',
            'logo',
            'tax_rate',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
