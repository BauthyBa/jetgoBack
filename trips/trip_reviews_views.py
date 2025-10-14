from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from api.supabase_client import get_supabase_admin
from os import environ
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TripReviewCreateView(APIView):
    """Vista para crear reseñas de viajes usando Supabase directamente"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            # Datos requeridos
            trip_id = request.data.get('trip_id')
            reviewer_id = request.data.get('reviewer_id')
            organizer_id = request.data.get('organizer_id')
            overall_rating = request.data.get('overall_rating')

            if not all([trip_id, reviewer_id, organizer_id, overall_rating]):
                return Response({
                    'ok': False, 
                    'error': 'trip_id, reviewer_id, organizer_id y overall_rating son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validar rating
            try:
                overall_rating = int(overall_rating)
                if overall_rating < 1 or overall_rating > 5:
                    return Response({
                        'ok': False, 
                        'error': 'El rating debe estar entre 1 y 5'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError):
                return Response({
                    'ok': False, 
                    'error': 'Rating debe ser un número entero'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Verificar que el viaje existe y está completado
            try:
                trip_resp = admin.table('trips').select('id,status,creator_id').eq('id', trip_id).limit(1).execute()
                trip = (getattr(trip_resp, 'data', None) or [None])[0]
                
                if not trip:
                    return Response({
                        'ok': False, 
                        'error': 'Viaje no encontrado'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                if trip.get('status') != 'completed':
                    return Response({
                        'ok': False, 
                        'error': 'Solo se pueden reseñar viajes completados'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if trip.get('creator_id') != organizer_id:
                    return Response({
                        'ok': False, 
                        'error': 'El organizer_id no coincide con el creador del viaje'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                logger.error(f"Error verificando viaje: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando el viaje'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Verificar que el reviewer fue miembro del viaje
            try:
                member_resp = admin.table('trip_members').select('user_id').eq('trip_id', trip_id).eq('user_id', reviewer_id).limit(1).execute()
                member = (getattr(member_resp, 'data', None) or [None])[0]
                
                if not member:
                    return Response({
                        'ok': False, 
                        'error': 'Solo los miembros del viaje pueden crear reseñas'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                logger.error(f"Error verificando membresía: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando membresía del viaje'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Verificar que no existe ya una reseña del mismo usuario para este viaje
            try:
                existing_resp = admin.table('trip_reviews').select('id').eq('trip_id', trip_id).eq('reviewer_id', reviewer_id).limit(1).execute()
                existing = (getattr(existing_resp, 'data', None) or [None])[0]
                
                if existing:
                    return Response({
                        'ok': False, 
                        'error': 'Ya has creado una reseña para este viaje'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                logger.error(f"Error verificando reseña existente: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando reseña existente'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Preparar datos para insertar
            review_data = {
                'trip_id': trip_id,
                'reviewer_id': reviewer_id,
                'organizer_id': organizer_id,
                'overall_rating': overall_rating,
                'destination_rating': request.data.get('destination_rating'),
                'organization_rating': request.data.get('organization_rating'),
                'communication_rating': request.data.get('communication_rating'),
                'value_rating': request.data.get('value_rating'),
                'overall_comment': request.data.get('overall_comment', ''),
                'destination_comment': request.data.get('destination_comment', ''),
                'organization_comment': request.data.get('organization_comment', ''),
                'communication_comment': request.data.get('communication_comment', ''),
                'value_comment': request.data.get('value_comment', ''),
                'trip_highlights': request.data.get('trip_highlights', ''),
                'trip_improvements': request.data.get('trip_improvements', ''),
                'would_recommend': request.data.get('would_recommend', False),
                'would_travel_again': request.data.get('would_travel_again', False),
                'is_anonymous': request.data.get('is_anonymous', False)
            }

            # Filtrar valores None
            review_data = {k: v for k, v in review_data.items() if v is not None}

            # Crear la reseña
            try:
                resp = admin.table('trip_reviews').insert(review_data).execute()
                review = (getattr(resp, 'data', None) or [None])[0]
                
                if not review:
                    return Response({
                        'ok': False, 
                        'error': 'Error creando la reseña'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                return Response({
                    'ok': True, 
                    'data': review,
                    'message': 'Reseña creada exitosamente'
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error creando reseña: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': f'Error creando la reseña: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error general en TripReviewCreateView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripReviewListView(APIView):
    """Vista para listar reseñas de viajes"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            trip_id = request.query_params.get('trip_id')
            organizer_id = request.query_params.get('organizer_id')
            reviewer_id = request.query_params.get('reviewer_id')
            limit = int(request.query_params.get('limit', 20))
            offset = int(request.query_params.get('offset', 0))

            admin = get_supabase_admin()

            # Construir query
            query = admin.table('trip_reviews').select('''
                *,
                trips:trips(name, destination, start_date, end_date),
                reviewer:User!trip_reviews_reviewer_id_fkey(userid, nombre, apellido, avatar_url),
                organizer:User!trip_reviews_organizer_id_fkey(userid, nombre, apellido, avatar_url)
            ''')

            # Aplicar filtros
            if trip_id:
                query = query.eq('trip_id', trip_id)
            if organizer_id:
                query = query.eq('organizer_id', organizer_id)
            if reviewer_id:
                query = query.eq('reviewer_id', reviewer_id)

            # Ordenar por fecha de creación (más recientes primero)
            query = query.order('created_at', desc=True)
            query = query.range(offset, offset + limit - 1)

            resp = query.execute()
            reviews = getattr(resp, 'data', None) or []

            return Response({
                'ok': True,
                'data': reviews,
                'count': len(reviews)
            })

        except Exception as e:
            logger.error(f"Error en TripReviewListView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripReviewDetailView(APIView):
    """Vista para obtener detalles de una reseña específica"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, review_id, *args, **kwargs):
        try:
            admin = get_supabase_admin()

            resp = admin.table('trip_reviews').select('''
                *,
                trips:trips(name, destination, start_date, end_date),
                reviewer:User!trip_reviews_reviewer_id_fkey(userid, nombre, apellido, avatar_url),
                organizer:User!trip_reviews_organizer_id_fkey(userid, nombre, apellido, avatar_url),
                responses:trip_review_responses(*)
            ''').eq('id', review_id).limit(1).execute()

            review = (getattr(resp, 'data', None) or [None])[0]

            if not review:
                return Response({
                    'ok': False, 
                    'error': 'Reseña no encontrada'
                }, status=status.HTTP_404_NOT_FOUND)

            return Response({
                'ok': True,
                'data': review
            })

        except Exception as e:
            logger.error(f"Error en TripReviewDetailView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripReviewUpdateView(APIView):
    """Vista para actualizar una reseña existente"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def put(self, request, review_id, *args, **kwargs):
        try:
            reviewer_id = request.data.get('reviewer_id')
            
            if not reviewer_id:
                return Response({
                    'ok': False, 
                    'error': 'reviewer_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Verificar que la reseña existe y pertenece al usuario
            try:
                existing_resp = admin.table('trip_reviews').select('reviewer_id').eq('id', review_id).limit(1).execute()
                existing = (getattr(existing_resp, 'data', None) or [None])[0]
                
                if not existing:
                    return Response({
                        'ok': False, 
                        'error': 'Reseña no encontrada'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                if existing.get('reviewer_id') != reviewer_id:
                    return Response({
                        'ok': False, 
                        'error': 'No tienes permisos para editar esta reseña'
                    }, status=status.HTTP_403_FORBIDDEN)
                    
            except Exception as e:
                logger.error(f"Error verificando reseña: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando la reseña'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Preparar datos para actualizar
            update_data = {}
            allowed_fields = [
                'overall_rating', 'destination_rating', 'organization_rating', 
                'communication_rating', 'value_rating', 'overall_comment',
                'destination_comment', 'organization_comment', 'communication_comment',
                'value_comment', 'trip_highlights', 'trip_improvements',
                'would_recommend', 'would_travel_again', 'is_anonymous'
            ]

            for field in allowed_fields:
                if field in request.data:
                    update_data[field] = request.data[field]

            if not update_data:
                return Response({
                    'ok': False, 
                    'error': 'No hay datos para actualizar'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Actualizar la reseña
            try:
                resp = admin.table('trip_reviews').update(update_data).eq('id', review_id).execute()
                updated_review = (getattr(resp, 'data', None) or [None])[0]
                
                if not updated_review:
                    return Response({
                        'ok': False, 
                        'error': 'Error actualizando la reseña'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                return Response({
                    'ok': True, 
                    'data': updated_review,
                    'message': 'Reseña actualizada exitosamente'
                })
                
            except Exception as e:
                logger.error(f"Error actualizando reseña: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': f'Error actualizando la reseña: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error general en TripReviewUpdateView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripReviewDeleteView(APIView):
    """Vista para eliminar una reseña"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def delete(self, request, review_id, *args, **kwargs):
        try:
            reviewer_id = request.data.get('reviewer_id')
            
            if not reviewer_id:
                return Response({
                    'ok': False, 
                    'error': 'reviewer_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Verificar que la reseña existe y pertenece al usuario
            try:
                existing_resp = admin.table('trip_reviews').select('reviewer_id').eq('id', review_id).limit(1).execute()
                existing = (getattr(existing_resp, 'data', None) or [None])[0]
                
                if not existing:
                    return Response({
                        'ok': False, 
                        'error': 'Reseña no encontrada'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                if existing.get('reviewer_id') != reviewer_id:
                    return Response({
                        'ok': False, 
                        'error': 'No tienes permisos para eliminar esta reseña'
                    }, status=status.HTTP_403_FORBIDDEN)
                    
            except Exception as e:
                logger.error(f"Error verificando reseña: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando la reseña'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Eliminar la reseña
            try:
                admin.table('trip_reviews').delete().eq('id', review_id).execute()

                return Response({
                    'ok': True, 
                    'message': 'Reseña eliminada exitosamente'
                })
                
            except Exception as e:
                logger.error(f"Error eliminando reseña: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': f'Error eliminando la reseña: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error general en TripReviewDeleteView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripReviewResponseView(APIView):
    """Vista para que el organizador responda a una reseña"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, review_id, *args, **kwargs):
        try:
            organizer_id = request.data.get('organizer_id')
            response_text = request.data.get('response_text', '').strip()
            
            if not organizer_id or not response_text:
                return Response({
                    'ok': False, 
                    'error': 'organizer_id y response_text son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Verificar que la reseña existe y el organizador es correcto
            try:
                review_resp = admin.table('trip_reviews').select('organizer_id').eq('id', review_id).limit(1).execute()
                review = (getattr(review_resp, 'data', None) or [None])[0]
                
                if not review:
                    return Response({
                        'ok': False, 
                        'error': 'Reseña no encontrada'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                if review.get('organizer_id') != organizer_id:
                    return Response({
                        'ok': False, 
                        'error': 'No tienes permisos para responder a esta reseña'
                    }, status=status.HTTP_403_FORBIDDEN)
                    
            except Exception as e:
                logger.error(f"Error verificando reseña: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando la reseña'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Verificar si ya existe una respuesta
            try:
                existing_resp = admin.table('trip_review_responses').select('id').eq('review_id', review_id).limit(1).execute()
                existing = (getattr(existing_resp, 'data', None) or [None])[0]
                
                if existing:
                    return Response({
                        'ok': False, 
                        'error': 'Ya existe una respuesta para esta reseña'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                logger.error(f"Error verificando respuesta existente: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando respuesta existente'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Crear la respuesta
            try:
                response_data = {
                    'review_id': review_id,
                    'organizer_id': organizer_id,
                    'response_text': response_text
                }

                resp = admin.table('trip_review_responses').insert(response_data).execute()
                response = (getattr(resp, 'data', None) or [None])[0]
                
                if not response:
                    return Response({
                        'ok': False, 
                        'error': 'Error creando la respuesta'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                return Response({
                    'ok': True, 
                    'data': response,
                    'message': 'Respuesta creada exitosamente'
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error creando respuesta: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': f'Error creando la respuesta: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error general en TripReviewResponseView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripReviewCategoriesView(APIView):
    """Vista para obtener las categorías de evaluación disponibles"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            admin = get_supabase_admin()

            resp = admin.table('trip_review_categories').select('*').eq('is_active', True).order('name').execute()
            categories = getattr(resp, 'data', None) or []

            return Response({
                'ok': True,
                'data': categories
            })

        except Exception as e:
            logger.error(f"Error en TripReviewCategoriesView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripReviewEligibilityView(APIView):
    """Vista para verificar si un usuario puede reseñar un viaje"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            trip_id = request.query_params.get('trip_id')
            user_id = request.query_params.get('user_id')
            
            if not trip_id or not user_id:
                return Response({
                    'ok': False, 
                    'error': 'trip_id y user_id son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Verificar que el viaje existe y está completado
            try:
                trip_resp = admin.table('trips').select('id,status,creator_id').eq('id', trip_id).limit(1).execute()
                trip = (getattr(trip_resp, 'data', None) or [None])[0]
                
                if not trip:
                    return Response({
                        'ok': True,
                        'can_review': False,
                        'reason': 'Viaje no encontrado'
                    })

                if trip.get('status') != 'completed':
                    return Response({
                        'ok': True,
                        'can_review': False,
                        'reason': 'Solo se pueden reseñar viajes completados'
                    })
                    
            except Exception as e:
                logger.error(f"Error verificando viaje: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando el viaje'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Verificar que el usuario fue miembro del viaje
            try:
                member_resp = admin.table('trip_members').select('user_id').eq('trip_id', trip_id).eq('user_id', user_id).limit(1).execute()
                member = (getattr(member_resp, 'data', None) or [None])[0]
                
                if not member:
                    return Response({
                        'ok': True,
                        'can_review': False,
                        'reason': 'Solo los miembros del viaje pueden crear reseñas'
                    })
                    
            except Exception as e:
                logger.error(f"Error verificando membresía: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando membresía del viaje'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Verificar que no existe ya una reseña del mismo usuario para este viaje
            try:
                existing_resp = admin.table('trip_reviews').select('id').eq('trip_id', trip_id).eq('reviewer_id', user_id).limit(1).execute()
                existing = (getattr(existing_resp, 'data', None) or [None])[0]
                
                if existing:
                    return Response({
                        'ok': True,
                        'can_review': False,
                        'reason': 'Ya has creado una reseña para este viaje'
                    })
                    
            except Exception as e:
                logger.error(f"Error verificando reseña existente: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando reseña existente'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({
                'ok': True,
                'can_review': True,
                'reason': 'Puedes crear una reseña para este viaje'
            })

        except Exception as e:
            logger.error(f"Error general en TripReviewEligibilityView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
