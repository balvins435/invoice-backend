from rest_framework.exceptions import ValidationError
from business.models import Business

def resolve_owned_business(*, business_id, user):
    if not business_id:
        raise ValidationError({"business_id": "This field is required."})
    business = Business.objects.filter(id=business_id, owner=user).first()
    if not business:
        raise ValidationError({"business_id": "Invalid business for this user."})
    return business
