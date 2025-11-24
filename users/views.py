from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.authentication import BaseAuthentication
from rest_framework.response import Response
from .serializers import RegisterSerializer, LoginSerializer, ReviewSerializer, CreateReviewSerializer
from .models import User, Review
from django.db.models import Avg
from api.supabase_client import get_supabase_admin
from os import environ
import math
from trips.models import Trip, TripParticipant
import re
from datetime import datetime, date
import requests


def calculate_trip_status(start_date, end_date=None):
    """
    Calcula el estado de un viaje basado en las fechas:
    - upcoming: si la fecha de inicio es en el futuro
    - active: si estamos entre la fecha de inicio y fin (o solo inicio si no hay fin)
    - completed: si la fecha de fin ya pasó (o la fecha de inicio si no hay fin)
    """
    if not start_date:
        return 'upcoming'
    
    try:
        # Convertir string a date si es necesario
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00')).date()
        elif isinstance(start_date, datetime):
            start_date = start_date.date()
        
        today = date.today()
        
        # Si hay fecha de fin
        if end_date:
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
            elif isinstance(end_date, datetime):
                end_date = end_date.date()
            
            if today < start_date:
                return 'upcoming'
            elif start_date <= today <= end_date:
                return 'active'
            else:
                return 'completed'
        else:
            # Solo fecha de inicio
            if today < start_date:
                return 'upcoming'
            elif today == start_date:
                return 'active'
            else:
                return 'completed'
                
    except Exception:
        return 'upcoming'


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
                'avatar_url': request.data.get('avatar_url'),
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
        country = payload.get('country')
        budget_min = payload.get('budget_min')
        budget_max = payload.get('budget_max')
        currency = payload.get('currency', 'USD')
        # status_val ya no es necesario, se calcula automáticamente
        room_type = payload.get('room_type')
        season = payload.get('season')
        max_participants = payload.get('max_participants')
        # transport_type puede venir como 'transport_type' (backend) o 'tipo' (UI)
        transport_type = payload.get('transport_type') or payload.get('tipo')
        date_iso = payload.get('start_date') or payload.get('date')  # Compatibilidad con ambos nombres
        name = payload.get('name') or f"Viaje {origin or ''}-{destination or ''}"
        if not creator_id:
            return Response({'ok': False, 'error': 'creator_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        # Required fields validation
        required_missing = []
        def add_if_missing(key, val):
            if val is None or (isinstance(val, str) and len(val.strip()) == 0):
                required_missing.append(key)
        add_if_missing('name', name)
        add_if_missing('origin', origin)
        add_if_missing('destination', destination)
        add_if_missing('country', country)
        add_if_missing('budget_min', budget_min)
        add_if_missing('budget_max', budget_max)
        # status ya no es requerido, se calcula automáticamente
        add_if_missing('room_type', room_type)
        add_if_missing('max_participants', max_participants)
        add_if_missing('transport_type', transport_type)
        if required_missing:
            return Response({'ok': False, 'error': f'Faltan campos requeridos: {", ".join(required_missing)}'}, status=status.HTTP_400_BAD_REQUEST)

        # Coerce numeric fields
        try:
            budget_min_num = None if budget_min in (None, '') else float(budget_min)
            budget_max_num = None if budget_max in (None, '') else float(budget_max)
            max_participants_num = int(max_participants) if max_participants not in (None, '') else None
        except Exception:
            return Response({'ok': False, 'error': 'Campos numéricos inválidos'}, status=status.HTTP_400_BAD_REQUEST)

        if max_participants_num is not None and max_participants_num <= 0:
            return Response({'ok': False, 'error': 'max_participants debe ser mayor a 0'}, status=status.HTTP_400_BAD_REQUEST)

        new_trip = None
        new_room = None
        errors: dict[str, str] = {}

        # 1) Create trip (table public.trips)
        try:
            # Allow optional image_url passthrough if provided by frontend
            image_url = payload.get('image_url')
            # Calcular estado automáticamente basado en fechas
            auto_status = calculate_trip_status(date_iso, payload.get('end_date'))
            
            trip_row = {
                'creator_id': creator_id,
                'origin': origin,
                'destination': destination,
                'date': date_iso,  # Para compatibilidad
                'start_date': date_iso,  # Columna principal
                'end_date': payload.get('end_date'),
                'name': name,
                'country': country,
                'budget_min': budget_min_num,
                'budget_max': budget_max_num,
                'currency': currency,
                'status': auto_status,
                'room_type': room_type,
                'season': season,
                'max_participants': max_participants_num,
                'transport_type': transport_type,
            }
            if image_url:
                try:
                    trip_row['image_url'] = image_url
                except Exception:
                    pass
            # Validate duplicate name (case-insensitive)
            try:
                existing = admin.table('trips').select('id').ilike('name', name).limit(1).execute()
                exists_any = bool((getattr(existing, 'data', None) or []))
                if exists_any:
                    return Response({'ok': False, 'error': 'Ya existe un viaje con ese nombre'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception:
                # Best-effort; rely on DB unique index as final guard
                pass

            trip = admin.table('trips').insert(trip_row).execute()
            new_trip = (getattr(trip, 'data', None) or [None])[0]
        except Exception as e:
            return Response({'ok': False, 'error': f'No se pudo crear viaje: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        # 2) Create chat room (tolerant to missing trip_id column)
        try:
            room_payload = { 'name': f"Chat {name}", 'creator_id': creator_id, 'is_group': True }
            if new_trip and new_trip.get('id'):
                try:
                    resp = admin.table('chat_rooms').insert({ **room_payload, 'trip_id': new_trip['id'] }).execute()
                    new_room = (getattr(resp, 'data', None) or [None])[0]
                except Exception:
                    # Fallback without trip_id but still mark as group
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
                admin.table('trip_members').insert({ 'trip_id': new_trip['id'], 'user_id': str(creator_id), 'role': 'owner' }).execute()
            except Exception:
                pass

        status_code = status.HTTP_200_OK if new_trip else status.HTTP_400_BAD_REQUEST
        return Response({'ok': bool(new_trip), 'trip': new_trip, 'room': new_room, 'errors': errors or None}, status=status_code)


class TripUpdateView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        """Update an existing trip. Only the creator can update.
        Accepts partial fields. Frontend sends: id, name, origin, destination,
        start_date, end_date, budget_min, budget_max, status, room_type,
        season, country, max_participants, image_url, creator_id.
        """
        try:
            admin = get_supabase_admin()
            payload = request.data or {}
            trip_id = payload.get('id')
            creator_id = str(payload.get('creator_id') or '')
            if not trip_id:
                return Response({'ok': False, 'error': 'id requerido'}, status=status.HTTP_400_BAD_REQUEST)
            if not creator_id:
                return Response({'ok': False, 'error': 'creator_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch existing trip
            trip_resp = admin.table('trips').select('*').eq('id', trip_id).limit(1).execute()
            current = (getattr(trip_resp, 'data', None) or [None])[0]
            if not current:
                return Response({'ok': False, 'error': 'Viaje no encontrado'}, status=status.HTTP_404_NOT_FOUND)
            if str(current.get('creator_id') or '') != creator_id:
                return Response({'ok': False, 'error': 'Solo el creador puede actualizar este viaje'}, status=status.HTTP_403_FORBIDDEN)

            # Build update payload (only provided fields)
            update_row = {}
            def set_if_present(key_db, key_payload, coerce=None):
                val = payload.get(key_payload)
                if val is None:
                    return
                if isinstance(val, str) and val.strip() == '':
                    update_row[key_db] = None
                    return
                try:
                    update_row[key_db] = coerce(val) if coerce else val
                except Exception:
                    update_row[key_db] = val

            set_if_present('name', 'name')
            set_if_present('origin', 'origin')
            set_if_present('destination', 'destination')
            # Handle start_date - try both column names for compatibility
            sd = payload.get('start_date')
            if sd is not None:
                if not (isinstance(sd, str) and sd.strip() == ''):
                    # Try to update both 'date' and 'start_date' columns
                    update_row['date'] = sd
                    update_row['start_date'] = sd
                else:
                    update_row['date'] = None
                    update_row['start_date'] = None
            set_if_present('end_date', 'end_date')
            set_if_present('country', 'country')
            set_if_present('budget_min', 'budget_min', float)
            set_if_present('budget_max', 'budget_max', float)
            set_if_present('currency', 'currency')
            set_if_present('room_type', 'room_type')
            set_if_present('season', 'season')
            set_if_present('max_participants', 'max_participants', int)
            set_if_present('image_url', 'image_url')
            # Transporte: usar columna transport_type (y tipo si existiera)
            if payload.get('transport_type') is not None:
                update_row['transport_type'] = payload.get('transport_type')
            elif payload.get('tipo') is not None:
                update_row['transport_type'] = payload.get('tipo')

            # Calcular estado automáticamente si se actualizan fechas
            if 'date' in update_row or 'end_date' in update_row:
                start_date = update_row.get('date') or current.get('date')
                end_date = update_row.get('end_date') or current.get('end_date')
                auto_status = calculate_trip_status(start_date, end_date)
                update_row['status'] = auto_status

            if not update_row:
                return Response({'ok': True, 'trip': current, 'message': 'Sin cambios'})

            # Apply update
            admin.table('trips').update(update_row).eq('id', trip_id).execute()
            # Fetch updated row
            updated_resp = admin.table('trips').select('*').eq('id', trip_id).limit(1).execute()
            updated = (getattr(updated_resp, 'data', None) or [None])[0]

            # Try to keep chat room name in sync if trip name changed
            try:
                if 'name' in update_row:
                    rooms = admin.table('chat_rooms').select('id').eq('trip_id', trip_id).limit(1).execute()
                    room = (getattr(rooms, 'data', None) or [None])[0]
                    if room and room.get('id'):
                        admin.table('chat_rooms').update({'name': f"Chat {update_row['name'] or ''}"}).eq('id', room['id']).execute()
            except Exception:
                pass

            return Response({'ok': True, 'trip': updated or current})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ListTripsView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            trips_resp = admin.table('trips').select('*').order('created_at', desc=True).execute()
            trips = getattr(trips_resp, 'data', []) or []

            # Attach current_participants count for each trip (best-effort)
            enriched = []
            for t in trips:
                current_count = None
                # 1) Intentar contar miembros del chat grupal (no depende de que el usuario sea miembro)
                try:
                    room_resp = admin.table('chat_rooms').select('id').eq('trip_id', t.get('id')).eq('is_group', True).limit(1).execute()
                    room = (getattr(room_resp, 'data', None) or [None])[0]
                    if room and room.get('id'):
                        mem_resp = admin.table('chat_members').select('id', count='exact').eq('room_id', room['id']).execute()
                        count = getattr(mem_resp, 'count', None)
                        if isinstance(count, int):
                            current_count = count
                except Exception:
                    current_count = None

                # 2) Si falló o no hay sala, contar trip_members como respaldo
                if current_count is None:
                    try:
                        c_resp = admin.table('trip_members').select('id', count='exact').eq('trip_id', t.get('id')).execute()
                        current = getattr(c_resp, 'count', None)
                        if isinstance(current, int):
                            current_count = current
                    except Exception:
                        current_count = None

                if isinstance(current_count, int):
                    # Guardar en ambos formatos por compatibilidad con el frontend
                    t = { **t, 'current_participants': current_count, 'currentParticipants': current_count }

                enriched.append(t)

            return Response({'ok': True, 'trips': enriched})
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
            trip_resp = admin.table('trips').select('id,name,creator_id,max_participants').eq('id', trip_id).limit(1).execute()
            trip = (getattr(trip_resp, 'data', None) or [None])[0]
            if not trip:
                return Response({'ok': False, 'error': 'Viaje no encontrado'}, status=status.HTTP_404_NOT_FOUND)

            # Intentar encontrar sala grupal por trip_id
            room = None
            try:
                rooms = admin.table('chat_rooms').select('*').eq('trip_id', trip_id).eq('is_group', True).limit(1).execute()
                room = (getattr(rooms, 'data', None) or [None])[0]
            except Exception:
                room = None

            # Si no existe, intentar localizar por nombre/creador y asignar trip_id y is_group (no crear una nueva)
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
                        admin.table('chat_rooms').update({'trip_id': trip_id, 'is_group': True}).eq('id', guessed['id']).execute()
                        room = guessed | {'trip_id': trip_id, 'is_group': True}
                    except Exception:
                        room = guessed
                else:
                    return Response({'ok': False, 'error': 'No hay sala para este viaje'}, status=status.HTTP_404_NOT_FOUND)

            # Enforce capacity: count current members and compare
            try:
                members_count_resp = admin.table('trip_members').select('id', count='exact').eq('trip_id', trip_id).execute()
                current = getattr(members_count_resp, 'count', None)
                cap = trip.get('max_participants') if trip else None
                if isinstance(cap, int) and cap > 0 and isinstance(current, int) and current >= cap:
                    return Response({'ok': False, 'error': 'El viaje alcanzó el máximo de participantes'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception:
                pass

            # Crear membresía
            try:
                admin.table('chat_members').insert({ 'room_id': room['id'], 'user_id': user_id, 'role': 'member' }).execute()
            except Exception:
                pass
            # Crear membresía en trip_members también
            try:
                admin.table('trip_members').insert({ 'trip_id': trip_id, 'user_id': str(user_id), 'role': 'member' }).execute()
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


class ChatMembersView(APIView):
    """Endpoint para obtener miembros de un chat usando admin de Supabase (bypass RLS)"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            print(f"🔍 ChatMembersView: Received request with room_id={request.query_params.get('room_id')}")
            
            admin = get_supabase_admin()
            room_id = request.query_params.get('room_id')
            
            if not room_id:
                print("❌ ChatMembersView: No room_id provided")
                return Response({'ok': False, 'error': 'room_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
            
            print(f"🔍 ChatMembersView: Querying chat_members for room_id={room_id}")
            
            # Get chat members for this room using admin (bypasses RLS)
            members_resp = admin.table('chat_members').select('*').eq('room_id', room_id).execute()
            members = getattr(members_resp, 'data', []) or []
            
            print(f"🔍 ChatMembersView: Found {len(members)} members")
            
            # Get user names for the members
            user_ids = [m.get('user_id') for m in members if m.get('user_id')]
            name_map = {}
            if user_ids:
                try:
                    print(f"🔍 ChatMembersView: Fetching names for user_ids={user_ids}")
                    users_resp = admin.table('User').select('userid,nombre,apellido').in_('userid', user_ids).execute()
                    users = getattr(users_resp, 'data', []) or []
                    for user in users:
                        full_name = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip()
                        if full_name:
                            name_map[user.get('userid')] = full_name
                    print(f"🔍 ChatMembersView: Name map={name_map}")
                except Exception as e:
                    print(f"❌ ChatMembersView: Error fetching user names: {e}")
            
            # Enrich members with names
            enriched_members = []
            for member in members:
                user_id = member.get('user_id')
                name = name_map.get(user_id, 'Usuario')
                enriched_members.append({
                    'user_id': user_id,
                    'role': member.get('role'),
                    'name': name
                })
            
            print(f"🔍 ChatMembersView: Returning {len(enriched_members)} enriched members")
            return Response({'ok': True, 'members': enriched_members, 'count': len(enriched_members)})
        except Exception as e:
            print(f"❌ ChatMembersView: Exception occurred: {str(e)}")
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TestEndpointView(APIView):
    """Endpoint de prueba para diagnosticar problemas de conectividad"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        print("🔍 TestEndpointView: Received GET request")
        return Response({
            'ok': True, 
            'message': 'Test endpoint working',
            'timestamp': str(datetime.now()),
            'headers': dict(request.headers)
        })

    def post(self, request, *args, **kwargs):
        print("🔍 TestEndpointView: Received POST request")
        return Response({
            'ok': True, 
            'message': 'Test endpoint working',
            'data': request.data,
            'timestamp': str(datetime.now())
        })


class DebugChatMembersView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            room_id = request.query_params.get('room_id')
            
            if room_id == 'all':
                # List all chat rooms
                rooms_resp = admin.table('chat_rooms').select('*').execute()
                rooms = getattr(rooms_resp, 'data', []) or []
                return Response({'ok': True, 'rooms': rooms, 'count': len(rooms)})
            
            if not room_id:
                return Response({'ok': False, 'error': 'room_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get chat members for this room
            print(f"🔍 DebugChatMembersView: room_id={room_id}")
            members_resp = admin.table('chat_members').select('*').eq('room_id', room_id).execute()
            members = getattr(members_resp, 'data', []) or []
            print(f"🔍 DebugChatMembersView: found {len(members)} members")
            
            return Response({'ok': True, 'members': members, 'count': len(members)})
        except Exception as e:
            print(f"🔍 DebugChatMembersView error: {str(e)}")
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            room_id = request.data.get('room_id')
            user_id = request.data.get('user_id')
            role = request.data.get('role', 'member')
            
            if not room_id or not user_id:
                return Response({'ok': False, 'error': 'room_id y user_id requeridos'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Try to insert member
            try:
                result = admin.table('chat_members').insert({
                    'room_id': room_id,
                    'user_id': user_id,
                    'role': role
                }).execute()
                
                return Response({'ok': True, 'result': result.data if hasattr(result, 'data') else 'inserted'})
            except Exception as insert_error:
                return Response({'ok': False, 'error': f'Error inserting: {str(insert_error)}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CreateReviewView(APIView):
    """Vista para crear una nueva reseña"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            reviewer_id = request.data.get('reviewer_id')
            reviewed_user_id = request.data.get('reviewed_user_id')
            rating = request.data.get('rating')
            comment = request.data.get('comment', '')

            if not reviewer_id or not reviewed_user_id or not rating:
                return Response({
                    'ok': False, 
                    'error': 'reviewer_id, reviewed_user_id y rating son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Verificar que los usuarios existan en Supabase
            admin = get_supabase_admin()
            schema = environ.get('SUPABASE_SCHEMA', 'public')
            table = environ.get('SUPABASE_USERS_TABLE', 'User')
            
            try:
                # Verificar reviewer
                reviewer_resp = admin.schema(schema).table(table).select('userid').eq('userid', str(reviewer_id)).limit(1).execute()
                reviewer_data = (getattr(reviewer_resp, 'data', None) or [None])[0]
                
                # Verificar reviewed_user
                reviewed_resp = admin.schema(schema).table(table).select('userid').eq('userid', str(reviewed_user_id)).limit(1).execute()
                reviewed_data = (getattr(reviewed_resp, 'data', None) or [None])[0]
                
                if not reviewer_data or not reviewed_data:
                    return Response({
                        'ok': False, 
                        'error': 'Usuario no encontrado'
                    }, status=status.HTTP_404_NOT_FOUND)
                    
            except Exception as e:
                return Response({
                    'ok': False, 
                    'error': f'Error verificando usuarios: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Verificar que no se esté autoreseñando
            if reviewer_id == reviewed_user_id:
                return Response({
                    'ok': False, 
                    'error': 'No puedes dejarte una reseña a ti mismo'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Crear o obtener usuarios Django basados en IDs de Supabase
            reviewer, _ = User.objects.get_or_create(
                id=reviewer_id,
                defaults={
                    'email': f'{reviewer_id}@temp.com',
                    'first_name': 'Usuario',
                    'last_name': 'Temporal',
                    'document_number': reviewer_id[:8],
                    'sex': 'M',
                    'birth_date': '1990-01-01',
                    'age': 30
                }
            )
            
            reviewed_user, _ = User.objects.get_or_create(
                id=reviewed_user_id,
                defaults={
                    'email': f'{reviewed_user_id}@temp.com',
                    'first_name': 'Usuario',
                    'last_name': 'Temporal',
                    'document_number': reviewed_user_id[:8],
                    'sex': 'M',
                    'birth_date': '1990-01-01',
                    'age': 30
                }
            )

            # Verificar que no exista ya una reseña
            existing_review = Review.objects.filter(
                reviewer=reviewer, 
                reviewed_user=reviewed_user
            ).first()

            if existing_review:
                # Actualizar reseña existente
                existing_review.rating = rating
                existing_review.comment = comment
                existing_review.save()
                serializer = ReviewSerializer(existing_review)
                return Response({
                    'ok': True, 
                    'review': serializer.data,
                    'message': 'Reseña actualizada exitosamente'
                })
            else:
                # Crear nueva reseña
                review = Review.objects.create(
                    reviewer=reviewer,
                    reviewed_user=reviewed_user,
                    rating=rating,
                    comment=comment
                )
                serializer = ReviewSerializer(review)
                return Response({
                    'ok': True, 
                    'review': serializer.data,
                    'message': 'Reseña creada exitosamente'
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class GetUserAvatarView(APIView):
    """Vista para obtener el avatar_url de un usuario específico"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({
                    'ok': False, 
                    'error': 'user_id requerido'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Obtener avatar_url desde Supabase Auth usando admin
            admin = get_supabase_admin()
            try:
                user_resp = admin.auth.admin.get_user_by_id(user_id)
                avatar_url = user_resp.user.user_metadata.get('avatar_url', '') if user_resp.user else ''
                
                return Response({
                    'ok': True,
                    'avatar_url': avatar_url
                })
            except Exception as e:
                return Response({
                    'ok': False, 
                    'error': f'Error obteniendo avatar: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class GetUserReviewsView(APIView):
    """Vista para obtener las reseñas de un usuario específico"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            user_id = request.query_params.get('user_id')
            
            if not user_id:
                return Response({
                    'ok': False, 
                    'error': 'user_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Verificar que el usuario exista en Supabase
            admin = get_supabase_admin()
            schema = environ.get('SUPABASE_SCHEMA', 'public')
            table = environ.get('SUPABASE_USERS_TABLE', 'User')
            
            try:
                user_resp = admin.schema(schema).table(table).select('userid').eq('userid', str(user_id)).limit(1).execute()
                user_data = (getattr(user_resp, 'data', None) or [None])[0]
                
                if not user_data:
                    return Response({
                        'ok': False, 
                        'error': 'Usuario no encontrado'
                    }, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return Response({
                    'ok': False, 
                    'error': f'Error verificando usuario: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Crear o obtener usuario Django si no existe
            user, _ = User.objects.get_or_create(
                id=user_id,
                defaults={
                    'email': f'{user_id}@temp.com',
                    'first_name': 'Usuario',
                    'last_name': 'Temporal',
                    'document_number': user_id[:8],
                    'sex': 'M',
                    'birth_date': '1990-01-01',
                    'age': 30
                }
            )

            # Obtener todas las reseñas del usuario
            reviews = Review.objects.filter(reviewed_user=user).select_related('reviewer')
            serializer = ReviewSerializer(reviews, many=True)

            # Calcular estadísticas
            total_reviews = reviews.count()
            avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
            avg_rating = round(avg_rating, 1) if avg_rating else 0

            # Contar reseñas por rating
            rating_distribution = {}
            for i in range(1, 6):
                rating_distribution[str(i)] = reviews.filter(rating=i).count()

            return Response({
                'ok': True,
                'reviews': serializer.data,
                'statistics': {
                    'total_reviews': total_reviews,
                    'average_rating': avg_rating,
                    'rating_distribution': rating_distribution
                }
            })

        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class GetUserProfileView(APIView):
    """Vista para obtener el perfil completo de un usuario incluyendo sus reseñas"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            user_id = request.query_params.get('user_id')
            
            if not user_id:
                return Response({
                    'ok': False, 
                    'error': 'user_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Obtener información del usuario desde Supabase
            admin = get_supabase_admin()
            schema = environ.get('SUPABASE_SCHEMA', 'public')
            table = environ.get('SUPABASE_USERS_TABLE', 'User')
            
            user_resp = admin.schema(schema).table(table).select('*').eq('userid', str(user_id)).limit(1).execute()
            user_data = (getattr(user_resp, 'data', None) or [None])[0]
            
            if not user_data:
                return Response({
                    'ok': False, 
                    'error': 'Usuario no encontrado'
                }, status=status.HTTP_404_NOT_FOUND)

            # Obtener reseñas del usuario desde Django
            try:
                # Crear o obtener usuario Django si no existe
                django_user, _ = User.objects.get_or_create(
                    id=user_id,
                    defaults={
                        'email': f'{user_id}@temp.com',
                        'first_name': 'Usuario',
                        'last_name': 'Temporal',
                        'document_number': user_id[:8],
                        'sex': 'M',
                        'birth_date': '1990-01-01',
                        'age': 30
                    }
                )
                
                reviews = Review.objects.filter(reviewed_user=django_user).select_related('reviewer')
                reviews_serializer = ReviewSerializer(reviews, many=True)

                # Calcular estadísticas
                total_reviews = reviews.count()
                avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
                avg_rating = round(avg_rating, 1) if avg_rating else 0

                # Contar reseñas por rating
                rating_distribution = {}
                for i in range(1, 6):
                    rating_distribution[str(i)] = reviews.filter(rating=i).count()

                # Calcular nivel de confianza (0-100) ponderado por cantidad de reseñas
                # Fórmula simple: confianza = (avg/5) * (1 - e^(-n/10)) * 100
                confidence = 0
                try:
                    confidence = int(round((avg_rating / 5.0) * (1 - math.e ** (-(total_reviews / 10.0))) * 100))
                except Exception:
                    confidence = 0
                
                reviews_data = {
                    'reviews': reviews_serializer.data,
                    'statistics': {
                        'total_reviews': total_reviews,
                        'average_rating': avg_rating,
                        'rating_distribution': rating_distribution,
                        'trust_level': confidence
                    }
                }
            except User.DoesNotExist:
                # Si el usuario no existe en Django, crear datos vacíos para las reseñas
                reviews_data = {
                    'reviews': [],
                    'statistics': {
                        'total_reviews': 0,
                        'average_rating': 0,
                        'rating_distribution': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0},
                        'trust_level': 0
                    }
                }

            # Historial de viajes (creados y participados) desde Django
            created_trips = Trip.objects.filter(creator_id=user_id).order_by('-created_at')[:20]
            participating_trip_ids = TripParticipant.objects.filter(user_id=user_id).values_list('trip_id', flat=True)
            participating_trips = Trip.objects.filter(id__in=participating_trip_ids).exclude(creator_id=user_id).order_by('-created_at')[:20]
            
            def serialize_trip_min(trip):
                return {
                    'id': trip.id,
                    'name': trip.name,
                    'origin': trip.origin,
                    'destination': trip.destination,
                    'start_date': trip.start_date,
                    'end_date': trip.end_date,
                    'travel_style': trip.travel_style,
                    'transport_type': trip.transport_type,
                    'budget_min': trip.budget_min,
                    'budget_max': trip.budget_max,
                    'status': trip.status,
                }
            
            trips_history = {
                'created': [serialize_trip_min(t) for t in created_trips],
                'participated': [serialize_trip_min(t) for t in participating_trips],
            }
            
            return Response({
                'ok': True,
                'user': user_data,
                'reviews_data': reviews_data,
                'trips_history': trips_history,
            })

        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


# --- Applications flow using Supabase public.applications table ---

class ApplicationCreateSupabaseView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        """Create an application row and a private chat between organizer and applicant.
        Expects: trip_id (uuid), applicant_id (uuid), message (optional)
        """
        try:
            admin = get_supabase_admin()
            trip_id = request.data.get('trip_id')
            applicant_id = request.data.get('applicant_id') or request.data.get('user_id')
            message = (request.data.get('message') or '').strip()
            if not trip_id or not applicant_id:
                return Response({'ok': False, 'error': 'trip_id y applicant_id requeridos'}, status=status.HTTP_400_BAD_REQUEST)

            # Read trip to get organizer and name
            trip_resp = admin.table('trips').select('id,name,creator_id').eq('id', trip_id).limit(1).execute()
            trip = (getattr(trip_resp, 'data', None) or [None])[0]
            if not trip:
                return Response({'ok': False, 'error': 'Viaje no encontrado'}, status=status.HTTP_404_NOT_FOUND)

            # Check if application already exists (pending)
            existing_app = None
            try:
                existing_resp = admin.table('applications').select('*').eq('trip_id', trip_id).eq('applicant_id', str(applicant_id)).eq('status', 'pending').limit(1).execute()
                existing_app = (getattr(existing_resp, 'data', None) or [None])[0]
            except Exception:
                pass

            # Reuse existing application or create new one
            if existing_app:
                application = existing_app
            else:
                app_payload = {
                    'trip_id': trip_id,
                    'applicant_id': str(applicant_id),
                    'status': 'pending',
                }
                if message:
                    app_payload['message'] = message
                try:
                    app_resp = admin.table('applications').insert(app_payload).execute()
                    application = (getattr(app_resp, 'data', None) or [None])[0]
                    if not application:
                        return Response({'ok': False, 'error': 'No se pudo crear la aplicación'}, status=status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    # If still getting unique constraint error, try fetching again
                    if '23505' in str(e) or 'unique' in str(e).lower():
                        try:
                            existing_resp = admin.table('applications').select('*').eq('trip_id', trip_id).eq('applicant_id', str(applicant_id)).eq('status', 'pending').limit(1).execute()
                            application = (getattr(existing_resp, 'data', None) or [None])[0]
                            if not application:
                                return Response({'ok': False, 'error': 'No se pudo crear la aplicación'}, status=status.HTTP_400_BAD_REQUEST)
                        except Exception:
                            return Response({'ok': False, 'error': f'Error al crear aplicación: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({'ok': False, 'error': f'Error al crear aplicación: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

            # Find or create a private room between organizer and applicant using direct_conversations
            organizer_id = str(trip.get('creator_id') or '')
            user_a = organizer_id if organizer_id < str(applicant_id) else str(applicant_id)
            user_b = str(applicant_id) if organizer_id < str(applicant_id) else organizer_id
            
            room = None
            try:
                # Check if conversation already exists
                conv_resp = admin.table('direct_conversations').select('*').eq('user_a', user_a).eq('user_b', user_b).limit(1).execute()
                conv = (getattr(conv_resp, 'data', None) or [None])[0]
                
                if conv and conv.get('room_id'):
                    # Fetch existing room
                    room_resp = admin.table('chat_rooms').select('*').eq('id', conv['room_id']).limit(1).execute()
                    room = (getattr(room_resp, 'data', None) or [None])[0]
                    
                    # Always update room with current trip_id and application_id
                    try:
                        updates = {
                            'application_id': application['id'],
                            'trip_id': trip_id,
                        }
                        admin.table('chat_rooms').update(updates).eq('id', room['id']).execute()
                        for k, v in updates.items():
                            room[k] = v
                    except Exception:
                        pass
                    
                    # Ensure both users are members (in case membership was deleted or incomplete)
                    if room:
                        try:
                            # Check existing memberships
                            existing_mems = admin.table('chat_members').select('user_id').eq('room_id', room['id']).execute()
                            existing_ids = {str(m.get('user_id')) for m in (getattr(existing_mems, 'data', []) or [])}
                            
                            # Add missing members
                            members_to_add = []
                            if str(organizer_id) not in existing_ids:
                                members_to_add.append({ 'room_id': room['id'], 'user_id': organizer_id, 'role': 'owner' })
                            if str(applicant_id) not in existing_ids:
                                members_to_add.append({ 'room_id': room['id'], 'user_id': str(applicant_id), 'role': 'member' })
                            
                            if members_to_add:
                                try:
                                    admin.table('chat_members').insert(members_to_add).execute()
                                except Exception:
                                    # Fallback: insert one by one
                                    for m in members_to_add:
                                        try:
                                            admin.table('chat_members').insert(m).execute()
                                        except Exception:
                                            pass
                        except Exception:
                            pass
                else:
                    # Create new private room
                    room_payload = {
                        'name': f"Privado: {trip.get('name')}",
                        'creator_id': organizer_id,
                        'trip_id': trip_id,
                        'application_id': application['id'],
                        'is_group': False,
                        'is_private': True,
                    }
                    try:
                        room_resp = admin.table('chat_rooms').insert(room_payload).execute()
                    except Exception:
                        # Fallback minimal set of columns
                        minimal = {k: room_payload[k] for k in ['name', 'creator_id', 'trip_id', 'application_id']}
                        room_resp = admin.table('chat_rooms').insert(minimal).execute()
                    room = (getattr(room_resp, 'data', None) or [None])[0]
                    
                    if room:
                        # Create direct_conversations entry
                        try:
                            admin.table('direct_conversations').insert({
                                'user_a': user_a,
                                'user_b': user_b,
                                'room_id': room['id']
                            }).execute()
                        except Exception:
                            pass
                        
                        # Add both users as members
                        members = [
                            { 'room_id': room['id'], 'user_id': organizer_id, 'role': 'owner' },
                            { 'room_id': room['id'], 'user_id': str(applicant_id), 'role': 'member' },
                        ]
                        try:
                            admin.table('chat_members').insert(members).execute()
                        except Exception:
                            for m in members:
                                try:
                                    admin.table('chat_members').insert(m).execute()
                                except Exception:
                                    pass
            except Exception:
                pass

            # Initial message from applicant (tagged so frontend can render actions inside the bubble)
            # Always send message if provided (even if reusing application/room)
            try:
                if room and message:
                    tagged = f"APP|{application['id']}|{message}"
                    admin.table('chat_messages').insert({
                        'room_id': room['id'],
                        'user_id': str(applicant_id),
                        'content': tagged,
                    }).execute()
            except Exception:
                pass

            # Crear notificación para el organizador
            try:
                # Obtener nombre del solicitante
                applicant_resp = admin.table('User').select('nombre, apellido').eq('userid', str(applicant_id)).limit(1).execute()
                applicant = (getattr(applicant_resp, 'data', None) or [None])[0]
                applicant_name = f"{applicant.get('nombre', '')} {applicant.get('apellido', '')}".strip() if applicant else 'Un usuario'
                
                # Crear notificación para el organizador
                notification_data = {
                    'user_id': organizer_id,
                    'type': 'trip_application',
                    'title': 'Nueva solicitud de viaje',
                    'message': f'{applicant_name} quiere unirse a tu viaje "{trip.get("name", "Sin nombre")}"',
                    'data': {
                        'trip_id': trip_id,
                        'applicant_id': str(applicant_id),
                        'application_id': application.get('id'),
                        'room_id': room.get('id') if room else None
                    }
                }
                
                admin.table('notifications').insert(notification_data).execute()
            except Exception as notification_error:
                # No fallar si la notificación no se puede crear
                print(f"Error creando notificación: {notification_error}")

            return Response({'ok': True, 'application': application, 'room_id': room.get('id') if room else None})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ApplicationRespondSupabaseView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        """Accept or reject an application.
        Expects: application_id (int), action ('accept'|'reject'), organizer_id (uuid)
        On accept: add applicant to trip_members and chat_members of the existing group chat room for the trip.
        """
        try:
            admin = get_supabase_admin()
            app_id = request.data.get('application_id') or request.data.get('id')
            action = (request.data.get('action') or '').strip().lower()
            organizer_id = str(request.data.get('organizer_id') or '')
            if not app_id or action not in ('accept', 'reject'):
                return Response({'ok': False, 'error': 'application_id y action requeridos'}, status=status.HTTP_400_BAD_REQUEST)

            # Load application and trip
            app_resp = admin.table('applications').select('*').eq('id', app_id).limit(1).execute()
            application = (getattr(app_resp, 'data', None) or [None])[0]
            if not application:
                return Response({'ok': False, 'error': 'Aplicación no encontrada'}, status=status.HTTP_404_NOT_FOUND)
            trip_id = application.get('trip_id')
            applicant_id = application.get('applicant_id')
            if not trip_id or not applicant_id:
                return Response({'ok': False, 'error': 'Aplicación inválida'}, status=status.HTTP_400_BAD_REQUEST)
            trip_resp = admin.table('trips').select('id,name,creator_id').eq('id', trip_id).limit(1).execute()
            trip = (getattr(trip_resp, 'data', None) or [None])[0]
            if not trip:
                return Response({'ok': False, 'error': 'Viaje no encontrado'}, status=status.HTTP_404_NOT_FOUND)

            # Verify organizer
            expected_org = str(trip.get('creator_id') or '')
            if organizer_id and organizer_id != expected_org:
                return Response({'ok': False, 'error': 'organizer_id inválido para esta aplicación'}, status=status.HTTP_403_FORBIDDEN)

            # Update application status
            new_status = 'accepted' if action == 'accept' else 'rejected'
            admin.table('applications').update({'status': new_status}).eq('id', app_id).execute()

            # Close private chat with a system message (best-effort)
            try:
                # Prefer room tied to this application id
                rcand = admin.table('chat_rooms').select('id,trip_id').eq('application_id', app_id).limit(1).execute()
                room = (getattr(rcand, 'data', None) or [None])[0]
                if not room:
                    # Fallback: find any private room for this trip including both participants
                    creator_id = expected_org
                    creator_rooms = admin.table('chat_members').select('room_id').eq('user_id', creator_id).execute()
                    applicant_rooms = admin.table('chat_members').select('room_id').eq('user_id', str(applicant_id)).execute()
                    creator_ids = {row['room_id'] for row in (getattr(creator_rooms, 'data', []) or []) if row and row.get('room_id')}
                    applicant_ids = {row['room_id'] for row in (getattr(applicant_rooms, 'data', []) or []) if row and row.get('room_id')}
                    common = list(creator_ids.intersection(applicant_ids))
                    if common:
                        r2 = (
                            admin.table('chat_rooms')
                            .select('id')
                            .in_('id', common)
                            .eq('trip_id', trip_id)
                            .limit(1)
                            .execute()
                        )
                        room = (getattr(r2, 'data', None) or [None])[0]
                if room:
                    # Send status marker message to drive frontend UI state (APP_STATUS)
                    marker = f"APP_STATUS|{app_id}|{'accepted' if action == 'accept' else 'rejected'}"
                    try:
                        admin.table('chat_messages').insert({
                            'room_id': room['id'],
                            'user_id': expected_org,
                            'content': marker,
                        }).execute()
                    except Exception:
                        # Fallback to plain text if needed
                        admin.table('chat_messages').insert({
                            'room_id': room['id'],
                            'user_id': expected_org,
                            'content': 'Aplicación aceptada' if action == 'accept' else 'Aplicación rechazada',
                        }).execute()
            except Exception:
                pass

            # Crear notificación para el solicitante
            try:
                # Obtener nombre del organizador
                organizer_resp = admin.table('User').select('nombre, apellido').eq('userid', expected_org).limit(1).execute()
                organizer = (getattr(organizer_resp, 'data', None) or [None])[0]
                organizer_name = f"{organizer.get('nombre', '')} {organizer.get('apellido', '')}".strip() if organizer else 'El organizador'
                
                if action == 'accept':
                    notification_data = {
                        'user_id': str(applicant_id),
                        'type': 'trip_application_accepted',
                        'title': '¡Solicitud aceptada!',
                        'message': f'{organizer_name} aceptó tu solicitud para el viaje "{trip.get("name", "Sin nombre")}"',
                        'data': {
                            'trip_id': trip_id,
                            'organizer_id': expected_org,
                            'application_id': app_id
                        }
                    }
                else:
                    notification_data = {
                        'user_id': str(applicant_id),
                        'type': 'trip_application_rejected',
                        'title': 'Solicitud rechazada',
                        'message': f'{organizer_name} rechazó tu solicitud para el viaje "{trip.get("name", "Sin nombre")}"',
                        'data': {
                            'trip_id': trip_id,
                            'organizer_id': expected_org,
                            'application_id': app_id
                        }
                    }
                
                admin.table('notifications').insert(notification_data).execute()
            except Exception as notification_error:
                # No fallar si la notificación no se puede crear
                print(f"Error creando notificación: {notification_error}")

            if action == 'reject':
                return Response({'ok': True, 'status': 'rejected'})

            # On accept: add applicant to group chat and trip membership
            # 1) Find group chat room (created at trip creation, marked as is_group=true)
            group_room = None
            try:
                gr = admin.table('chat_rooms').select('*').eq('trip_id', trip_id).eq('is_group', True).limit(1).execute()
                group_room = (getattr(gr, 'data', None) or [None])[0]
                if not group_room:
                    # Fallback by name and mark as group if found
                    gr2 = admin.table('chat_rooms').select('*').eq('name', f"Chat {trip.get('name')}").limit(1).execute()
                    group_room = (getattr(gr2, 'data', None) or [None])[0]
                    if group_room:
                        try:
                            admin.table('chat_rooms').update({'is_group': True, 'trip_id': trip_id}).eq('id', group_room['id']).execute()
                            group_room['is_group'] = True
                            group_room['trip_id'] = trip_id
                        except Exception:
                            pass
            except Exception:
                group_room = None

            # 2) Add to chat_members
            try:
                if group_room and group_room.get('id'):
                    admin.table('chat_members').insert({ 'room_id': group_room['id'], 'user_id': str(applicant_id), 'role': 'member' }).execute()
            except Exception:
                pass

            # 3) Add to trip_members
            try:
                admin.table('trip_members').insert({ 'trip_id': trip_id, 'user_id': str(applicant_id), 'role': 'member' }).execute()
            except Exception:
                pass

            return Response({'ok': True, 'status': 'accepted'})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TripHistoryView(APIView):
    """Endpoint para obtener el historial de viajes de un usuario"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            user_id = request.query_params.get('user_id')
            
            if not user_id:
                return Response({'ok': False, 'error': 'user_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get trip history for the user
            history_resp = admin.table('trip_history').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
            history = getattr(history_resp, 'data', []) or []
            
            # Get trip details for each history entry
            enriched_history = []
            for entry in history:
                try:
                    # Get trip details
                    trip_resp = admin.table('trips').select('*').eq('id', entry.get('trip_id')).limit(1).execute()
                    trip = (getattr(trip_resp, 'data', None) or [None])[0]
                    
                    if trip:
                        enriched_entry = {
                            'id': entry.get('id'),
                            'trip_id': entry.get('trip_id'),
                            'role': entry.get('role'),
                            'status': entry.get('status'),
                            'joined_at': entry.get('joined_at'),
                            'left_at': entry.get('left_at'),
                            'rating_given': entry.get('rating_given'),
                            'review_text': entry.get('review_text'),
                            'created_at': entry.get('created_at'),
                            'trip_details': {
                                'name': trip.get('name'),
                                'origin': trip.get('origin'),
                                'destination': trip.get('destination'),
                                'date': trip.get('date'),
                                'country': trip.get('country'),
                                'image_url': trip.get('image_url')
                            }
                        }
                        enriched_history.append(enriched_entry)
                except Exception as e:
                    print(f"Error enriching trip history entry: {e}")
                    continue
            
            return Response({'ok': True, 'history': enriched_history, 'count': len(enriched_history)})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CompleteTripView(APIView):
    """Endpoint para marcar un viaje como completado y agregar todos los participantes al historial"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            payload = request.data or {}
            trip_id = payload.get('trip_id')
            creator_id = payload.get('creator_id')
            
            if not trip_id:
                return Response({'ok': False, 'error': 'trip_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
            if not creator_id:
                return Response({'ok': False, 'error': 'creator_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Verificar que el usuario es el creador del viaje
            trip_resp = admin.table('trips').select('creator_id').eq('id', trip_id).limit(1).execute()
            trip = (getattr(trip_resp, 'data', None) or [None])[0]
            if not trip or str(trip.get('creator_id')) != str(creator_id):
                return Response({'ok': False, 'error': 'Solo el creador puede marcar el viaje como completado'}, status=status.HTTP_403_FORBIDDEN)
            
            # Buscar el chat GRUPAL del viaje (no los chats privados)
            chat_resp = admin.table('chat_rooms').select('id').eq('trip_id', trip_id).eq('is_group', True).limit(1).execute()
            chat_room = (getattr(chat_resp, 'data', None) or [None])[0]
            
            if chat_room:
                # Obtener miembros del chat
                members_resp = admin.table('chat_members').select('user_id, role').eq('room_id', chat_room.get('id')).execute()
                members = getattr(members_resp, 'data', []) or []
            else:
                members = []
            
            # Agregar cada miembro al historial de viajes
            history_entries = []
            for member in members:
                try:
                    # Mapear role de chat_members a trip_history
                    member_role = member.get('role')
                    if member_role == 'owner':
                        history_role = 'organizer'
                    else:
                        history_role = 'member'
                        
                    history_entry = {
                        'user_id': member.get('user_id'),
                        'trip_id': trip_id,
                        'role': history_role,
                        'status': 'completed',
                        'joined_at': trip.get('date'),  # Usar la fecha del viaje como fecha de unión
                        'left_at': None,
                        'rating_given': None,
                        'review_text': None
                    }
                    history_entries.append(history_entry)
                except Exception as e:
                    print(f"Error creating history entry for user {member.get('user_id')}: {e}")
                    continue
            
            # Insertar todas las entradas del historial
            if history_entries:
                admin.table('trip_history').insert(history_entries).execute()
            
            # Actualizar el estado del viaje a completado
            admin.table('trips').update({'status': 'completed'}).eq('id', trip_id).execute()
            
            return Response({
                'ok': True, 
                'message': f'Viaje marcado como completado. {len(history_entries)} participantes agregados al historial.',
                'participants_added': len(history_entries)
            })
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RateTripView(APIView):
    """Endpoint para calificar y reseñar un viaje completado"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            payload = request.data or {}
            user_id = payload.get('user_id')
            trip_id = payload.get('trip_id')
            rating = payload.get('rating')
            review_text = payload.get('review_text', '')
            
            if not user_id:
                return Response({'ok': False, 'error': 'user_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
            if not trip_id:
                return Response({'ok': False, 'error': 'trip_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
            if not rating:
                return Response({'ok': False, 'error': 'rating requerido'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Validar rating
            try:
                rating = int(rating)
                if rating < 1 or rating > 5:
                    return Response({'ok': False, 'error': 'Rating debe estar entre 1 y 5'}, status=status.HTTP_400_BAD_REQUEST)
            except ValueError:
                return Response({'ok': False, 'error': 'Rating debe ser un número'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Verificar que el usuario participó en el viaje
            history_resp = admin.table('trip_history').select('*').eq('user_id', user_id).eq('trip_id', trip_id).eq('status', 'completed').limit(1).execute()
            history_entry = (getattr(history_resp, 'data', None) or [None])[0]
            
            if not history_entry:
                return Response({'ok': False, 'error': 'No se encontró el viaje en tu historial'}, status=status.HTTP_404_NOT_FOUND)
            
            # Actualizar la entrada del historial con la calificación
            update_data = {
                'rating_given': rating,
                'review_text': review_text.strip() if review_text else None,
                'updated_at': 'now()'
            }
            
            admin.table('trip_history').update(update_data).eq('id', history_entry.get('id')).execute()
            
            return Response({
                'ok': True, 
                'message': 'Calificación y reseña guardadas exitosamente'
            })
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AutoCompleteTripsView(APIView):
    """Endpoint para marcar automáticamente viajes como completados cuando pasen las fechas"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            
            # Obtener todos los viajes que deberían estar completados
            today = date.today()
            
            # Buscar viajes activos o próximos que ya deberían estar completados
            trips_resp = admin.table('trips').select('*').in_('status', ['active', 'upcoming']).execute()
            trips = getattr(trips_resp, 'data', []) or []
            
            completed_trips = []
            
            for trip in trips:
                try:
                    # Verificar si el viaje debería estar completado
                    start_date = trip.get('date')
                    end_date = trip.get('end_date')
                    
                    if not start_date:
                        continue
                    
                    # Convertir fechas
                    if isinstance(start_date, str):
                        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00')).date()
                    elif isinstance(start_date, datetime):
                        start_date = start_date.date()
                    
                    should_be_completed = False
                    
                    if end_date:
                        if isinstance(end_date, str):
                            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
                        elif isinstance(end_date, datetime):
                            end_date = end_date.date()
                        
                        # Si la fecha de fin ya pasó
                        if today > end_date:
                            should_be_completed = True
                    else:
                        # Si no hay fecha de fin, usar la fecha de inicio
                        if today > start_date:
                            should_be_completed = True
                    
                    if should_be_completed:
                        # Marcar como completado
                        admin.table('trips').update({'status': 'completed'}).eq('id', trip.get('id')).execute()
                        
                        # Buscar el chat GRUPAL del viaje (no los chats privados)
                        chat_resp = admin.table('chat_rooms').select('id').eq('trip_id', trip.get('id')).eq('is_group', True).limit(1).execute()
                        chat_room = (getattr(chat_resp, 'data', None) or [None])[0]
                        
                        if chat_room:
                            # Obtener miembros del chat
                            members_resp = admin.table('chat_members').select('user_id, role').eq('room_id', chat_room.get('id')).execute()
                            members = getattr(members_resp, 'data', []) or []
                        else:
                            members = []
                        
                        history_entries = []
                        for member in members:
                            # Mapear role de chat_members a trip_history
                            member_role = member.get('role')
                            if member_role == 'owner':
                                history_role = 'organizer'
                            else:
                                history_role = 'member'
                                
                            history_entry = {
                                'user_id': member.get('user_id'),
                                'trip_id': trip.get('id'),
                                'role': history_role,
                                'status': 'completed',
                                'joined_at': start_date.isoformat(),
                                'left_at': None,
                                'rating_given': None,
                                'review_text': None
                            }
                            history_entries.append(history_entry)
                        
                        if history_entries:
                            admin.table('trip_history').insert(history_entries).execute()
                        
                        completed_trips.append({
                            'id': trip.get('id'),
                            'name': trip.get('name'),
                            'participants_added': len(history_entries)
                        })
                        
                except Exception as e:
                    print(f"Error processing trip {trip.get('id')}: {e}")
                    continue
            
            return Response({
                'ok': True,
                'message': f'Procesados {len(completed_trips)} viajes completados automáticamente',
                'completed_trips': completed_trips
            })
            
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UpdateTripDatesView(APIView):
    """Endpoint para actualizar fechas de viajes (para testing)"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            payload = request.data or {}
            trip_id = payload.get('trip_id')
            start_date = payload.get('start_date')
            end_date = payload.get('end_date')
            
            if not trip_id:
                return Response({'ok': False, 'error': 'trip_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Verificar que el viaje existe
            trip_resp = admin.table('trips').select('*').eq('id', trip_id).limit(1).execute()
            trip = (getattr(trip_resp, 'data', None) or [None])[0]
            if not trip:
                return Response({'ok': False, 'error': 'Viaje no encontrado'}, status=status.HTTP_404_NOT_FOUND)
            
            # Preparar actualización
            update_data = {}
            
            if start_date:
                update_data['date'] = start_date
                update_data['start_date'] = start_date
                
            if end_date:
                update_data['end_date'] = end_date
                
            # Recalcular estado automáticamente
            if start_date or end_date:
                final_start = start_date or trip.get('start_date') or trip.get('date')
                final_end = end_date or trip.get('end_date')
                auto_status = calculate_trip_status(final_start, final_end)
                update_data['status'] = auto_status
            
            # Aplicar actualización
            if update_data:
                admin.table('trips').update(update_data).eq('id', trip_id).execute()
                
                # Si el viaje se marcó como completado automáticamente, agregar al historial
                if update_data.get('status') == 'completed':
                    # Buscar el chat GRUPAL del viaje (no los chats privados)
                    chat_resp = admin.table('chat_rooms').select('id').eq('trip_id', trip_id).eq('is_group', True).limit(1).execute()
                    chat_room = (getattr(chat_resp, 'data', None) or [None])[0]
                    
                    if chat_room:
                        # Obtener miembros del chat
                        members_resp = admin.table('chat_members').select('user_id, role').eq('room_id', chat_room.get('id')).execute()
                        members = getattr(members_resp, 'data', []) or []
                    else:
                        members = []
                    
                    # Verificar qué miembros ya están en el historial
                    existing_history_resp = admin.table('trip_history').select('user_id').eq('trip_id', trip_id).execute()
                    existing_user_ids = set([entry.get('user_id') for entry in (getattr(existing_history_resp, 'data', []) or [])])
                    
                    history_entries = []
                    for member in members:
                        user_id = member.get('user_id')
                        
                        # Solo agregar si no está ya en el historial
                        if user_id not in existing_user_ids:
                            # Mapear role de chat_members a trip_history
                            member_role = member.get('role')
                            if member_role == 'owner':
                                history_role = 'organizer'
                            else:
                                history_role = 'member'
                                
                            history_entry = {
                                'user_id': user_id,
                                'trip_id': trip_id,
                                'role': history_role,
                                'status': 'completed',
                                'joined_at': final_start,
                                'left_at': None,
                                'rating_given': None,
                                'review_text': None
                            }
                            history_entries.append(history_entry)
                    
                    if history_entries:
                        admin.table('trip_history').insert(history_entries).execute()
                
                return Response({
                    'ok': True,
                    'message': 'Fechas actualizadas exitosamente',
                    'new_status': update_data.get('status'),
                    'history_entries_added': len(history_entries) if update_data.get('status') == 'completed' else 0
                })
            else:
                return Response({'ok': False, 'error': 'No se proporcionaron fechas para actualizar'}, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AddMissingTripHistoryView(APIView):
    """Endpoint para agregar miembros faltantes al historial de un viaje completado"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            payload = request.data or {}
            trip_id = payload.get('trip_id')
            
            if not trip_id:
                return Response({'ok': False, 'error': 'trip_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Buscar el chat GRUPAL del viaje (no los chats privados)
            chat_resp = admin.table('chat_rooms').select('id').eq('trip_id', trip_id).eq('is_group', True).limit(1).execute()
            chat_room = (getattr(chat_resp, 'data', None) or [None])[0]
            
            if not chat_room:
                return Response({'ok': False, 'error': 'Chat del viaje no encontrado'}, status=status.HTTP_404_NOT_FOUND)
            
            # Obtener miembros del chat
            members_resp = admin.table('chat_members').select('user_id, role').eq('room_id', chat_room.get('id')).execute()
            members = getattr(members_resp, 'data', []) or []
            
            # Obtener miembros que ya están en el historial
            existing_history_resp = admin.table('trip_history').select('user_id').eq('trip_id', trip_id).execute()
            existing_user_ids = set([entry.get('user_id') for entry in (getattr(existing_history_resp, 'data', []) or [])])
            
            print(f"DEBUG: Members in chat: {[m.get('user_id') for m in members]}")
            print(f"DEBUG: Existing in history: {existing_user_ids}")
            
            # Agregar solo los miembros faltantes
            history_entries = []
            for member in members:
                user_id = member.get('user_id')
                
                # Agregar solo miembros que no estén ya en el historial
                if user_id not in existing_user_ids:
                    # Mapear role de chat_members a trip_history
                    member_role = member.get('role')
                    if member_role == 'owner':
                        history_role = 'organizer'
                    else:
                        history_role = 'member'
                        
                    history_entry = {
                        'user_id': user_id,
                        'trip_id': trip_id,
                        'role': history_role,
                        'status': 'completed',
                        'joined_at': '2024-01-15',  # Fecha del viaje
                        'left_at': None,
                        'rating_given': None,
                        'review_text': None
                    }
                    history_entries.append(history_entry)
            
            if history_entries:
                admin.table('trip_history').insert(history_entries).execute()
                return Response({
                    'ok': True,
                    'message': f'Agregados {len(history_entries)} miembros al historial',
                    'added_members': len(history_entries)
                })
            else:
                return Response({
                    'ok': True,
                    'message': 'Todos los miembros ya están en el historial',
                    'added_members': 0
                })
                
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CreateNotificationView(APIView):
    """Endpoint para crear notificaciones automáticamente"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            user_id = request.data.get('user_id')
            notification_type = request.data.get('type')
            title = request.data.get('title')
            message = request.data.get('message')
            data = request.data.get('data', {})
            
            if not all([user_id, notification_type, title, message]):
                return Response({
                    'ok': False,
                    'error': 'user_id, type, title y message son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()
            
            # Crear la notificación
            notification_data = {
                'user_id': user_id,
                'type': notification_type,
                'title': title,
                'message': message,
                'data': data,
                'read': False,
                'created_at': 'now()'
            }
            
            print(f"🔔 Creando notificación: {notification_data}")
            insert_resp = admin.table('notifications').insert(notification_data).execute()
            notification = (getattr(insert_resp, 'data', None) or [None])[0]
            
            if notification:
                print(f"🔔 Notificación creada exitosamente: {notification}")
                return Response({
                    'ok': True,
                    'notification': notification,
                    'message': 'Notificación creada exitosamente'
                })
            else:
                print(f"🔔 Error: No se pudo crear la notificación")
                return Response({
                    'ok': False,
                    'error': 'Error creando la notificación'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            print(f"🔔 Error creando notificación: {str(e)}")
            return Response({
                'ok': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestNotificationView(APIView):
    """Endpoint de prueba para crear notificaciones de chat"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            user_id = request.data.get('user_id')
            room_id = request.data.get('room_id')
            content = request.data.get('content', 'Mensaje de prueba')
            
            if not user_id or not room_id:
                return Response({
                    'ok': False,
                    'error': 'user_id y room_id son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()
            
            # Simular la lógica de notificaciones de chat
            try:
                # Obtener información de la sala
                room_resp = admin.table('chat_rooms').select('*').eq('id', room_id).limit(1).execute()
                room = (getattr(room_resp, 'data', None) or [None])[0]
                
                if not room:
                    return Response({
                        'ok': False,
                        'error': 'Sala no encontrada'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # Obtener todos los miembros de la sala excepto el remitente
                members_resp = admin.table('chat_members').select('user_id').eq('room_id', room_id).neq('user_id', str(user_id)).execute()
                members = getattr(members_resp, 'data', []) or []
                
                print(f"🔔 Miembros encontrados: {members}")
                
                # Obtener nombre del remitente
                sender_resp = admin.table('User').select('nombre, apellido').eq('userid', str(user_id)).limit(1).execute()
                sender = (getattr(sender_resp, 'data', None) or [None])[0]
                sender_name = f"{sender.get('nombre', '')} {sender.get('apellido', '')}".strip() if sender else 'Un usuario'
                
                # Determinar el tipo de notificación
                room_name = room.get('name', 'Chat')
                is_group = room.get('is_group', False)
                
                if is_group:
                    notification_type = 'group_chat_message'
                    title = f'Nuevo mensaje en {room_name}'
                    message = f'{sender_name} envió un mensaje en el chat grupal'
                else:
                    notification_type = 'private_chat_message'
                    title = f'Mensaje de {sender_name}'
                    message = f'{sender_name} te envió un mensaje privado'
                
                # Crear notificaciones para cada miembro
                created_notifications = []
                for member in members:
                    member_id = member.get('user_id')
                    if member_id:
                        notification_data = {
                            'user_id': member_id,
                            'type': notification_type,
                            'title': title,
                            'message': message,
                            'data': {
                                'room_id': room_id,
                                'sender_id': str(user_id),
                                'sender_name': sender_name,
                                'message_content': content[:100] + '...' if len(content) > 100 else content,
                                'is_file': False
                            }
                        }
                        
                        print(f"🔔 Creando notificación para {member_id}: {notification_data}")
                        insert_resp = admin.table('notifications').insert(notification_data).execute()
                        notification = (getattr(insert_resp, 'data', None) or [None])[0]
                        if notification:
                            created_notifications.append(notification)
                
                return Response({
                    'ok': True,
                    'notifications_created': len(created_notifications),
                    'notifications': created_notifications
                })
                
            except Exception as e:
                print(f"🔔 Error en lógica de notificaciones: {str(e)}")
                return Response({
                    'ok': False,
                    'error': f'Error en lógica de notificaciones: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            print(f"🔔 Error general: {str(e)}")
            return Response({
                'ok': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================
# ENDPOINTS PARA SOLICITUDES DE AMISTAD
# ============================================

class SendFriendRequestView(APIView):
    """Enviar solicitud de amistad"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            sender_id = request.data.get('sender_id')
            receiver_id = request.data.get('receiver_id')
            
            if not sender_id or not receiver_id:
                return Response({
                    'ok': False,
                    'error': 'sender_id y receiver_id son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validar que los IDs sean UUIDs válidos
            import uuid
            try:
                uuid.UUID(sender_id)
                uuid.UUID(receiver_id)
            except ValueError:
                return Response({
                    'ok': False,
                    'error': 'sender_id y receiver_id deben ser UUIDs válidos'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if sender_id == receiver_id:
                return Response({
                    'ok': False,
                    'error': 'No puedes enviarte una solicitud a ti mismo'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            admin = get_supabase_admin()
            
            # Verificar si ya existe una solicitud entre estos usuarios
            # Primero buscar como sender
            existing_resp1 = admin.table('friend_requests').select('*').eq('sender_id', sender_id).eq('receiver_id', receiver_id).execute()
            # Luego buscar como receiver
            existing_resp2 = admin.table('friend_requests').select('*').eq('sender_id', receiver_id).eq('receiver_id', sender_id).execute()
            
            existing_requests = []
            if existing_resp1.data:
                existing_requests.extend(existing_resp1.data)
            if existing_resp2.data:
                existing_requests.extend(existing_resp2.data)
            
            if existing_requests:
                existing = existing_requests[0]
                if existing['status'] == 'pending':
                    return Response({
                        'ok': False,
                        'error': 'Ya existe una solicitud pendiente entre estos usuarios'
                    }, status=status.HTTP_400_BAD_REQUEST)
                elif existing['status'] == 'accepted':
                    return Response({
                        'ok': False,
                        'error': 'Ya son amigos'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Crear nueva solicitud
            friend_request_data = {
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            insert_resp = admin.table('friend_requests').insert(friend_request_data).execute()
            friend_request = (getattr(insert_resp, 'data', None) or [None])[0]
            
            if not friend_request:
                return Response({
                    'ok': False,
                    'error': 'Error creando la solicitud'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Crear notificación para el receptor
            try:
                # Obtener nombre del remitente
                sender_resp = admin.table('User').select('nombre, apellido').eq('userid', sender_id).limit(1).execute()
                sender = (getattr(sender_resp, 'data', None) or [None])[0]
                sender_name = f"{sender.get('nombre', '')} {sender.get('apellido', '')}".strip() if sender else 'Un usuario'
                
                notification_data = {
                    'user_id': receiver_id,
                    'type': 'friend_request',
                    'title': 'Nueva solicitud de amistad',
                    'message': f'{sender_name} te envió una solicitud de amistad',
                    'data': {
                        'sender_id': sender_id,
                        'sender_name': sender_name,
                        'request_id': friend_request['id']
                    }
                }
                
                admin.table('notifications').insert(notification_data).execute()
            except Exception as notification_error:
                print(f"Error creando notificación de solicitud: {notification_error}")
            
            return Response({
                'ok': True,
                'friend_request': friend_request,
                'message': 'Solicitud enviada exitosamente'
            })
            
        except Exception as e:
            print(f"Error enviando solicitud de amistad: {str(e)}")
            return Response({
                'ok': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RespondFriendRequestView(APIView):
    """Responder a una solicitud de amistad (aceptar/rechazar)"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            request_id = request.data.get('request_id')
            action = request.data.get('action')  # 'accept' o 'reject'
            user_id = request.data.get('user_id')  # ID del usuario que responde
            
            if not all([request_id, action, user_id]):
                return Response({
                    'ok': False,
                    'error': 'request_id, action y user_id son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if action not in ['accept', 'reject']:
                return Response({
                    'ok': False,
                    'error': 'action debe ser "accept" o "reject"'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            admin = get_supabase_admin()
            
            # Obtener la solicitud
            request_resp = admin.table('friend_requests').select('*').eq('id', request_id).limit(1).execute()
            friend_request = (getattr(request_resp, 'data', None) or [None])[0]
            
            if not friend_request:
                return Response({
                    'ok': False,
                    'error': 'Solicitud no encontrada'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Verificar que el usuario es el receptor
            if friend_request['receiver_id'] != user_id:
                return Response({
                    'ok': False,
                    'error': 'No tienes permisos para responder a esta solicitud'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Verificar que la solicitud está pendiente
            if friend_request['status'] != 'pending':
                return Response({
                    'ok': False,
                    'error': 'Esta solicitud ya fue respondida'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Actualizar el estado
            new_status = 'accepted' if action == 'accept' else 'rejected'
            update_data = {
                'status': new_status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            update_resp = admin.table('friend_requests').update(update_data).eq('id', request_id).execute()
            updated_request = (getattr(update_resp, 'data', None) or [None])[0]
            
            if not updated_request:
                return Response({
                    'ok': False,
                    'error': 'Error actualizando la solicitud'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Crear notificación para el remitente
            try:
                # Obtener nombre del receptor
                receiver_resp = admin.table('User').select('nombre, apellido').eq('userid', user_id).limit(1).execute()
                receiver = (getattr(receiver_resp, 'data', None) or [None])[0]
                receiver_name = f"{receiver.get('nombre', '')} {receiver.get('apellido', '')}".strip() if receiver else 'Un usuario'
                
                if action == 'accept':
                    notification_data = {
                        'user_id': friend_request['sender_id'],
                        'type': 'friend_request_accepted',
                        'title': 'Solicitud de amistad aceptada',
                        'message': f'{receiver_name} aceptó tu solicitud de amistad',
                        'data': {
                            'receiver_id': user_id,
                            'receiver_name': receiver_name,
                            'request_id': request_id
                        }
                    }
                else:
                    notification_data = {
                        'user_id': friend_request['sender_id'],
                        'type': 'friend_request_rejected',
                        'title': 'Solicitud de amistad rechazada',
                        'message': f'{receiver_name} rechazó tu solicitud de amistad',
                        'data': {
                            'receiver_id': user_id,
                            'receiver_name': receiver_name,
                            'request_id': request_id
                        }
                    }
                
                admin.table('notifications').insert(notification_data).execute()
            except Exception as notification_error:
                print(f"Error creando notificación de respuesta: {notification_error}")
            
            return Response({
                'ok': True,
                'friend_request': updated_request,
                'message': f'Solicitud {new_status} exitosamente'
            })
            
        except Exception as e:
            print(f"Error respondiendo solicitud de amistad: {str(e)}")
            return Response({
                'ok': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetFriendRequestsView(APIView):
    """Obtener solicitudes de amistad de un usuario"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            user_id = request.query_params.get('user_id')
            request_type = request.query_params.get('type', 'received')  # 'sent' o 'received'
            
            print(f"🔍 GetFriendRequestsView - user_id recibido: {user_id}")
            print(f"🔍 GetFriendRequestsView - request_type: {request_type}")
            print(f"🔍 GetFriendRequestsView - query_params completos: {request.query_params}")
            
            if not user_id:
                return Response({
                    'ok': False,
                    'error': 'user_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            admin = get_supabase_admin()
            
            if request_type == 'sent':
                # Solicitudes enviadas
                requests_resp = admin.table('friend_requests').select('*').eq('sender_id', user_id).order('created_at', desc=True).execute()
            else:
                # Solicitudes recibidas
                requests_resp = admin.table('friend_requests').select('*').eq('receiver_id', user_id).order('created_at', desc=True).execute()
            
            friend_requests = getattr(requests_resp, 'data', []) or []
            
            # Enriquecer con información del usuario
            enriched_requests = []
            for req in friend_requests:
                other_user_id = req['receiver_id'] if request_type == 'sent' else req['sender_id']
                
                # Obtener información del otro usuario
                user_resp = admin.table('User').select('nombre, apellido, userid').eq('userid', other_user_id).limit(1).execute()
                other_user = (getattr(user_resp, 'data', None) or [None])[0]
                
                enriched_request = {
                    **req,
                    'other_user': {
                        'id': other_user_id,
                        'nombre': other_user.get('nombre', '') if other_user else '',
                        'apellido': other_user.get('apellido', '') if other_user else '',
                        'full_name': f"{other_user.get('nombre', '')} {other_user.get('apellido', '')}".strip() if other_user else 'Usuario'
                    }
                }
                enriched_requests.append(enriched_request)
            
            return Response({
                'ok': True,
                'friend_requests': enriched_requests
            })
            
        except Exception as e:
            print(f"Error obteniendo solicitudes de amistad: {str(e)}")
            return Response({
                'ok': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetFriendsView(APIView):
    """Obtener lista de amigos de un usuario"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            user_id = request.query_params.get('user_id')
            
            if not user_id:
                return Response({
                    'ok': False,
                    'error': 'user_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            admin = get_supabase_admin()
            
            # Obtener solicitudes aceptadas donde el usuario es remitente o receptor
            # Buscar como sender
            requests_resp1 = admin.table('friend_requests').select('*').eq('sender_id', user_id).eq('status', 'accepted').execute()
            # Buscar como receiver
            requests_resp2 = admin.table('friend_requests').select('*').eq('receiver_id', user_id).eq('status', 'accepted').execute()
            
            friend_requests = []
            if requests_resp1.data:
                friend_requests.extend(requests_resp1.data)
            if requests_resp2.data:
                friend_requests.extend(requests_resp2.data)
            
            # Enriquecer con información de los amigos
            friends = []
            for req in friend_requests:
                friend_id = req['receiver_id'] if req['sender_id'] == user_id else req['sender_id']
                
                # Obtener información del amigo
                friend_resp = admin.table('User').select('nombre, apellido, userid').eq('userid', friend_id).limit(1).execute()
                friend = (getattr(friend_resp, 'data', None) or [None])[0]
                
                if friend:
                    friends.append({
                        'id': friend_id,
                        'nombre': friend.get('nombre', ''),
                        'apellido': friend.get('apellido', ''),
                        'full_name': f"{friend.get('nombre', '')} {friend.get('apellido', '')}".strip(),
                        'friendship_date': req['created_at']
                    })
            
            return Response({
                'ok': True,
                'friends': friends
            })
            
        except Exception as e:
            print(f"Error obteniendo amigos: {str(e)}")
            return Response({
                'ok': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CheckFriendshipStatusView(APIView):
    """Verificar el estado de amistad entre dos usuarios"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            user1_id = request.query_params.get('user1_id')
            user2_id = request.query_params.get('user2_id')
            
            if not user1_id or not user2_id:
                return Response({
                    'ok': False,
                    'error': 'user1_id y user2_id son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            admin = get_supabase_admin()
            
            # Buscar solicitud entre estos usuarios
            # Buscar como sender
            request_resp1 = admin.table('friend_requests').select('*').eq('sender_id', user1_id).eq('receiver_id', user2_id).limit(1).execute()
            # Buscar como receiver
            request_resp2 = admin.table('friend_requests').select('*').eq('sender_id', user2_id).eq('receiver_id', user1_id).limit(1).execute()
            
            friend_request = None
            if request_resp1.data and len(request_resp1.data) > 0:
                friend_request = request_resp1.data[0]
            elif request_resp2.data and len(request_resp2.data) > 0:
                friend_request = request_resp2.data[0]
            
            if not friend_request:
                return Response({
                    'ok': True,
                    'status': 'none',
                    'message': 'No hay relación de amistad'
                })
            
            status_map = {
                'pending': 'pending',
                'accepted': 'friends',
                'rejected': 'rejected'
            }
            
            return Response({
                'ok': True,
                'status': status_map.get(friend_request['status'], 'none'),
                'friend_request': friend_request
            })
            
        except Exception as e:
            print(f"Error verificando estado de amistad: {str(e)}")
            return Response({
                'ok': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DebugFriendRequestsView(APIView):
    """Debug: Ver todas las solicitudes de amistad"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()
            
            # Obtener todas las solicitudes
            requests_resp = admin.table('friend_requests').select('*').order('created_at', desc=True).execute()
            all_requests = getattr(requests_resp, 'data', []) or []
            
            return Response({
                'ok': True,
                'total_requests': len(all_requests),
                'requests': all_requests
            })
            
        except Exception as e:
            print(f"Error obteniendo todas las solicitudes: {str(e)}")
            return Response({
                'ok': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InviteFriendToTripView(APIView):
    """Invitar un amigo a un viaje"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            trip_id = request.data.get('trip_id')
            friend_id = request.data.get('friend_id')
            organizer_id = request.data.get('organizer_id')
            
            if not all([trip_id, friend_id, organizer_id]):
                return Response({
                    'ok': False,
                    'error': 'trip_id, friend_id y organizer_id son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            admin = get_supabase_admin()
            
            # Verificar que el organizador es realmente el organizador del viaje
            trip_resp = admin.table('trips').select('creator_id').eq('id', trip_id).limit(1).execute()
            trip = (getattr(trip_resp, 'data', None) or [None])[0]
            
            if not trip or trip.get('creator_id') != organizer_id:
                return Response({
                    'ok': False,
                    'error': 'Solo el organizador puede invitar amigos'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Verificar que son amigos
            friendship_resp = admin.table('friend_requests').select('*').or_(
                f'and(sender_id.eq.{organizer_id},receiver_id.eq.{friend_id},status.eq.accepted)',
                f'and(sender_id.eq.{friend_id},receiver_id.eq.{organizer_id},status.eq.accepted)'
            ).limit(1).execute()
            
            if not friendship_resp.data or len(friendship_resp.data) == 0:
                return Response({
                    'ok': False,
                    'error': 'Solo puedes invitar a tus amigos'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Verificar que el amigo no esté ya en el viaje
            existing_member_resp = admin.table('trip_members').select('*').eq('trip_id', trip_id).eq('user_id', friend_id).limit(1).execute()
            if existing_member_resp.data and len(existing_member_resp.data) > 0:
                return Response({
                    'ok': False,
                    'error': 'Este amigo ya está en el viaje'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Obtener información del viaje y del amigo
            trip_info_resp = admin.table('trips').select('title, destination').eq('id', trip_id).limit(1).execute()
            trip_info = (getattr(trip_info_resp, 'data', None) or [None])[0]
            
            friend_info_resp = admin.table('User').select('nombre, apellido').eq('userid', friend_id).limit(1).execute()
            friend_info = (getattr(friend_info_resp, 'data', None) or [None])[0]
            
            organizer_info_resp = admin.table('User').select('nombre, apellido').eq('userid', organizer_id).limit(1).execute()
            organizer_info = (getattr(organizer_info_resp, 'data', None) or [None])[0]
            
            # Agregar al amigo al viaje
            trip_member_data = {
                'trip_id': trip_id,
                'user_id': friend_id,
                'role': 'member',
                'joined_at': datetime.utcnow().isoformat()
            }
            
            admin.table('trip_members').insert(trip_member_data).execute()
            
            # Buscar el chat grupal del viaje
            chat_resp = admin.table('chat_rooms').select('id').eq('trip_id', trip_id).eq('is_group', True).limit(1).execute()
            chat_room = (getattr(chat_resp, 'data', None) or [None])[0]
            
            if chat_room:
                # Agregar al amigo al chat grupal
                chat_member_data = {
                    'room_id': chat_room['id'],
                    'user_id': friend_id,
                    'role': 'member',
                    'joined_at': datetime.utcnow().isoformat()
                }
                
                admin.table('chat_members').insert(chat_member_data).execute()
            
            # Crear notificación para el amigo
            friend_name = f"{friend_info.get('nombre', '')} {friend_info.get('apellido', '')}".strip() if friend_info else 'Un amigo'
            organizer_name = f"{organizer_info.get('nombre', '')} {organizer_info.get('apellido', '')}".strip() if organizer_info else 'Un organizador'
            trip_title = trip_info.get('title', 'Un viaje') if trip_info else 'Un viaje'
            
            notification_data = {
                'user_id': friend_id,
                'type': 'trip_invitation',
                'title': 'Invitación a viaje',
                'message': f'{organizer_name} te invitó al viaje "{trip_title}"',
                'data': {
                    'trip_id': trip_id,
                    'organizer_id': organizer_id,
                    'organizer_name': organizer_name,
                    'trip_title': trip_title
                }
            }
            
            admin.table('notifications').insert(notification_data).execute()
            
            return Response({
                'ok': True,
                'message': f'Invitación enviada a {friend_name}',
                'friend_name': friend_name
            })
            
        except Exception as e:
            print(f"Error invitando amigo a viaje: {str(e)}")
            return Response({
                'ok': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RemoveFriendView(APIView):
    """Eliminar relación de amistad (unfriend) entre dos usuarios"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            user_id = request.data.get('user_id')
            friend_id = request.data.get('friend_id')
            if not user_id or not friend_id:
                return Response({
                    'ok': False,
                    'error': 'user_id y friend_id son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)

            if user_id == friend_id:
                return Response({
                    'ok': False,
                    'error': 'No puedes eliminarte a ti mismo'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Eliminar relaciones de amistad aceptadas en cualquier dirección (best-effort)
            try:
                admin.table('friend_requests')\
                    .delete()\
                    .eq('sender_id', user_id)\
                    .eq('receiver_id', friend_id)\
                    .eq('status', 'accepted')\
                    .execute()
            except Exception:
                pass
            try:
                admin.table('friend_requests')\
                    .delete()\
                    .eq('sender_id', friend_id)\
                    .eq('receiver_id', user_id)\
                    .eq('status', 'accepted')\
                    .execute()
            except Exception:
                pass

            # A partir de aquí, consideramos la operación exitosa independientemente de si existía o no,
            # para evitar falsos negativos por falta de 'count' en delete.

            # Notificar al amigo (best-effort)
            try:
                remover_resp = admin.table('User').select('nombre, apellido').eq('userid', user_id).limit(1).execute()
                remover = (getattr(remover_resp, 'data', None) or [None])[0]
                remover_name = f"{(remover or {}).get('nombre','')} {(remover or {}).get('apellido','')}".strip() or 'Un usuario'
                admin.table('notifications').insert({
                    'user_id': friend_id,
                    'type': 'friend_removed',
                    'title': 'Amistad eliminada',
                    'message': f'{remover_name} te eliminó de sus amigos',
                    'data': {
                        'remover_id': user_id,
                        'remover_name': remover_name
                    }
                }).execute()
            except Exception:
                pass

            return Response({
                'ok': True,
                'message': 'Amistad eliminada correctamente'
            })
        except Exception as e:
            return Response({
                'ok': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
