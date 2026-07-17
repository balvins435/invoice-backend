from rest_framework import serializers
from .models import Business


class BusinessSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='name')
    display_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Business
        fields = [
            'id',
            'business_name',
            'display_name',
            'slug',
            'email',
            'phone',
            'address',
            'logo',
            'logo_shape',
            'tax_rate',
            'default_invoice_template',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
