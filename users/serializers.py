from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    full_name = serializers.CharField(read_only=True)
    tokens = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 'password', 'created_at', 'tokens']

    def create(self, validated_data):
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        full_name = f"{first_name} {last_name}".strip()
        return User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=full_name
        )

    def get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'created_at']
