from rest_framework import serializers
from datetime import datetime

class TripExpenseCreateSerializer(serializers.Serializer):
    """Serializer para crear gastos de viaje"""
    trip_id = serializers.UUIDField(required=True)
    payer_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    currency = serializers.CharField(max_length=3, required=False, default='USD')
    description = serializers.CharField(max_length=500, required=True)
    category = serializers.CharField(max_length=50, required=True)
    expense_date = serializers.DateTimeField(required=False, default=datetime.now)
    location = serializers.CharField(max_length=200, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    receipt_url = serializers.URLField(required=False, allow_blank=True)
    receipt_filename = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_amount(self, value):
        """Validar que el monto sea positivo"""
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a 0")
        return value

    def validate_description(self, value):
        """Validar que la descripción no esté vacía"""
        if not value.strip():
            raise serializers.ValidationError("La descripción no puede estar vacía")
        return value.strip()


class TripExpenseUpdateSerializer(serializers.Serializer):
    """Serializer para actualizar gastos de viaje"""
    user_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    description = serializers.CharField(max_length=500, required=False)
    category = serializers.CharField(max_length=50, required=False)
    expense_date = serializers.DateTimeField(required=False)
    location = serializers.CharField(max_length=200, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    receipt_url = serializers.URLField(required=False, allow_blank=True)
    receipt_filename = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_amount(self, value):
        """Validar que el monto sea positivo"""
        if value is not None and value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a 0")
        return value


class TripExpenseSplitSerializer(serializers.Serializer):
    """Serializer para divisiones de gastos"""
    id = serializers.UUIDField(read_only=True)
    expense_id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(read_only=True)
    amount_owed = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_settled = serializers.BooleanField(read_only=True)
    settled_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    user = serializers.DictField(read_only=True)


class TripExpenseCommentSerializer(serializers.Serializer):
    """Serializer para comentarios en gastos"""
    id = serializers.UUIDField(read_only=True)
    expense_id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(read_only=True)
    comment = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    user = serializers.DictField(read_only=True)


class TripExpensePaymentSerializer(serializers.Serializer):
    """Serializer para pagos entre usuarios"""
    id = serializers.UUIDField(read_only=True)
    expense_id = serializers.UUIDField(read_only=True)
    from_user_id = serializers.UUIDField(read_only=True)
    to_user_id = serializers.UUIDField(read_only=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    currency = serializers.CharField(read_only=True)
    payment_method = serializers.CharField(read_only=True)
    payment_reference = serializers.CharField(read_only=True)
    notes = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    from_user = serializers.DictField(read_only=True)
    to_user = serializers.DictField(read_only=True)


class TripExpenseListSerializer(serializers.Serializer):
    """Serializer para listar gastos con información relacionada"""
    id = serializers.UUIDField(read_only=True)
    trip_id = serializers.UUIDField(read_only=True)
    payer_id = serializers.UUIDField(read_only=True)
    amount = serializers.DecimalField(read_only=True)
    currency = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    category = serializers.CharField(read_only=True)
    expense_date = serializers.DateTimeField(read_only=True)
    location = serializers.CharField(read_only=True)
    notes = serializers.CharField(read_only=True)
    receipt_url = serializers.URLField(read_only=True)
    receipt_filename = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    approved_by = serializers.UUIDField(read_only=True)
    approved_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    # Información relacionada
    payer = serializers.DictField(read_only=True)
    splits = serializers.ListField(child=TripExpenseSplitSerializer(), read_only=True)
    comments = serializers.ListField(child=TripExpenseCommentSerializer(), read_only=True)
    payments = serializers.ListField(child=TripExpensePaymentSerializer(), read_only=True)


class ExpenseCategorySerializer(serializers.Serializer):
    """Serializer para categorías de gastos"""
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    icon = serializers.CharField(read_only=True)
    color = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class TripExpenseSummarySerializer(serializers.Serializer):
    """Serializer para resumen de gastos"""
    total_expenses = serializers.DecimalField(read_only=True)
    total_paid = serializers.DecimalField(read_only=True)
    total_owed = serializers.DecimalField(read_only=True)
    currency = serializers.CharField(read_only=True)
    expense_count = serializers.IntegerField(read_only=True)


class UserBalanceSerializer(serializers.Serializer):
    """Serializer para balance de usuario"""
    total_owed = serializers.DecimalField(read_only=True)
    total_paid = serializers.DecimalField(read_only=True)
    balance = serializers.DecimalField(read_only=True)


class TripExpenseCreateCommentSerializer(serializers.Serializer):
    """Serializer para crear comentarios en gastos"""
    expense_id = serializers.UUIDField(required=True)
    user_id = serializers.UUIDField(required=True)
    comment = serializers.CharField(max_length=1000, required=True)
    
    def validate_comment(self, value):
        """Validar que el comentario no esté vacío"""
        if not value.strip():
            raise serializers.ValidationError("El comentario no puede estar vacío")
        return value.strip()


class TripExpenseCreatePaymentSerializer(serializers.Serializer):
    """Serializer para crear pagos entre usuarios"""
    expense_id = serializers.UUIDField(required=True)
    from_user_id = serializers.UUIDField(required=True)
    to_user_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    currency = serializers.CharField(max_length=3, required=False, default='USD')
    payment_method = serializers.CharField(max_length=50, required=False, allow_blank=True)
    payment_reference = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_amount(self, value):
        """Validar que el monto sea positivo"""
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a 0")
        return value

    def validate(self, data):
        """Validar que no se pague a uno mismo"""
        if data.get('from_user_id') == data.get('to_user_id'):
            raise serializers.ValidationError("No puedes pagarte a ti mismo")
        return data
