from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import FeedEvent, Trip, Application
from .feed_serializers import FeedEventSerializer, FeedEventCreateSerializer, FeedStatsSerializer
from users.models import User


class FeedEventListView(generics.ListAPIView):
    """Vista para obtener el feed de eventos sociales"""
    serializer_class = FeedEventSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Obtiene los eventos del feed con filtros opcionales"""
        queryset = FeedEvent.objects.filter(is_public=True).select_related(
            'user', 'target_user', 'trip'
        ).prefetch_related('application')
        
        # Filtro por tipo de evento
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        # Filtro por usuario
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filtro por viaje
        trip_id = self.request.query_params.get('trip_id')
        if trip_id:
            queryset = queryset.filter(trip_id=trip_id)
        
        # Filtro por fecha (últimos N días)
        days = self.request.query_params.get('days', 30)
        try:
            days = int(days)
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=cutoff_date)
        except ValueError:
            pass
        
        return queryset


class FeedEventCreateView(generics.CreateAPIView):
    """Vista para crear eventos del feed"""
    serializer_class = FeedEventCreateSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        """Crea un nuevo evento del feed"""
        serializer.save(user=self.request.user)


@api_view(['GET'])
def feed_stats(request):
    """Obtiene estadísticas del feed"""
    if not request.user.is_authenticated:
        return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
    
    # Estadísticas básicas
    total_events = FeedEvent.objects.filter(is_public=True).count()
    
    # Eventos por tipo
    events_by_type = dict(
        FeedEvent.objects.filter(is_public=True)
        .values('event_type')
        .annotate(count=Count('id'))
        .values_list('event_type', 'count')
    )
    
    # Actividad reciente (últimos 10 eventos)
    recent_activity = FeedEvent.objects.filter(is_public=True)[:10]
    recent_serializer = FeedEventSerializer(recent_activity, many=True)
    
    # Usuarios más activos
    top_users = list(
        FeedEvent.objects.filter(is_public=True)
        .values('user__first_name', 'user__last_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    
    # Destinos más populares
    top_destinations = list(
        FeedEvent.objects.filter(is_public=True, trip__isnull=False)
        .values('trip__destination')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    
    stats_data = {
        'total_events': total_events,
        'events_by_type': events_by_type,
        'recent_activity': recent_serializer.data,
        'top_users': top_users,
        'top_destinations': top_destinations
    }
    
    serializer = FeedStatsSerializer(stats_data)
    return Response(serializer.data)


@api_view(['POST'])
def create_feed_event(request):
    """Crea un evento del feed programáticamente"""
    if not request.user.is_authenticated:
        return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
    
    serializer = FeedEventCreateSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Funciones helper para crear eventos automáticamente
def create_trip_created_event(trip):
    """Crea un evento cuando se crea un viaje"""
    FeedEvent.objects.create(
        event_type='trip_created',
        user=trip.creator,
        trip=trip,
        title=f"{trip.creator.first_name} creó un nuevo viaje",
        description=f"Viaje a {trip.destination} desde {trip.origin}",
        metadata={
            'trip_id': trip.id,
            'destination': trip.destination,
            'origin': trip.origin,
            'start_date': trip.start_date.isoformat() if trip.start_date else None
        }
    )


def create_trip_joined_event(trip, user):
    """Crea un evento cuando un usuario se une a un viaje"""
    FeedEvent.objects.create(
        event_type='trip_joined',
        user=user,
        trip=trip,
        title=f"{user.first_name} se unió a un viaje",
        description=f"Se unió al viaje a {trip.destination}",
        metadata={
            'trip_id': trip.id,
            'destination': trip.destination,
            'trip_creator': trip.creator.first_name
        }
    )


def create_application_received_event(application):
    """Crea un evento cuando se recibe una aplicación"""
    FeedEvent.objects.create(
        event_type='application_received',
        user=application.applicant,
        target_user=application.trip.creator,
        trip=application.trip,
        application=application,
        title=f"{application.applicant.first_name} aplicó a tu viaje",
        description=f"Aplicó al viaje a {application.trip.destination}",
        metadata={
            'application_id': application.id,
            'trip_id': application.trip.id,
            'message': application.message
        }
    )


def create_application_accepted_event(application):
    """Crea un evento cuando se acepta una aplicación"""
    FeedEvent.objects.create(
        event_type='application_accepted',
        user=application.trip.creator,
        target_user=application.applicant,
        trip=application.trip,
        application=application,
        title=f"Tu aplicación fue aceptada",
        description=f"Fuiste aceptado en el viaje a {application.trip.destination}",
        metadata={
            'application_id': application.id,
            'trip_id': application.trip.id,
            'trip_creator': application.trip.creator.first_name
        }
    )


def create_application_rejected_event(application):
    """Crea un evento cuando se rechaza una aplicación"""
    FeedEvent.objects.create(
        event_type='application_rejected',
        user=application.trip.creator,
        target_user=application.applicant,
        trip=application.trip,
        application=application,
        title=f"Tu aplicación fue rechazada",
        description=f"No fuiste aceptado en el viaje a {application.trip.destination}",
        metadata={
            'application_id': application.id,
            'trip_id': application.trip.id,
            'trip_creator': application.trip.creator.first_name
        }
    )


def create_friendship_request_event(sender, receiver):
    """Crea un evento cuando se envía una solicitud de amistad"""
    FeedEvent.objects.create(
        event_type='friendship_request',
        user=sender,
        target_user=receiver,
        title=f"{sender.first_name} te envió una solicitud de amistad",
        description=f"Quiere conectarse contigo",
        metadata={
            'sender_id': sender.id,
            'receiver_id': receiver.id
        }
    )


def create_friendship_accepted_event(sender, receiver):
    """Crea un evento cuando se acepta una amistad"""
    FeedEvent.objects.create(
        event_type='friendship_accepted',
        user=receiver,
        target_user=sender,
        title=f"{receiver.first_name} y {sender.first_name} ahora son amigos",
        description=f"Se conectaron en JetGo",
        metadata={
            'sender_id': sender.id,
            'receiver_id': receiver.id
        }
    )


def create_trip_completed_event(trip):
    """Crea un evento cuando se completa un viaje"""
    FeedEvent.objects.create(
        event_type='trip_completed',
        user=trip.creator,
        trip=trip,
        title=f"Viaje completado: {trip.name}",
        description=f"El viaje a {trip.destination} ha terminado",
        metadata={
            'trip_id': trip.id,
            'destination': trip.destination,
            'participants_count': trip.current_participants
        }
    )


def create_user_joined_event(user):
    """Crea un evento cuando un nuevo usuario se registra"""
    FeedEvent.objects.create(
        event_type='user_joined',
        user=user,
        title=f"¡Bienvenido {user.first_name}!",
        description=f"Se unió a la comunidad JetGo",
        metadata={
            'user_id': user.id,
            'join_date': user.date_joined.isoformat()
        }
    )
