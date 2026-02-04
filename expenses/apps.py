from django.apps import AppConfig


class ExpensesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'expenses'

    def ready(self):
        """Import signals when app is ready"""
        try:
            import expenses.signals
        except ImportError:
            pass
