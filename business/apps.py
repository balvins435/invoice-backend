from django.apps import AppConfig


class BusinessConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'business'

    # def ready(self):
    #     """Import signals when app is ready"""
    #     try:
    #         import business.signals
    #     except ImportError:
    #         pass
