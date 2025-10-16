from rest_framework import serializers
from .models import FeedEvent, Trip, Application
from users.models import User


class FeedEventSerializer(serializers.ModelSerializer):
    """Serializer para eventos del feed social"""
    user_name = serializers.SerializerMethodField()
    user_avatar = serializers.SerializerMethodField()
    target_user_name = serializers.SerializerMethodField()
    trip_name = serializers.SerializerMethodField()
    trip_destination = serializers.SerializerMethodField()
    event_icon = serializers.ReadOnlyField()
    event_color = serializers.ReadOnlyField()
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = FeedEvent
        fields = [
            'id', 'event_type', 'title', 'description', 'metadata',
            'user_name', 'user_avatar', 'target_user_name',
            'trip_name', 'trip_destination', 'event_icon', 'event_color',
            'created_at', 'time_ago', 'is_public'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_user_name(self, obj):
        """Obtiene el nombre completo del usuario"""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip()
        return "Usuario"
    
    def get_user_avatar(self, obj):
        """Obtiene el avatar del usuario"""
        if hasattr(obj.user, 'avatar_url') and obj.user.avatar_url:
            return obj.user.avatar_url
        return None
    
    def get_target_user_name(self, obj):
        """Obtiene el nombre del usuario objetivo"""
        if obj.target_user:
            return f"{obj.target_user.first_name} {obj.target_user.last_name}".strip()
        return None
    
    def get_trip_name(self, obj):
        """Obtiene el nombre del viaje"""
        if obj.trip:
            return obj.trip.name
        return None
    
    def get_trip_destination(self, obj):
        """Obtiene el destino del viaje"""
        if obj.trip:
            return obj.trip.destination
        return None
    
    def get_time_ago(self, obj):
        """Calcula el tiempo transcurrido desde la creación"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 0:
            return f"hace {diff.days} día{'s' if diff.days > 1 else ''}"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"hace {hours} hora{'s' if hours > 1 else ''}"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"hace {minutes} minuto{'s' if minutes > 1 else ''}"
        else:
            return "ahora mismo"


class FeedEventCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear eventos del feed"""
    
    class Meta:
        model = FeedEvent
        fields = [
            'event_type', 'user', 'target_user', 'trip', 'application',
            'title', 'description', 'metadata', 'is_public'
        ]
    
    def create(self, validated_data):
        """Crea un nuevo evento del feed"""
        return FeedEvent.objects.create(**validated_data)


class FeedStatsSerializer(serializers.Serializer):
    """Serializer para estadísticas del feed"""
    total_events = serializers.IntegerField()
    events_by_type = serializers.DictField()
    recent_activity = serializers.ListField(child=FeedEventSerializer())
    top_users = serializers.ListField()
    top_destinations = serializers.ListField()
