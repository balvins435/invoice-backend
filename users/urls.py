from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView
)
from .views import RegisterView, MeView, LogoutView, UpdateProfileView, ChangePasswordView

urlpatterns = [
    path('register/', RegisterView.as_view()),
    path('login/', TokenObtainPairView.as_view()),
    path('refresh/', TokenRefreshView.as_view()),
    path('me/', MeView.as_view()),
    path('me/update-profile/', UpdateProfileView.as_view()),
    path('me/change-password/', ChangePasswordView.as_view()),
    path('logout/', LogoutView.as_view()),
]
