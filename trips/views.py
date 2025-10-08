from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import Trip, Application, TripParticipant
from .serializers import (
    TripSerializer, TripListSerializer, ApplicationSerializer, 
    ApplicationCreateSerializer, ApplicationResponseSerializer,
    TripParticipantSerializer
)
from api.supabase_client import get_supabase_admin
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)
class TripListCreateView(generics.ListCreateAPIView):
    """Listar y crear viajes"""
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return TripListSerializer
        return TripSerializer
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        queryset = Trip.objects.filter(status='abierto').order_by('-created_at')
        
        # Filtros opcionales
        origin = self.request.query_params.get('origin')
        destination = self.request.query_params.get('destination')
        travel_style = self.request.query_params.get('travel_style')
        budget_min = self.request.query_params.get('budget_min')
        budget_max = self.request.query_params.get('budget_max')
        
        if origin:
            queryset = queryset.filter(origin__icontains=origin)
        if destination:
            queryset = queryset.filter(destination__icontains=destination)
        if travel_style:
            queryset = queryset.filter(travel_style=travel_style)
        if budget_min:
            queryset = queryset.filter(budget_min__gte=budget_min)
        if budget_max:
            queryset = queryset.filter(budget_max__lte=budget_max)
            
        return queryset
    
    def perform_create(self, serializer):
        # Validaciones antes de crear el viaje
        validated_data = serializer.validated_data
        
        # Validación de presupuesto
        budget_min = validated_data.get('budget_min')
        budget_max = validated_data.get('budget_max')
        
        if budget_min is not None and budget_min < 0:
            raise ValidationError({'budget_min': 'El presupuesto mínimo no puede ser menor a 0'})
        
        if budget_max is not None and budget_max < 0:
            raise ValidationError({'budget_max': 'El presupuesto máximo no puede ser menor a 0'})
        
        if budget_min is not None and budget_max is not None and budget_min > budget_max:
            raise ValidationError({'budget_min': 'El presupuesto mínimo no puede ser mayor al máximo'})
        
        # Validación de fechas
        start_date = validated_data.get('start_date')
        end_date = validated_data.get('end_date')
        today = date.today()
        
        if start_date and start_date < today:
            raise ValidationError({'start_date': 'La fecha de inicio no puede ser anterior al día de hoy'})
        
        if end_date and end_date < today:
            raise ValidationError({'end_date': 'La fecha de fin no puede ser anterior al día de hoy'})
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError({'start_date': 'La fecha de inicio no puede ser posterior a la fecha de fin'})
        
        trip = serializer.save(creator=self.request.user)
        # Registrar al creador como participante
        try:
            TripParticipant.objects.get_or_create(
                trip=trip,
                user=self.request.user,
                defaults={'is_creator': True}
            )
        except Exception:
            pass


class TripDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Detalle, actualizar y eliminar viaje"""
    serializer_class = TripSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Trip.objects.all()
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
    
    def perform_update(self, serializer):
        # Validaciones antes de actualizar el viaje
        validated_data = serializer.validated_data
        
        # Validación de presupuesto
        budget_min = validated_data.get('budget_min')
        budget_max = validated_data.get('budget_max')
        
        if budget_min is not None and budget_min < 0:
            raise ValidationError({'budget_min': 'El presupuesto mínimo no puede ser menor a 0'})
        
        if budget_max is not None and budget_max < 0:
            raise ValidationError({'budget_max': 'El presupuesto máximo no puede ser menor a 0'})
        
        if budget_min is not None and budget_max is not None and budget_min > budget_max:
            raise ValidationError({'budget_min': 'El presupuesto mínimo no puede ser mayor al máximo'})
        
        # Validación de fechas
        start_date = validated_data.get('start_date')
        end_date = validated_data.get('end_date')
        today = date.today()
        
        if start_date and start_date < today:
            raise ValidationError({'start_date': 'La fecha de inicio no puede ser anterior al día de hoy'})
        
        if end_date and end_date < today:
            raise ValidationError({'end_date': 'La fecha de fin no puede ser anterior al día de hoy'})
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError({'start_date': 'La fecha de inicio no puede ser posterior a la fecha de fin'})
        
        serializer.save()


class ApplicationCreateView(generics.CreateAPIView):
    """Aplicar a un viaje"""
    serializer_class = ApplicationCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        application = serializer.save(applicant=self.request.user)
        # Crear chat privado entre aplicante y organizador con el mensaje inicial
        create_private_chat_for_application(application)


class ApplicationListView(generics.ListAPIView):
    """Listar aplicaciones del usuario"""
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Application.objects.filter(applicant=self.request.user).order_by('-created_at')


class TripApplicationsListView(generics.ListAPIView):
    """Listar aplicaciones de un viaje (solo para el creador)"""
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        trip_id = self.kwargs['trip_id']
        trip = get_object_or_404(Trip, id=trip_id)
        
        # Solo el creador puede ver las aplicaciones
        if trip.creator != self.request.user:
            return Application.objects.none()
        
        return Application.objects.filter(trip=trip).order_by('-created_at')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def respond_to_application(request, application_id):
    """Aceptar o rechazar una aplicación"""
    application = get_object_or_404(Application, id=application_id)
    
    # Solo el creador del viaje puede responder
    if application.trip.creator != request.user:
        return Response(
            {'error': 'No tienes permisos para responder esta aplicación'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = ApplicationResponseSerializer(application, data=request.data)
    if serializer.is_valid():
        action = serializer.validated_data['action']
        
        try:
            if action == 'accept':
                application.accept()
                # Cerrar chat privado y, si corresponde, unir/crear chat grupal
                close_private_chat(application, f"Tu aplicación a '{application.trip.name}' fue aceptada. Te agregamos al chat grupal.")
                # Crear/asegurar chat grupal solo si hay 3+ participantes
                if application.trip.current_participants >= 3:
                    room = ensure_group_chat_for_trip(application.trip)
                    if room:
                        add_trip_participants_to_room(application.trip, room.get('id'))
                return Response({'message': 'Aplicación aceptada'})
            else:
                application.reject()
                # Cerrar chat privado con mensaje de rechazo
                close_private_chat(application, f"Tu aplicación a '{application.trip.name}' fue rechazada por el organizador.")
                return Response({'message': 'Aplicación rechazada'})
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def create_private_chat_for_application(application):
    """Crear chat privado entre anfitrión y aplicante al momento de aplicar, con el mensaje inicial del aplicante."""
    try:
        admin = get_supabase_admin()

        # Intentar crear sala con metadata de privado
        room_payload = {
            'name': f"Privado: {application.trip.name}",
            'creator_id': str(application.trip.creator.id),
            'trip_id': application.trip.id,
            'application_id': application.id,
            'is_group': False,
            'is_private': True,
        }
        try:
            room_resp = admin.table('chat_rooms').insert(room_payload).execute()
        except Exception:
            # Fallback sin flags adicionales por compatibilidad de esquema
            minimal = {k: room_payload[k] for k in ['name', 'creator_id', 'trip_id', 'application_id']}
            room_resp = admin.table('chat_rooms').insert(minimal).execute()
        room = (getattr(room_resp, 'data', None) or [None])[0]

        if room:
            # Miembros: organizador y aplicante
            members = [
                {'room_id': room['id'], 'user_id': str(application.trip.creator.id), 'role': 'owner'},
                {'room_id': room['id'], 'user_id': str(application.applicant.id), 'role': 'member'},
            ]
            try:
                admin.table('chat_members').insert(members).execute()
            except Exception:
                pass

            # Mensaje inicial del aplicante (si lo hay)
            initial = (application.message or '').strip()
            if initial:
                try:
                    admin.table('chat_messages').insert({
                        'room_id': room['id'],
                        'user_id': str(application.applicant.id),
                        'content': initial,
                    }).execute()
                except Exception:
                    pass
            logger.info(f"Chat privado creado para aplicación {application.id}")
    except Exception as e:
        logger.error(f"Error creando chat privado para aplicación {application.id}: {e}")
        # No lanzar excepción


def _find_private_room_for_application(admin, application):
    try:
        resp = admin.table('chat_rooms').select('*').eq('application_id', application.id).limit(1).execute()
        return (getattr(resp, 'data', None) or [None])[0]
    except Exception:
        return None


def close_private_chat(application, closing_message: str | None = None):
    """Marca como cerrado el chat privado de la aplicación (si existe) y agrega mensaje final."""
    try:
        admin = get_supabase_admin()
        room = _find_private_room_for_application(admin, application)
        if not room:
            return
        # Intentar marcar cierre en la sala (is_closed/closed_at si existen)
        now_iso = datetime.utcnow().isoformat()
        try:
            admin.table('chat_rooms').update({'is_closed': True, 'closed_at': now_iso}).eq('id', room['id']).execute()
        except Exception:
            # Fallback: intentar solo closed_at
            try:
                admin.table('chat_rooms').update({'closed_at': now_iso}).eq('id', room['id']).execute()
            except Exception:
                pass
        # Mensaje de cierre (desde el organizador)
        if closing_message:
            try:
                admin.table('chat_messages').insert({
                    'room_id': room['id'],
                    'user_id': str(application.trip.creator.id),
                    'content': closing_message,
                }).execute()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error cerrando chat privado para aplicación {application.id}: {e}")


def ensure_group_chat_for_trip(trip):
    """Obtiene o crea la sala de chat grupal para un viaje. Devuelve el dict de la sala o None."""
    try:
        admin = get_supabase_admin()
        # Buscar existente por trip_id e is_group true
        try:
            resp = admin.table('chat_rooms').select('*').eq('trip_id', trip.id).eq('is_group', True).limit(1).execute()
            room = (getattr(resp, 'data', None) or [None])[0]
        except Exception:
            # Fallback: buscar por nombre únicamente
            try:
                resp = admin.table('chat_rooms').select('*').eq('name', f"Grupo: {trip.name}").limit(1).execute()
                room = (getattr(resp, 'data', None) or [None])[0]
            except Exception:
                room = None
        if room:
            return room
        # Crear si no existe
        payload = {
            'name': f"Grupo: {trip.name}",
            'creator_id': str(trip.creator.id),
            'trip_id': trip.id,
            'is_group': True,
        }
        try:
            created = admin.table('chat_rooms').insert(payload).execute()
        except Exception:
            # Fallback sin is_group
            created = admin.table('chat_rooms').insert({k: payload[k] for k in ['name', 'creator_id', 'trip_id']}).execute()
        return (getattr(created, 'data', None) or [None])[0]
    except Exception as e:
        logger.error(f"Error asegurando chat grupal para viaje {trip.id}: {e}")
        return None


def add_trip_participants_to_room(trip, room_id):
    """Agrega a todos los participantes del viaje a la sala indicada (id)."""
    try:
        admin = get_supabase_admin()
        participants = TripParticipant.objects.filter(trip=trip)
        payload = []
        for p in participants:
            payload.append({
                'room_id': room_id,
                'user_id': str(p.user.id),
                'role': 'owner' if p.is_creator else 'member',
            })
        if payload:
            try:
                admin.table('chat_members').insert(payload).execute()
            except Exception:
                # Insertar individualmente para tolerar duplicados
                for row in payload:
                    try:
                        admin.table('chat_members').insert(row).execute()
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"Error agregando participantes de viaje {trip.id} a sala {room_id}: {e}")


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def leave_trip(request, trip_id):
    """Permite a un usuario abandonar un viaje y lo elimina del chat grupal asociado."""
    trip = get_object_or_404(Trip, id=trip_id)
    user = request.user

    # Validar participación
    participant = TripParticipant.objects.filter(trip=trip, user=user).first()
    if not participant:
        return Response({'error': 'No sos participante de este viaje'}, status=status.HTTP_400_BAD_REQUEST)

    # Evitar que el creador abandone (simplificación)
    if participant.is_creator:
        return Response({'error': 'El creador no puede abandonar el viaje'}, status=status.HTTP_400_BAD_REQUEST)

    # Remover participación y decrementar contadores
    try:
        participant.delete()
        if trip.current_participants > 0:
            trip.current_participants -= 1
            trip.save()
    except Exception as e:
        return Response({'error': f'No se pudo abandonar el viaje: {e}'}, status=status.HTTP_400_BAD_REQUEST)

    # Remover membresía del chat grupal (si existe)
    try:
        admin = get_supabase_admin()
        # Intentar localizar sala grupal por trip_id
        room = None
        try:
            resp = admin.table('chat_rooms').select('*').eq('trip_id', trip.id).eq('is_group', True).limit(1).execute()
            room = (getattr(resp, 'data', None) or [None])[0]
        except Exception:
            try:
                resp = admin.table('chat_rooms').select('*').eq('name', f"Grupo: {trip.name}").limit(1).execute()
                room = (getattr(resp, 'data', None) or [None])[0]
            except Exception:
                room = None
        if room and room.get('id'):
            try:
                admin.table('chat_members').delete().eq('room_id', room['id']).eq('user_id', str(user.id)).execute()
            except Exception:
                pass
    except Exception:
        # No bloquear por errores de chat
        pass

    return Response({'message': 'Has abandonado el viaje'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def trip_participants(request, trip_id):
    """Obtener participantes de un viaje"""
    trip = get_object_or_404(Trip, id=trip_id)
    
    # Solo participantes o creador pueden ver la lista
    if not (trip.creator == request.user or 
            TripParticipant.objects.filter(trip=trip, user=request.user).exists()):
        return Response(
            {'error': 'No tienes permisos para ver los participantes'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    participants = TripParticipant.objects.filter(trip=trip)
    serializer = TripParticipantSerializer(participants, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_participating_trips(request):
    """Obtener viajes donde el usuario es participante"""
    try:
        user = request.user
        
        # Obtener viajes donde el usuario es participante (creador o miembro)
        participating_trips = Trip.objects.filter(
            Q(creator=user) | Q(participants__user=user)
        ).distinct().order_by('-created_at')
        
        serializer = TripListSerializer(participating_trips, many=True)
        return Response({
            'ok': True,
            'trips': serializer.data
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo viajes del usuario {request.user.id}: {e}")
        return Response({
            'ok': False,
            'error': 'Error interno del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_group_chat(request, trip_id):
    """Crear chat grupal cuando hay más de 2 participantes"""
    trip = get_object_or_404(Trip, id=trip_id)
    
    # Solo el creador puede crear chat grupal
    if trip.creator != request.user:
        return Response(
            {'error': 'Solo el creador puede crear el chat grupal'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    if trip.current_participants < 3:
        return Response(
            {'error': 'Se necesitan al menos 3 participantes para crear un chat grupal'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        admin = get_supabase_admin()
        
        # Crear sala de chat grupal
        room_data = {
            'name': f"Grupo: {trip.name}",
            'creator_id': str(trip.creator.id),
            'trip_id': trip.id,
            'is_group': True
        }
        
        room_response = admin.table('chat_rooms').insert(room_data).execute()
        room = (getattr(room_response, 'data', None) or [None])[0]
        
        if room:
            # Agregar todos los participantes
            participants = TripParticipant.objects.filter(trip=trip)
            members_data = []
            
            for participant in participants:
                members_data.append({
                    'room_id': room['id'],
                    'user_id': str(participant.user.id),
                    'role': 'owner' if participant.is_creator else 'member'
                })
            
            admin.table('chat_members').insert(members_data).execute()
            
            # Mensaje de bienvenida grupal
            welcome_message = {
                'room_id': room['id'],
                'user_id': str(trip.creator.id),
                'content': f"¡Bienvenidos al grupo de {trip.name}! ¡Hablemos sobre nuestro viaje!"
            }
            
            admin.table('chat_messages').insert(welcome_message).execute()
            
            return Response({'message': 'Chat grupal creado', 'room_id': room['id']})
            
    except Exception as e:
        logger.error(f"Error creando chat grupal para viaje {trip_id}: {e}")
        return Response(
            {'error': 'No se pudo crear el chat grupal. Verifica la configuración de Supabase.'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )