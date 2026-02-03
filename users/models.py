# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('business', 'Business'),
        ('individual', 'Individual'),
        ('freelancer', 'Freelancer'),
    )
    
    # Remove username field, use email instead
    username = None
    email = models.EmailField(unique=True, verbose_name='email address')
    
    # Additional fields
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='individual')
    phone = models.CharField(max_length=20, blank=True)
    email_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    verification_token_expires = models.DateTimeField(default=timezone.now)
    
    # Password reset fields
    reset_token = models.UUIDField(null=True, blank=True, editable=False)
    reset_token_expires = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.email} ({self.get_full_name()})"
    
    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email
    
    def save(self, *args, **kwargs):
        # Set verification token expiry (24 hours)
        if not self.verification_token_expires:
            self.verification_token_expires = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)