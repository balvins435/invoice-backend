from rest_framework import viewsets, permissions
from .models import Expense, ExpenseCategory
from .serializers import ExpenseSerializer, ExpenseCategorySerializer
from rest_framework.exceptions import ValidationError
from .selectors import expenses_for_user, filter_expenses
from .application.services import resolve_owned_business


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return filter_expenses(expenses_for_user(self.request.user), self.request.query_params)

    def perform_create(self, serializer):
        business_id = self.request.data.get('business_id') or self.request.data.get('business')
        business = resolve_owned_business(business_id=business_id, user=self.request.user)
        serializer.save(user=self.request.user, business=business)
