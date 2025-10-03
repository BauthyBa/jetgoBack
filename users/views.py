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
                # Campos de personalización de perfil (opción A)
                'bio': request.data.get('bio'),
                'interests': request.data.get('interests'),
                'favorite_travel_styles': request.data.get('favorite_travel_styles'),
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
        """Create trip, then create a linked chat room and add creator as member.
        Returns ok:true if at least the trip is created; includes partial error details when chat/membership fail.
        """
        admin = get_supabase_admin()
        payload = request.data or {}
        creator_id = str(payload.get('creator_id') or '')
        origin = payload.get('origin')
        destination = payload.get('destination')
        date_iso = payload.get('date')
        name = payload.get('name') or f"Viaje {origin or ''}-{destination or ''}"
        if not creator_id:
            return Response({'ok': False, 'error': 'creator_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        new_trip = None
        new_room = None
        errors: dict[str, str] = {}

        # 1) Create trip (table public.trips)
        try:
            trip_row = {
                'creator_id': creator_id,
                'origin': origin,
                'destination': destination,
                'date': date_iso,
                'name': name,
            }
            trip = admin.table('trips').insert(trip_row).execute()
            new_trip = (getattr(trip, 'data', None) or [None])[0]
        except Exception as e:
            return Response({'ok': False, 'error': f'No se pudo crear viaje: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        # 2) Create chat room (tolerant to missing trip_id column)
        try:
            room_payload = { 'name': f"Chat {name}", 'creator_id': creator_id }
            if new_trip and new_trip.get('id'):
                try:
                    resp = admin.table('chat_rooms').insert({ **room_payload, 'trip_id': new_trip['id'] }).execute()
                    new_room = (getattr(resp, 'data', None) or [None])[0]
                except Exception:
                    resp = admin.table('chat_rooms').insert(room_payload).execute()
                    new_room = (getattr(resp, 'data', None) or [None])[0]
            else:
                resp = admin.table('chat_rooms').insert(room_payload).execute()
                new_room = (getattr(resp, 'data', None) or [None])[0]
        except Exception as e:
            errors['room'] = f'No se pudo crear sala: {e}'

        # 3) Membership owner (best effort)
        if new_room:
            try:
                admin.table('chat_members').insert({ 'room_id': new_room['id'], 'user_id': creator_id, 'role': 'owner' }).execute()
            except Exception as e:
                errors['membership'] = f'No se pudo agregar al creador a la sala: {e}'
        # 3b) Trip membership owner (best effort)
        if new_trip and new_trip.get('id'):
            try:
                admin.table('trip_members').insert({ 'trip_id': new_trip['id'], 'user_id': creator_id, 'role': 'owner' }).execute()
            except Exception:
                pass

        status_code = status.HTTP_200_OK if new_trip else status.HTTP_400_BAD_REQUEST
        return Response({'ok': bool(new_trip), 'trip': new_trip, 'room': new_room, 'errors': errors or None}, status=status_code)


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

            # Si no existe, intentar localizar por nombre/creador y asignar trip_id (no crear una nueva)
            if not room:
                try:
                    guess = (
                        admin.table('chat_rooms')
                        .select('*')
                        .eq('creator_id', str(trip.get('creator_id') or ''))
                        .eq('name', f"Chat {trip.get('name') or ''}")
                        .limit(1)
                        .execute()
                    )
                    guessed = (getattr(guess, 'data', None) or [None])[0]
                except Exception:
                    guessed = None
                if guessed:
                    try:
                        admin.table('chat_rooms').update({'trip_id': trip_id}).eq('id', guessed['id']).execute()
                        room = guessed | {'trip_id': trip_id}
                    except Exception:
                        room = guessed
                else:
                    return Response({'ok': False, 'error': 'No hay sala para este viaje'}, status=status.HTTP_404_NOT_FOUND)

            # Crear membresía
            try:
                admin.table('chat_members').insert({ 'room_id': room['id'], 'user_id': user_id, 'role': 'member' }).execute()
            except Exception:
                pass
            # Crear membresía en trip_members también
            try:
                admin.table('trip_members').insert({ 'trip_id': trip_id, 'user_id': user_id, 'role': 'member' }).execute()
            except Exception:
                pass
            return Response({'ok': True, 'room_id': room['id']})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LeaveTripView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        """Permite abandonar un viaje. Si el usuario es el creador, elimina el viaje y su chat grupal.
        Para miembros, elimina su membresía del viaje y del chat.
        """
        try:
            admin = get_supabase_admin()
            trip_id = request.data.get('trip_id')
            user_id = str(request.data.get('user_id') or '')
            if not trip_id or not user_id:
                return Response({'ok': False, 'error': 'trip_id y user_id requeridos'}, status=status.HTTP_400_BAD_REQUEST)

            # Obtener viaje
            trip_resp = admin.table('trips').select('id,name,creator_id').eq('id', trip_id).limit(1).execute()
            trip = (getattr(trip_resp, 'data', None) or [None])[0]
            if not trip:
                return Response({'ok': False, 'error': 'Viaje no encontrado'}, status=status.HTTP_404_NOT_FOUND)

            is_owner = str(trip.get('creator_id') or '') == user_id

            # Localizar sala grupal por trip_id (si existe)
            room = None
            try:
                rooms = admin.table('chat_rooms').select('id,trip_id').eq('trip_id', trip_id).limit(1).execute()
                room = (getattr(rooms, 'data', None) or [None])[0]
            except Exception:
                room = None

            if is_owner:
                # El organizador elimina el viaje y limpia el chat para todos
                try:
                    if room and room.get('id'):
                        rid = room['id']
                        try:
                            admin.table('chat_messages').delete().eq('room_id', rid).execute()
                        except Exception:
                            pass
                        try:
                            admin.table('chat_members').delete().eq('room_id', rid).execute()
                        except Exception:
                            pass
                        try:
                            admin.table('chat_rooms').delete().eq('id', rid).execute()
                        except Exception:
                            pass
                except Exception:
                    # Continuar aunque falle limpieza parcial
                    pass
                try:
                    admin.table('trip_members').delete().eq('trip_id', trip_id).execute()
                except Exception:
                    pass
                try:
                    admin.table('trips').delete().eq('id', trip_id).execute()
                except Exception as e:
                    return Response({'ok': False, 'error': f'No se pudo eliminar el viaje: {e}'}, status=status.HTTP_400_BAD_REQUEST)
                return Response({'ok': True, 'deleted': True})

            # Miembro: salir del viaje y del chat
            try:
                if room and room.get('id'):
                    admin.table('chat_members').delete().eq('room_id', room['id']).eq('user_id', user_id).execute()
            except Exception:
                pass
            try:
                admin.table('trip_members').delete().eq('trip_id', trip_id).eq('user_id', user_id).execute()
            except Exception:
                pass
            return Response({'ok': True, 'deleted': False})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ListTripMembersView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            trip_id = request.query_params.get('trip_id')
            if not trip_id:
                return Response({'ok': False, 'error': 'trip_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
            members_resp = admin.table('trip_members').select('user_id').eq('trip_id', trip_id).execute()
            members = getattr(members_resp, 'data', []) or []
            ids = list({str(m.get('user_id')) for m in members if m and m.get('user_id')})
            name_map = {}
            if ids:
                try:
                    schema = environ.get('SUPABASE_SCHEMA', 'public')
                    table = environ.get('SUPABASE_USERS_TABLE', 'User')
                    prof = admin.schema(schema).table(table).select('userid,nombre,apellido').in_('userid', ids).execute()
                    for row in (getattr(prof, 'data', []) or []):
                        uid = str(row.get('userid'))
                        full = ' '.join([x for x in [row.get('nombre'), row.get('apellido')] if x]).strip()
                        if uid and full:
                            name_map[uid] = full
                except Exception:
                    name_map = {}
            enriched = [{ 'user_id': str(m.get('user_id')), 'name': name_map.get(str(m.get('user_id')))} for m in members]
            return Response({'ok': True, 'members': enriched})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
