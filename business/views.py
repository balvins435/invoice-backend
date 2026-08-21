from rest_framework import permissions, viewsets

from .models import Business
from .serializers import BusinessSerializer
from .permissions import IsOwner
from .selectors import businesses_for_user, filter_businesses


class BusinessViewSet(viewsets.ModelViewSet):
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return filter_businesses(businesses_for_user(self.request.user), self.request.query_params)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
