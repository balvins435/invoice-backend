from rest_framework import viewsets, permissions
from .models import Expense, ExpenseCategory
from .serializers import ExpenseSerializer, ExpenseCategorySerializer
from business.models import Business
from rest_framework.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Expense.objects.filter(
            business__owner=self.request.user
        )

        business_id = self.request.query_params.get('business') or self.request.query_params.get('business_id')
        if business_id:
            queryset = queryset.filter(business_id=business_id)

        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__name=category.lower())

        tax_deductible = self.request.query_params.get('tax_deductible')
        if tax_deductible in ['true', 'false']:
            queryset = queryset.filter(tax_deductible=(tax_deductible == 'true'))

        date_from = (
            self.request.query_params.get('date_from')
            or self.request.query_params.get('start_date')
        )
        if date_from:
            queryset = queryset.filter(expense_date__gte=date_from)

        date_to = (
            self.request.query_params.get('date_to')
            or self.request.query_params.get('end_date')
        )
        if date_to:
            queryset = queryset.filter(expense_date__lte=date_to)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        updated_after_raw = self.request.query_params.get("updated_after")
        if updated_after_raw:
            updated_after = parse_datetime(updated_after_raw)
            if updated_after is None:
                raise ValidationError({"updated_after": "Invalid datetime format. Use ISO-8601."})
            if timezone.is_naive(updated_after):
                updated_after = timezone.make_aware(updated_after, timezone.get_current_timezone())
            queryset = queryset.filter(updated_at__gt=updated_after)

        return queryset

    def perform_create(self, serializer):
        business_id = self.request.data.get('business_id') or self.request.data.get('business')
        if not business_id:
            raise ValidationError({'business_id': 'This field is required.'})

        business = Business.objects.filter(id=business_id, owner=self.request.user).first()
        if not business:
            raise ValidationError({'business_id': 'Invalid business for this user.'})

        serializer.save(user=self.request.user, business=business)
