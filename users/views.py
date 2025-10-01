from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.authentication import BaseAuthentication
from rest_framework.response import Response
from .serializers import RegisterSerializer, LoginSerializer
from api.supabase_client import get_supabase_admin
from os import environ
import re
import requests


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({
            'access': serializer.validated_data['supabase_access'],
            'refresh': serializer.validated_data['supabase_refresh'],
        })

class UpsertProfileView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    http_method_names = ['post']
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            schema = environ.get('SUPABASE_SCHEMA', 'public')
            table = environ.get('SUPABASE_USERS_TABLE', 'User')
            user_id = request.data.get('user_id')
            update_row = {
                'userid': str(user_id),
                'dni': request.data.get('document_number'),
                'nombre': request.data.get('first_name'),
                'apellido': request.data.get('last_name'),
                'sexo': request.data.get('sex'),
                'fecha_nacimiento': request.data.get('birth_date'),
                'mail': request.data.get('email'),
            }
            # Use upsert to insert or update by userid
            try:
                resp = admin.schema(schema).table(table).upsert(update_row, on_conflict='userid').execute()
            except Exception:
                # Fallback to update when upsert is unavailable
                resp = admin.schema(schema).table(table).update(update_row).eq('userid', str(user_id)).execute()
            return Response({'ok': True, 'data': getattr(resp, 'data', None)})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, *args, **kwargs):
        return Response({'detail': 'Method not allowed'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


class InviteView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    http_method_names = ['post']
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        room_id = request.data.get('room_id')
        inviter_id = request.data.get('inviter_id')
        if not email or not room_id:
            return Response({'ok': False, 'error': 'email y room_id requeridos'}, status=status.HTTP_400_BAD_REQUEST)
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(email)):
            return Response({'ok': False, 'error': 'email inválido'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            admin = get_supabase_admin()
            # Registrar invitación en tabla (si existe)
            try:
                admin.table('chat_invitations').insert({
                    'room_id': room_id,
                    'email': email,
                    'inviter_id': inviter_id,
                    'status': 'sent',
                }).execute()
            except Exception:
                pass

            # Intentar invitación vía GoTrue Admin REST
            base_url = environ.get('SUPABASE_URL')
            service_key = environ.get('SUPABASE_SERVICE_ROLE_KEY')
            sent = False
            if base_url and service_key:
                try:
                    resp = requests.post(
                        f"{base_url.rstrip('/')}/auth/v1/invite",
                        json={ 'email': email },
                        headers={
                            'Authorization': f"Bearer {service_key}",
                            'apikey': service_key,
                            'Content-Type': 'application/json',
                        },
                        timeout=10,
                    )
                    if resp.status_code in (200, 201):
                        sent = True
                except Exception:
                    sent = False
            return Response({'ok': True, 'email_sent': sent})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TripCreateView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        """Create trip in Supabase and a chat room + membership for creator."""
        try:
            admin = get_supabase_admin()
            payload = request.data or {}
            creator_id = str(payload.get('creator_id') or '')
            origin = payload.get('origin')
            destination = payload.get('destination')
            date_iso = payload.get('date')
            name = payload.get('name') or f"Viaje {origin or ''}-{destination or ''}"
            if not creator_id:
                return Response({'ok': False, 'error': 'creator_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

            # 1) Create trip (table public.trips)
            trip_row = {
                'creator_id': creator_id,
                'origin': origin,
                'destination': destination,
                'date': date_iso,
                'name': name,
            }
            trip = admin.table('trips').insert(trip_row).execute()
            new_trip = (getattr(trip, 'data', None) or [None])[0]

            # 2) Create chat room
            room_payload = { 'name': f"Chat {name}", 'creator_id': creator_id }
            if new_trip and new_trip.get('id'):
                room_payload['trip_id'] = new_trip['id']
            room = admin.table('chat_rooms').insert(room_payload).execute()
            new_room = (getattr(room, 'data', None) or [None])[0]

            # 3) Membership owner
            if new_room:
                try:
                    admin.table('chat_members').insert({ 'room_id': new_room['id'], 'user_id': creator_id, 'role': 'owner' }).execute()
                except Exception:
                    pass

            return Response({'ok': True, 'trip': new_trip, 'room': new_room})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ListTripsView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            trips = admin.table('trips').select('*').order('created_at', desc=True).execute()
            return Response({'ok': True, 'trips': getattr(trips, 'data', [])})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class JoinTripView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            trip_id = request.data.get('trip_id')
            user_id = request.data.get('user_id')
            if not trip_id or not user_id:
                return Response({'ok': False, 'error': 'trip_id y user_id requeridos'}, status=status.HTTP_400_BAD_REQUEST)

            # Verificar que el viaje exista
            trip_resp = admin.table('trips').select('id,name,creator_id').eq('id', trip_id).limit(1).execute()
            trip = (getattr(trip_resp, 'data', None) or [None])[0]
            if not trip:
                return Response({'ok': False, 'error': 'Viaje no encontrado'}, status=status.HTTP_404_NOT_FOUND)

            # Intentar encontrar sala por trip_id
            room = None
            try:
                rooms = admin.table('chat_rooms').select('*').eq('trip_id', trip_id).limit(1).execute()
                room = (getattr(rooms, 'data', None) or [None])[0]
            except Exception:
                room = None

            # Si no existe sala, crearla (con trip_id si la columna existe)
            if not room:
                payload = { 'name': f"Chat {trip.get('name') or ''}", 'creator_id': str(trip.get('creator_id') or user_id) }
                created = None
                # Intentar con trip_id
                try:
                    payload_with_trip = { **payload, 'trip_id': trip_id }
                    created_resp = admin.table('chat_rooms').insert(payload_with_trip).execute()
                    created = (getattr(created_resp, 'data', None) or [None])[0]
                except Exception:
                    # Fallback sin trip_id (por si la columna no existe aún)
                    try:
                        created_resp = admin.table('chat_rooms').insert(payload).execute()
                        created = (getattr(created_resp, 'data', None) or [None])[0]
                    except Exception as e2:
                        return Response({'ok': False, 'error': f'No se pudo crear sala: {e2}'}, status=status.HTTP_400_BAD_REQUEST)
                room = created

            # Crear membresía
            try:
                admin.table('chat_members').insert({ 'room_id': room['id'], 'user_id': user_id, 'role': 'member' }).execute()
            except Exception:
                pass
            return Response({'ok': True, 'room_id': room['id']})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
