from rest_framework import viewsets, permissions
from .models import Expense, ExpenseCategory
from .serializers import ExpenseSerializer, ExpenseCategorySerializer
from business.models import Business
from rest_framework.exceptions import ValidationError
from django.db.models import Q


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

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(expense_date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(expense_date__lte=date_to)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        business_id = self.request.data.get('business_id') or self.request.data.get('business')
        if not business_id:
            raise ValidationError({'business_id': 'This field is required.'})

        business = Business.objects.filter(id=business_id, owner=self.request.user).first()
        if not business:
            raise ValidationError({'business_id': 'Invalid business for this user.'})

        serializer.save(user=self.request.user, business=business)
