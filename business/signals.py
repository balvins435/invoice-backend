# # business/signals.py
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.contrib.auth import get_user_model
# from .models import BusinessProfile, BusinessSettings

# User = get_user_model()

# @receiver(post_save, sender=User)
# def create_business_profile_for_new_user(sender, instance, created, **kwargs):
#     """Automatically create empty business profile for new users"""
#     if created and instance.user_type in ['business', 'freelancer']:
#         BusinessProfile.objects.create(
#             user=instance,
#             business_name=f"{instance.get_full_name()}'s Business",
#             business_email=instance.email
#         )

# @receiver(post_save, sender=BusinessProfile)
# def create_business_settings(sender, instance, created, **kwargs):
#     """Automatically create default settings for new business profile"""
#     if created:
#         BusinessSettings.objects.create(business=instance)