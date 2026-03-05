from rest_framework.routers import DefaultRouter

from .views import TaxSubmissionViewSet

router = DefaultRouter()
router.register("submissions", TaxSubmissionViewSet, basename="tax-submissions")

urlpatterns = router.urls
