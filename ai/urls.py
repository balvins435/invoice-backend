from django.urls import path
from .views import generate_invoice

urlpatterns = [
    path('generate-invoice/', generate_invoice),
]