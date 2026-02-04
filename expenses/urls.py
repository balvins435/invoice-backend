from rest_framework.routers import DefaultRouter
from .views import ExpenseViewSet, ExpenseCategoryViewSet

router = DefaultRouter()
router.register('expenses', ExpenseViewSet, basename='expenses')
router.register('categories', ExpenseCategoryViewSet, basename='expense-categories')

urlpatterns = router.urls
