# users/serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from .models import User
from django.utils import timezone
import uuid

class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration
    """
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        style={'input_type': 'password'},
        validators=[validate_password]
    )
    password2 = serializers.CharField(
        write_only=True, 
        required=True,
        style={'input_type': 'password'}
    )
    user_type = serializers.ChoiceField(
        choices=User.USER_TYPE_CHOICES, 
        default='individual'
    )
    
    class Meta:
        model = User
        fields = (
            'id', 
            'email', 
            'first_name', 
            'last_name', 
            'phone', 
            'user_type', 
            'password', 
            'password2', 
            'created_at'
        )
        extra_kwargs = {
            'first_name': {'required': True, 'allow_blank': False},
            'last_name': {'required': True, 'allow_blank': False},
            'email': {'required': True},
        }
        read_only_fields = ('id', 'created_at')
    
    def validate_email(self, value):
        """
        Check if email already exists
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()  # Store emails in lowercase
    
    def validate(self, attrs):
        """
        Validate that both passwords match
        """
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match.",
                "password2": "Password fields didn't match."
            })
        
        # Check password strength
        try:
            validate_password(attrs['password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
        
        return attrs
    
    def create(self, validated_data):
        """
        Create and return a new user instance
        """
        validated_data.pop('password2')
        
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone=validated_data.get('phone', ''),
            user_type=validated_data.get('user_type', 'individual')
        )
        return user

class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login
    """
    email = serializers.EmailField(
        required=True,
        help_text="User's email address"
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="User's password"
    )
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if not email or not password:
            raise serializers.ValidationError(
                "Both email and password are required."
            )
        
        # Normalize email to lowercase
        attrs['email'] = email.lower()
        
        return attrs

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile (read/update)
    """
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = (
            'id', 
            'email', 
            'first_name', 
            'last_name',
            'full_name',
            'phone', 
            'user_type', 
            'email_verified', 
            'created_at', 
            'updated_at'
        )
        read_only_fields = (
            'id', 
            'email', 
            'email_verified', 
            'created_at', 
            'updated_at'
        )
    
    def get_full_name(self, obj):
        return obj.get_full_name()

class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing password
    """
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Current password"
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        validators=[validate_password],
        help_text="New password (must meet security requirements)"
    )
    new_password2 = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Confirm new password"
    )
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(
                "Your current password is incorrect."
            )
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({
                "new_password": "New password fields didn't match.",
                "new_password2": "New password fields didn't match."
            })
        
        # Check if new password is same as old password
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({
                "new_password": "New password cannot be the same as your current password."
            })
        
        return attrs

class ResetPasswordRequestSerializer(serializers.Serializer):
    """
    Serializer for requesting password reset
    """
    email = serializers.EmailField(
        required=True,
        help_text="Email address associated with the account"
    )
    
    def validate_email(self, value):
        # Normalize email
        return value.lower()

class ResetPasswordConfirmSerializer(serializers.Serializer):
    """
    Serializer for confirming password reset
    """
    token = serializers.UUIDField(
        required=True,
        help_text="Password reset token received via email"
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        validators=[validate_password],
        help_text="New password"
    )
    new_password2 = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Confirm new password"
    )
    
    def validate_token(self, value):
        """
        Validate that token exists and is not expired
        """
        try:
            user = User.objects.get(reset_token=value)
            
            # Check if token has expired
            if user.reset_token_expires and user.reset_token_expires < timezone.now():
                raise serializers.ValidationError(
                    "Reset token has expired. Please request a new one."
                )
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid reset token.")
        
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({
                "new_password": "Password fields didn't match.",
                "new_password2": "Password fields didn't match."
            })
        return attrs

class VerifyEmailSerializer(serializers.Serializer):
    """
    Serializer for email verification
    """
    token = serializers.UUIDField(
        required=True,
        help_text="Email verification token received via email"
    )
    
    def validate_token(self, value):
        """
        Validate that token exists and is not expired
        """
        try:
            user = User.objects.get(verification_token=value)
            
            # Check if token has expired
            if user.verification_token_expires and user.verification_token_expires < timezone.now():
                raise serializers.ValidationError(
                    "Verification token has expired. Please request a new verification email."
                )
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid verification token.")
        
        return value

class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile (without changing email)
    """
    class Meta:
        model = User
        fields = (
            'first_name',
            'last_name',
            'phone',
            'user_type'
        )
    
    def validate_phone(self, value):
        """
        Basic phone validation (optional)
        """
        if value and not value.replace('+', '').replace(' ', '').replace('-', '').isdigit():
            raise serializers.ValidationError(
                "Phone number should contain only digits, spaces, plus, and hyphen characters."
            )
        return value

class MinimalUserSerializer(serializers.ModelSerializer):
    """
    Serializer for minimal user information (used in other serializers)
    """
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'full_name')
        read_only_fields = fields
    
    def get_full_name(self, obj):
        return obj.get_full_name()

class TokenSerializer(serializers.Serializer):
    """
    Serializer for JWT tokens
    """
    refresh = serializers.CharField()
    access = serializers.CharField()
    
class LoginResponseSerializer(serializers.Serializer):
    """
    Serializer for login response
    """
    user = UserProfileSerializer()
    refresh = serializers.CharField()
    access = serializers.CharField()
    message = serializers.CharField(default="Login successful")

class RegistrationResponseSerializer(serializers.Serializer):
    """
    Serializer for registration response
    """
    user = UserProfileSerializer()
    refresh = serializers.CharField()
    access = serializers.CharField()
    message = serializers.CharField(default="Registration successful")