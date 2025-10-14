from rest_framework import serializers
from datetime import datetime

class TripReviewCreateSerializer(serializers.Serializer):
    """Serializer para crear reseñas de viajes"""
    trip_id = serializers.UUIDField(required=True)
    reviewer_id = serializers.UUIDField(required=True)
    organizer_id = serializers.UUIDField(required=True)
    overall_rating = serializers.IntegerField(min_value=1, max_value=5, required=True)
    
    # Ratings opcionales
    destination_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    organization_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    communication_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    value_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    
    # Comentarios opcionales
    overall_comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    destination_comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    organization_comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    communication_comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    value_comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    # Aspectos específicos del viaje
    trip_highlights = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    trip_improvements = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    # Preguntas de recomendación
    would_recommend = serializers.BooleanField(required=False, default=False)
    would_travel_again = serializers.BooleanField(required=False, default=False)
    
    # Configuración de privacidad
    is_anonymous = serializers.BooleanField(required=False, default=False)

    def validate(self, data):
        """Validaciones adicionales"""
        # Verificar que al menos un comentario esté presente
        comment_fields = [
            'overall_comment', 'destination_comment', 'organization_comment',
            'communication_comment', 'value_comment', 'trip_highlights'
        ]
        
        has_comment = any(data.get(field, '').strip() for field in comment_fields)
        if not has_comment:
            raise serializers.ValidationError(
                "Debes proporcionar al menos un comentario sobre el viaje"
            )
        
        return data


class TripReviewUpdateSerializer(serializers.Serializer):
    """Serializer para actualizar reseñas de viajes"""
    reviewer_id = serializers.UUIDField(required=True)
    
    # Ratings opcionales
    overall_rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    destination_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    organization_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    communication_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    value_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    
    # Comentarios opcionales
    overall_comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    destination_comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    organization_comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    communication_comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    value_comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    # Aspectos específicos del viaje
    trip_highlights = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    trip_improvements = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    # Preguntas de recomendación
    would_recommend = serializers.BooleanField(required=False)
    would_travel_again = serializers.BooleanField(required=False)
    
    # Configuración de privacidad
    is_anonymous = serializers.BooleanField(required=False)


class TripReviewResponseSerializer(serializers.Serializer):
    """Serializer para respuestas del organizador a reseñas"""
    organizer_id = serializers.UUIDField(required=True)
    response_text = serializers.CharField(max_length=2000, required=True)
    
    def validate_response_text(self, value):
        """Validar que el texto de respuesta no esté vacío"""
        if not value.strip():
            raise serializers.ValidationError("El texto de respuesta no puede estar vacío")
        return value.strip()


class TripReviewListSerializer(serializers.Serializer):
    """Serializer para listar reseñas con información relacionada"""
    id = serializers.UUIDField(read_only=True)
    trip_id = serializers.UUIDField(read_only=True)
    reviewer_id = serializers.UUIDField(read_only=True)
    organizer_id = serializers.UUIDField(read_only=True)
    
    # Ratings
    overall_rating = serializers.IntegerField(read_only=True)
    destination_rating = serializers.IntegerField(read_only=True, allow_null=True)
    organization_rating = serializers.IntegerField(read_only=True, allow_null=True)
    communication_rating = serializers.IntegerField(read_only=True, allow_null=True)
    value_rating = serializers.IntegerField(read_only=True, allow_null=True)
    
    # Comentarios
    overall_comment = serializers.CharField(read_only=True)
    destination_comment = serializers.CharField(read_only=True)
    organization_comment = serializers.CharField(read_only=True)
    communication_comment = serializers.CharField(read_only=True)
    value_comment = serializers.CharField(read_only=True)
    
    # Aspectos del viaje
    trip_highlights = serializers.CharField(read_only=True)
    trip_improvements = serializers.CharField(read_only=True)
    
    # Recomendaciones
    would_recommend = serializers.BooleanField(read_only=True)
    would_travel_again = serializers.BooleanField(read_only=True)
    
    # Configuración
    is_anonymous = serializers.BooleanField(read_only=True)
    
    # Fechas
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    # Información relacionada
    trips = serializers.DictField(read_only=True)
    reviewer = serializers.DictField(read_only=True)
    organizer = serializers.DictField(read_only=True)
    responses = serializers.ListField(read_only=True, required=False)


class TripReviewCategorySerializer(serializers.Serializer):
    """Serializer para categorías de evaluación"""
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class TripReviewStatsSerializer(serializers.Serializer):
    """Serializer para estadísticas de reseñas"""
    total_reviews = serializers.IntegerField(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    rating_distribution = serializers.DictField(read_only=True)
    recommendation_rate = serializers.FloatField(read_only=True)
    would_travel_again_rate = serializers.FloatField(read_only=True)
    
    # Estadísticas por categoría
    destination_avg = serializers.FloatField(read_only=True, allow_null=True)
    organization_avg = serializers.FloatField(read_only=True, allow_null=True)
    communication_avg = serializers.FloatField(read_only=True, allow_null=True)
    value_avg = serializers.FloatField(read_only=True, allow_null=True)
