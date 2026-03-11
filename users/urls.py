from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView
)
from .views import (
    RegisterView,
    MeView,
    LogoutView,
    UpdateProfileView,
    ChangePasswordView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
)
from .social_views import SocialAuthRedirectView, SocialAuthErrorView, SocialProvidersView

urlpatterns = [
    path('register/', RegisterView.as_view()),
    path('login/', TokenObtainPairView.as_view()),
    path('refresh/', TokenRefreshView.as_view()),
    path('me/', MeView.as_view()),
    path('me/update-profile/', UpdateProfileView.as_view()),
    path('me/change-password/', ChangePasswordView.as_view()),
    path('logout/', LogoutView.as_view()),
    path('password-reset/', PasswordResetRequestView.as_view()),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view()),
    path('social/redirect/', SocialAuthRedirectView.as_view()),
    path('social/error/', SocialAuthErrorView.as_view()),
    path('social/providers/', SocialProvidersView.as_view()),
]
