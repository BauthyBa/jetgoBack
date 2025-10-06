from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.authentication import BaseAuthentication
from rest_framework.response import Response
from .serializers import RegisterSerializer, LoginSerializer, ReviewSerializer, CreateReviewSerializer
from .models import User, Review
from django.db.models import Avg
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
        country = payload.get('country')
        budget_min = payload.get('budget_min')
        budget_max = payload.get('budget_max')
        status_val = payload.get('status')
        room_type = payload.get('room_type')
        season = payload.get('season')
        max_participants = payload.get('max_participants')
        date_iso = payload.get('date')
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
        add_if_missing('status', status_val)
        add_if_missing('room_type', room_type)
        add_if_missing('max_participants', max_participants)
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
            trip_row = {
                'creator_id': creator_id,
                'origin': origin,
                'destination': destination,
                'date': date_iso,
                'name': name,
                'country': country,
                'budget_min': budget_min_num,
                'budget_max': budget_max_num,
                'status': status_val,
                'room_type': room_type,
                'season': season,
                'max_participants': max_participants_num,
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
            trips_resp = admin.table('trips').select('*').order('created_at', desc=True).execute()
            trips = getattr(trips_resp, 'data', []) or []

            # Attach current_participants count for each trip (best-effort)
            enriched = []
            for t in trips:
                try:
                    c_resp = admin.table('trip_members').select('id', count='exact').eq('trip_id', t.get('id')).execute()
                    current = getattr(c_resp, 'count', None)
                    if isinstance(current, int):
                        t = { **t, 'current_participants': current }
                except Exception:
                    pass
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

            # Verificar que los usuarios existan
            try:
                reviewer = User.objects.get(id=reviewer_id)
                reviewed_user = User.objects.get(id=reviewed_user_id)
            except User.DoesNotExist:
                return Response({
                    'ok': False, 
                    'error': 'Usuario no encontrado'
                }, status=status.HTTP_404_NOT_FOUND)

            # Verificar que no se esté autoreseñando
            if reviewer_id == reviewed_user_id:
                return Response({
                    'ok': False, 
                    'error': 'No puedes dejarte una reseña a ti mismo'
                }, status=status.HTTP_400_BAD_REQUEST)

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

            # Verificar que el usuario exista
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({
                    'ok': False, 
                    'error': 'Usuario no encontrado'
                }, status=status.HTTP_404_NOT_FOUND)

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
                django_user = User.objects.get(id=user_id)
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

                reviews_data = {
                    'reviews': reviews_serializer.data,
                    'statistics': {
                        'total_reviews': total_reviews,
                        'average_rating': avg_rating,
                        'rating_distribution': rating_distribution
                    }
                }
            except User.DoesNotExist:
                # Si el usuario no existe en Django, crear datos vacíos para las reseñas
                reviews_data = {
                    'reviews': [],
                    'statistics': {
                        'total_reviews': 0,
                        'average_rating': 0,
                        'rating_distribution': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                    }
                }

            return Response({
                'ok': True,
                'user': user_data,
                'reviews_data': reviews_data
            })

        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
