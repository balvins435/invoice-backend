from rest_framework.permissions import BasePermission


class IsBusinessOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.business.owner == request.user

class IsInvoiceOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user