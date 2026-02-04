from django.apps import AppConfig


class InvoiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'invoice'

    def ready(self):
        """Import signals when app is ready"""
        try:
            import invoices.signals
        except ImportError:
            pass
