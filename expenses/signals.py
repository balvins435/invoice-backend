# expenses/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Expense, RecurringExpense


@receiver(post_save, sender=Expense)
def update_category_budget(sender, instance, created, **kwargs):
    """
    Update category budget tracking
    """
    if instance.category and instance.category.monthly_budget > 0:
        # Budget tracking would be updated in real-time queries
        # This is handled by the model properties
        pass


@receiver(post_save, sender=Expense)
def notify_on_approval(sender, instance, **kwargs):
    """
    Send notification when expense is approved
    """
    # TODO: Implement notification system
    pass


@receiver(pre_save, sender=Expense)
def check_budget_exceeded(sender, instance, **kwargs):
    """
    Check if expense exceeds category budget
    """
    if instance.category and instance.category.monthly_budget > 0:
        spent = instance.category.spent_this_month
        if instance.pk:
            # For updates, subtract old amount
            old_instance = Expense.objects.get(pk=instance.pk)
            spent -= old_instance.total_amount_in_business_currency
        
        # Add new amount
        spent += instance.total_amount_in_business_currency
        
        # Check if exceeds budget
        if spent > instance.category.monthly_budget:
            # Could set a flag or send notification
            instance.notes = f"⚠️ WARNING: This expense exceeds the monthly budget for '{instance.category.name}'. Budget: {instance.category.monthly_budget}, Spent: {spent}\n\n{instance.notes}"
            