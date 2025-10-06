from rest_framework import serializers
from .models import Trip, Application, TripParticipant
from users.models import User


class TripSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator.first_name', read_only=True)
    creator_last_name = serializers.CharField(source='creator.last_name', read_only=True)
    available_spots = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    
    class Meta:
        model = Trip
        fields = [
            'id', 'name', 'description', 'creator', 'creator_name', 'creator_last_name',
            'start_date', 'end_date', 'origin', 'destination', 'travel_style',
            'transport_type', 'accommodation_type', 'planned_activities',
            'max_participants', 'current_participants', 'available_spots', 'is_full',
            'budget_min', 'budget_max', 'flexibility_level', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['creator', 'current_participants', 'created_at', 'updated_at']


class ApplicationSerializer(serializers.ModelSerializer):
    applicant_name = serializers.CharField(source='applicant.first_name', read_only=True)
    applicant_last_name = serializers.CharField(source='applicant.last_name', read_only=True)
    applicant_email = serializers.CharField(source='applicant.email', read_only=True)
    trip_name = serializers.CharField(source='trip.name', read_only=True)
    
    class Meta:
        model = Application
        fields = [
            'id', 'trip', 'trip_name', 'applicant', 'applicant_name', 
            'applicant_last_name', 'applicant_email', 'status', 'message',
            'created_at', 'updated_at', 'responded_at'
        ]
        read_only_fields = ['applicant', 'created_at', 'updated_at', 'responded_at']


class ApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['trip', 'message']
    
    def validate(self, attrs):
        trip = attrs.get('trip')
        user = self.context['request'].user
        
        # Verificar que el usuario no sea el creador del viaje
        if trip.creator == user:
            raise serializers.ValidationError("No puedes aplicar a tu propio viaje")
        
        # Verificar que el viaje esté abierto
        if trip.status != 'abierto':
            raise serializers.ValidationError("Este viaje no está abierto para aplicaciones")
        
        # Verificar que el viaje no esté lleno
        if trip.is_full:
            raise serializers.ValidationError("Este viaje ya está completo")
        
        # Verificar que no haya una aplicación previa
        if Application.objects.filter(trip=trip, applicant=user).exists():
            raise serializers.ValidationError("Ya has aplicado a este viaje")
        
        return attrs


class ApplicationResponseSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['accept', 'reject'])
    
    def validate(self, attrs):
        application = self.instance
        if application.status != 'pending':
            raise serializers.ValidationError("Solo se pueden responder aplicaciones pendientes")
        return attrs


class TripParticipantSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = TripParticipant
        fields = ['id', 'user', 'user_name', 'user_last_name', 'user_email', 
                 'joined_at', 'is_creator']
        read_only_fields = ['joined_at', 'is_creator']


class TripListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listar viajes"""
    creator_name = serializers.CharField(source='creator.first_name', read_only=True)
    available_spots = serializers.ReadOnlyField()
    
    class Meta:
        model = Trip
        fields = [
            'id', 'name', 'origin', 'destination', 'start_date', 'end_date',
            'travel_style', 'max_participants', 'current_participants', 
            'available_spots', 'budget_min', 'budget_max', 'status',
            'creator_name', 'created_at'
        ]
