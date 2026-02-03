# users/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import uuid

from .models import User
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer,
    ChangePasswordSerializer, ResetPasswordRequestSerializer,
    ResetPasswordConfirmSerializer, VerifyEmailSerializer
)

class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Send verification email
        verification_link = f"{settings.FRONTEND_URL}/verify-email/{user.verification_token}"
        subject = 'Verify Your Email Address'
        message = render_to_string('emails/verification_email.html', {
            'user': user,
            'verification_link': verification_link,
        })
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], html_message=message)
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserProfileSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'Registration successful. Please check your email for verification.'
        }, status=status.HTTP_201_CREATED)

class UserLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            user = authenticate(request, email=email, password=password)
            
            if user:
                if not user.email_verified:
                    return Response({
                        'error': 'Please verify your email address before logging in.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    'user': UserProfileSerializer(user).data,
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'message': 'Login successful'
                })
            
            return Response({
                'error': 'Invalid email or password'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user

class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = self.get_object()
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response({
            'message': 'Password changed successfully'
        })

class ResetPasswordRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            user.reset_token = uuid.uuid4()
            user.reset_token_expires = timezone.now() + timezone.timedelta(hours=1)
            user.save()
            
            # Send reset email
            reset_link = f"{settings.FRONTEND_URL}/reset-password/{user.reset_token}"
            subject = 'Reset Your Password'
            message = render_to_string('emails/reset_password_email.html', {
                'user': user,
                'reset_link': reset_link,
            })
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], html_message=message)
            
        except User.DoesNotExist:
            # Don't reveal that user doesn't exist for security
            pass
        
        return Response({
            'message': 'If an account exists with this email, you will receive a password reset link.'
        })

class ResetPasswordConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        user = User.objects.get(reset_token=token)
        user.set_password(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        user.save()
        
        return Response({
            'message': 'Password has been reset successfully.'
        })

class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        user = User.objects.get(verification_token=token)
        
        user.email_verified = True
        user.verification_token = None
        user.verification_token_expires = None
        user.save()
        
        return Response({
            'message': 'Email verified successfully. You can now log in.'
        })

class ResendVerificationEmailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        if user.email_verified:
            return Response({
                'message': 'Email is already verified.'
            })
        
        # Generate new verification token
        user.verification_token = uuid.uuid4()
        user.verification_token_expires = timezone.now() + timezone.timedelta(hours=24)
        user.save()
        
        # Send verification email
        verification_link = f"{settings.FRONTEND_URL}/verify-email/{user.verification_token}"
        subject = 'Verify Your Email Address'
        message = render_to_string('emails/verification_email.html', {
            'user': user,
            'verification_link': verification_link,
        })
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], html_message=message)
        
        return Response({
            'message': 'Verification email sent successfully.'
        })

class UserLogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)