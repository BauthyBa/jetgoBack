from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from api.supabase_client import get_supabase_admin
from os import environ
import logging

logger = logging.getLogger(__name__)

class SupabaseCreateReviewView(APIView):
    """Vista para crear reseñas usando Supabase directamente"""
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

            # Validar rating
            try:
                rating = int(rating)
                if rating < 1 or rating > 5:
                    return Response({
                        'ok': False, 
                        'error': 'El rating debe estar entre 1 y 5'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError):
                return Response({
                    'ok': False, 
                    'error': 'Rating debe ser un número entero'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Verificar que no se esté autoreseñando
            if reviewer_id == reviewed_user_id:
                return Response({
                    'ok': False, 
                    'error': 'No puedes dejarte una reseña a ti mismo'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Verificar que los usuarios existan
            try:
                reviewer_resp = admin.table('User').select('userid,nombre,apellido').eq('userid', str(reviewer_id)).limit(1).execute()
                reviewer_data = (getattr(reviewer_resp, 'data', None) or [None])[0]
                
                reviewed_resp = admin.table('User').select('userid,nombre,apellido').eq('userid', str(reviewed_user_id)).limit(1).execute()
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

            # Verificar si ya existe una reseña
            try:
                existing_resp = admin.table('reviews').select('*').eq('reviewer_id', reviewer_id).eq('reviewed_user_id', reviewed_user_id).limit(1).execute()
                existing_review = (getattr(existing_resp, 'data', None) or [None])[0]

                if existing_review:
                    # Actualizar reseña existente
                    update_resp = admin.table('reviews').update({
                        'rating': rating,
                        'comment': comment
                    }).eq('id', existing_review['id']).execute()
                    
                    updated_review = (getattr(update_resp, 'data', None) or [None])[0]
                    if updated_review:
                        # Agregar nombres para la respuesta
                        updated_review['reviewer_name'] = f"{reviewer_data.get('nombre', '')} {reviewer_data.get('apellido', '')}".strip()
                        updated_review['reviewed_user_name'] = f"{reviewed_data.get('nombre', '')} {reviewed_data.get('apellido', '')}".strip()
                        
                        return Response({
                            'ok': True,
                            'review': updated_review,
                            'message': 'Reseña actualizada exitosamente'
                        })
                else:
                    # Crear nueva reseña
                    insert_resp = admin.table('reviews').insert({
                        'reviewer_id': reviewer_id,
                        'reviewed_user_id': reviewed_user_id,
                        'rating': rating,
                        'comment': comment
                    }).execute()
                    
                    new_review = (getattr(insert_resp, 'data', None) or [None])[0]
                    if new_review:
                        # Agregar nombres para la respuesta
                        new_review['reviewer_name'] = f"{reviewer_data.get('nombre', '')} {reviewer_data.get('apellido', '')}".strip()
                        new_review['reviewed_user_name'] = f"{reviewed_data.get('nombre', '')} {reviewed_data.get('apellido', '')}".strip()
                        
                        return Response({
                            'ok': True,
                            'review': new_review,
                            'message': 'Reseña creada exitosamente'
                        }, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({
                    'ok': False, 
                    'error': f'Error al procesar reseña: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class SupabaseGetUserReviewsView(APIView):
    """Vista para obtener reseñas de un usuario usando Supabase"""
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

            # Verificar que el usuario exista
            try:
                user_resp = admin.table('User').select('userid').eq('userid', str(user_id)).limit(1).execute()
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

            # Obtener todas las reseñas del usuario
            try:
                reviews_resp = admin.table('reviews').select('*').eq('reviewed_user_id', user_id).order('created_at', desc=True).execute()
                reviews = getattr(reviews_resp, 'data', []) or []

                # Enriquecer reseñas con nombres de usuarios
                enriched_reviews = []
                for review in reviews:
                    try:
                        # Obtener nombre del reviewer
                        reviewer_resp = admin.table('User').select('nombre,apellido').eq('userid', review['reviewer_id']).limit(1).execute()
                        reviewer_data = (getattr(reviewer_resp, 'data', None) or [None])[0]
                        
                        review['reviewer_name'] = 'Usuario anónimo'
                        if reviewer_data:
                            nombre = reviewer_data.get('nombre', '')
                            apellido = reviewer_data.get('apellido', '')
                            review['reviewer_name'] = f"{nombre} {apellido}".strip() or 'Usuario anónimo'
                        
                        enriched_reviews.append(review)
                    except Exception:
                        review['reviewer_name'] = 'Usuario anónimo'
                        enriched_reviews.append(review)

                # Calcular estadísticas
                total_reviews = len(enriched_reviews)
                if total_reviews > 0:
                    total_rating = sum(review['rating'] for review in enriched_reviews)
                    avg_rating = round(total_rating / total_reviews, 1)
                else:
                    avg_rating = 0

                # Distribución de ratings
                rating_distribution = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                for review in enriched_reviews:
                    rating_str = str(review['rating'])
                    if rating_str in rating_distribution:
                        rating_distribution[rating_str] += 1

                return Response({
                    'ok': True,
                    'reviews': enriched_reviews,
                    'statistics': {
                        'total_reviews': total_reviews,
                        'average_rating': avg_rating,
                        'rating_distribution': rating_distribution
                    }
                })

            except Exception as e:
                return Response({
                    'ok': False, 
                    'error': f'Error obteniendo reseñas: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class SupabaseGetUserNotificationsView(APIView):
    """Vista para obtener notificaciones de un usuario"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            user_id = request.query_params.get('user_id')
            limit = request.query_params.get('limit', 20)
            
            if not user_id:
                return Response({
                    'ok': False, 
                    'error': 'user_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                limit = int(limit)
                if limit > 100:
                    limit = 100
            except (ValueError, TypeError):
                limit = 20

            admin = get_supabase_admin()

            # Obtener notificaciones del usuario
            try:
                notifications_resp = admin.table('notifications').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute()
                notifications = getattr(notifications_resp, 'data', []) or []

                # Contar notificaciones no leídas
                unread_resp = admin.table('notifications').select('id', count='exact').eq('user_id', user_id).eq('read', False).execute()
                unread_count = getattr(unread_resp, 'count', 0) or 0

                return Response({
                    'ok': True,
                    'notifications': notifications,
                    'unread_count': unread_count
                })

            except Exception as e:
                return Response({
                    'ok': False, 
                    'error': f'Error obteniendo notificaciones: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class SupabaseMarkNotificationReadView(APIView):
    """Vista para marcar notificaciones como leídas"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            notification_id = request.data.get('notification_id')
            user_id = request.data.get('user_id')
            
            if not notification_id or not user_id:
                return Response({
                    'ok': False, 
                    'error': 'notification_id y user_id son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            try:
                # Marcar como leída solo si pertenece al usuario
                update_resp = admin.table('notifications').update({
                    'read': True
                }).eq('id', notification_id).eq('user_id', user_id).execute()
                
                updated_notification = (getattr(update_resp, 'data', None) or [None])[0]
                
                if updated_notification:
                    return Response({
                        'ok': True,
                        'message': 'Notificación marcada como leída'
                    })
                else:
                    return Response({
                        'ok': False,
                        'error': 'Notificación no encontrada o no pertenece al usuario'
                    }, status=status.HTTP_404_NOT_FOUND)

            except Exception as e:
                return Response({
                    'ok': False, 
                    'error': f'Error actualizando notificación: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class SupabaseMarkAllNotificationsReadView(APIView):
    """Vista para marcar todas las notificaciones como leídas"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            user_id = request.data.get('user_id')
            
            if not user_id:
                return Response({
                    'ok': False, 
                    'error': 'user_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            try:
                # Marcar todas las notificaciones del usuario como leídas
                update_resp = admin.table('notifications').update({
                    'read': True
                }).eq('user_id', user_id).eq('read', False).execute()
                
                return Response({
                    'ok': True,
                    'message': 'Todas las notificaciones marcadas como leídas'
                })

            except Exception as e:
                return Response({
                    'ok': False, 
                    'error': f'Error actualizando notificaciones: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
