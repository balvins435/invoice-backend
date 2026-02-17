from rest_framework import serializers
from .models import Expense, ExpenseCategory


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'


class ExpenseSerializer(serializers.ModelSerializer):
    business_id = serializers.IntegerField(write_only=True, required=False)
    category = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(source='description', required=False, allow_blank=True)

    class Meta:
        model = Expense
        fields = [
            'id',
            'business',
            'business_id',
            'user',
            'category',
            'title',
            'description',
            'notes',
            'amount',
            'vat_amount',
            'total_amount',
            'tax_deductible',
            'expense_date',
            'receipt',
            'created_at',
        ]
        read_only_fields = ['total_amount', 'created_at', 'user', 'business']

    def _get_or_create_category(self, raw_category):
        if not raw_category:
            return None
        category_value = str(raw_category).strip().lower()
        if not category_value:
            return None
        category, _ = ExpenseCategory.objects.get_or_create(name=category_value)
        return category

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['category'] = instance.category.name if instance.category else 'other'
        return data

    def create(self, validated_data):
        validated_data.pop('business_id', None)
        raw_category = validated_data.pop('category', None)
        validated_data['category'] = self._get_or_create_category(raw_category)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('business_id', None)
        raw_category = validated_data.pop('category', None)
        if raw_category is not None:
            validated_data['category'] = self._get_or_create_category(raw_category)
        return super().update(instance, validated_data)
