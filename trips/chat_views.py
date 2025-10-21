from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from api.supabase_client import get_supabase_admin
import uuid
import os
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Tipos de archivo permitidos
ALLOWED_FILE_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf', 'text/plain',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'audio/webm', 'audio/webm;codecs=opus', 'audio/mp3', 'audio/wav', 'audio/ogg', 'audio/m4a', 'audio/mpeg', 'audio/x-m4a'
}

# Tamaño máximo de archivo (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

def extract_audio_metadata(file_path, file_type):
    """Extraer metadatos de audio si es posible"""
    try:
        if file_type.startswith('audio/'):
            # Para audios, intentar extraer duración
            # En un entorno de producción, usaría librosa o similar
            # Por ahora, retornamos None para que el frontend maneje la duración
            return {
                'audio_duration': None,  # Se calculará en el frontend
                'audio_waveform': None   # Se generará en el frontend
            }
    except Exception as e:
        logger.warning(f"Error extrayendo metadatos de audio: {e}")
    
    return {
        'audio_duration': None,
        'audio_waveform': None
    }


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def test_endpoint(request):
    """Endpoint de prueba simple"""
    return Response({'status': 'success', 'message': 'Test endpoint working'})

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def test_audio_upload(request):
    """Endpoint de prueba para subir audios"""
    try:
        logger.info("=== TEST AUDIO UPLOAD ===")
        logger.info(f"Request data: {request.data}")
        logger.info(f"Request files: {request.FILES}")
        
        if 'file' not in request.FILES:
            return Response({'error': 'No se encontró archivo'}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        logger.info(f"File info: name={file.name}, type={file.content_type}, size={file.size}")
        
        # Verificar que es un audio
        if not file.content_type.startswith('audio/'):
            return Response({'error': 'El archivo no es un audio'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Leer contenido
        file_content = file.read()
        logger.info(f"File content size: {len(file_content)} bytes")
        
        # Generar path único
        unique_filename = f"test_{uuid.uuid4()}.webm"
        file_path = f"test/{unique_filename}"
        
        # Subir a Supabase
        admin = get_supabase_admin()
        upload_response = admin.storage.from_('jetgo-audios').upload(
            file_path,
            file_content,
            file_options={
                'content-type': file.content_type,
                'cache-control': '3600'
            }
        )
        
        logger.info(f"Upload response: {upload_response}")
        
        if hasattr(upload_response, 'error') and upload_response.error:
            return Response({'error': f'Error subiendo: {upload_response.error}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Obtener URL pública
        file_url = admin.storage.from_('jetgo-audios').get_public_url(file_path)
        
        return Response({
            'status': 'success',
            'message': 'Audio subido correctamente',
            'file_url': file_url,
            'file_path': file_path,
            'bucket': 'jetgo-audios'
        })
        
    except Exception as e:
        logger.error(f"Error en test upload: {e}")
        return Response({'error': f'Error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def upload_chat_file(request):
    """Subir archivo para el chat y crear mensaje en una sola operación"""
    try:
        logger.info("=== UPLOAD REQUEST START ===")
        logger.info(f"Method: {request.method}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Data keys: {list(request.data.keys()) if hasattr(request, 'data') else 'No data'}")
        logger.info(f"Files keys: {list(request.FILES.keys()) if hasattr(request, 'FILES') else 'No files'}")
        
        # Obtener datos del body
        user_id = request.data.get('user_id')
        room_id = request.data.get('room_id')
        
        logger.info(f"User ID from body: {user_id}")
        logger.info(f"Room ID from body: {room_id}")
        
        if not user_id or not room_id:
            return Response({'error': 'user_id y room_id son requeridos'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que el archivo existe
        if 'file' not in request.FILES:
            return Response({'error': 'No se encontró archivo'}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        
        logger.info(f"=== FILE DEBUG ===")
        logger.info(f"File content_type: {file.content_type}")
        logger.info(f"File size: {file.size}")
        logger.info(f"File name: {file.name}")
        logger.info(f"File type: {type(file)}")
        logger.info(f"File attributes: {dir(file)}")
        
        # Validar tipo de archivo - ser más flexible con audio
        is_audio_file = file.content_type.startswith('audio/')
        
        if is_audio_file:
            # Para archivos de audio, aceptar cualquier tipo de audio
            logger.info(f"Audio file detected: {file.content_type}")
            is_allowed_type = True
        else:
            # Para otros archivos, validar estrictamente
            is_allowed_type = file.content_type in ALLOWED_FILE_TYPES
        
        logger.info(f"File validation - is_audio: {is_audio_file}, is_allowed: {is_allowed_type}")
        
        if not is_allowed_type:
            logger.error(f"Tipo de archivo no permitido: {file.content_type}")
            return Response({'error': f'Tipo de archivo no permitido: {file.content_type}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar tamaño
        if file.size > MAX_FILE_SIZE:
            return Response({'error': 'Archivo demasiado grande (máximo 10MB)'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que el usuario pertenece a la sala
        admin = get_supabase_admin()
        membership = admin.table('chat_members').select('*').eq('room_id', room_id).eq('user_id', str(user_id)).execute()
        
        if not membership.data:
            return Response({'error': 'No tienes acceso a esta sala'}, status=status.HTTP_403_FORBIDDEN)
        
        # Generar nombre único para el archivo
        file_extension = file.name.split('.')[-1] if '.' in file.name else ''
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = f"{user_id}/{unique_filename}"
        
        # Subir archivo a Supabase Storage
        try:
            # Leer el contenido del archivo
            file_content = file.read()
            
            # Subir directamente a Supabase Storage
            # Usar bucket de audios si es audio, sino usar chat-files
            bucket_name = 'jetgo-audios' if file.content_type.startswith('audio/') else 'chat-files'
            
            logger.info(f"=== AUDIO UPLOAD DEBUG ===")
            logger.info(f"File type: {file.content_type}")
            logger.info(f"Bucket selected: {bucket_name}")
            logger.info(f"File path: {file_path}")
            logger.info(f"File size: {len(file_content)} bytes")
            logger.info(f"Content type for upload: audio/webm")
            
            # Forzar el tipo MIME correcto en el upload
            upload_response = admin.storage.from_(bucket_name).upload(
                file_path,
                file_content,
                file_options={
                    'content-type': 'audio/webm',
                    'cache-control': '3600'
                }
            )
            
            logger.info(f"Upload response: {upload_response}")
            
            # Verificar si hubo error en el upload
            if hasattr(upload_response, 'error') and upload_response.error:
                logger.error(f"Error subiendo archivo: {upload_response.error}")
                return Response({'error': 'Error subiendo archivo'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Obtener URL pública del archivo
            file_url = admin.storage.from_(bucket_name).get_public_url(file_path)
            logger.info(f"File URL: {file_url}")
            
        except Exception as e:
            logger.error(f"Error subiendo archivo: {e}")
            return Response({'error': f'Error subiendo archivo: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Extraer metadatos de audio si es necesario
        audio_metadata = extract_audio_metadata(file_path, file.content_type)
        
        # Normalizar el tipo de archivo para la base de datos
        if file.content_type.startswith('audio/'):
            normalized_file_type = 'audio/webm'  # Usar tipo específico que funciona
        else:
            normalized_file_type = file.content_type.split(';')[0] if ';' in file.content_type else file.content_type
        
        logger.info(f"Original file_type: {file.content_type}")
        logger.info(f"Normalized file_type: {normalized_file_type}")
        
        # Crear mensaje con archivo
        message_data = {
            'room_id': room_id,
            'user_id': str(user_id),
            'content': f"📎 {file.name}",
            'is_file': True,
            'file_url': file_url,
            'file_name': file.name,
            'file_type': normalized_file_type,  # Usar tipo normalizado
            'file_size': file.size,
            'audio_duration': audio_metadata.get('audio_duration'),
            'audio_waveform': json.dumps(audio_metadata.get('audio_waveform')) if audio_metadata.get('audio_waveform') else None,
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Verificar que todos los campos requeridos están presentes
        logger.info(f"=== MESSAGE DATA DEBUG ===")
        logger.info(f"file_url: {message_data.get('file_url')}")
        logger.info(f"file_name: {message_data.get('file_name')}")
        logger.info(f"file_type: {message_data.get('file_type')}")
        logger.info(f"is_file: {message_data.get('is_file')}")
        required_fields = [
            message_data.get('file_url'),
            message_data.get('file_name'),
            message_data.get('file_type')
        ]
        logger.info(f"All required fields present: {all(required_fields)}")
        
        # Insertar mensaje en la base de datos
        response = admin.table('chat_messages').insert(message_data).execute()
        
        if not response.data:
            return Response({'error': 'Error creando mensaje'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'status': 'success',
            'message': 'Archivo subido y mensaje creado',
            'message_id': response.data[0]['id'],
            'file_url': file_url,
            'file_name': file.name,
            'file_type': file.content_type,
            'file_size': file.size
        })
        
    except Exception as e:
        logger.error(f"Error en upload: {e}")
        return Response({'error': f'Error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def send_chat_message(request):
    """Enviar mensaje de chat (texto o archivo)"""
    try:
        room_id = request.data.get('room_id')
        content = request.data.get('content', '')
        file_data = request.data.get('file_data')  # Datos del archivo ya subido
        
        if not room_id:
            return Response({'error': 'room_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener user_id del header o del token
        user_id = request.headers.get('X-User-ID') or request.data.get('user_id')
        if not user_id:
            return Response({'error': 'User ID requerido'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que el usuario pertenece a la sala
        admin = get_supabase_admin()
        membership = admin.table('chat_members').select('*').eq('room_id', room_id).eq('user_id', str(user_id)).execute()
        
        if not membership.data:
            return Response({'error': 'No tienes acceso a esta sala'}, status=status.HTTP_403_FORBIDDEN)
        
        # Obtener perfil completo del remitente
        sender_resp = admin.table('User').select('*').eq('userid', str(user_id)).limit(1).execute()
        sender = (getattr(sender_resp, 'data', None) or [None])[0]
        
        # Obtener reseñas del usuario
        reviews_resp = admin.table('reviews').select('rating').eq('reviewed_user_id', str(user_id)).execute()
        reviews = getattr(reviews_resp, 'data', []) or []
        avg_rating = sum([review.get('rating', 0) for review in reviews]) / len(reviews) if reviews else 0
        
        # Obtener intereses del usuario si existen
        interests_resp = admin.table('user_interests').select('interest').eq('user_id', str(user_id)).execute()
        interests = [item.get('interest') for item in (getattr(interests_resp, 'data', []) or [])]
        
        # Preparar datos del perfil de usuario
        user_profile = {
            'id': str(user_id),
            'nombre': sender.get('nombre', ''),
            'apellido': sender.get('apellido', ''),
            'avatar_url': sender.get('avatar_url', ''),
            'descripcion': sender.get('descripcion', ''),
            'avg_rating': avg_rating,
            'reviews_count': len(reviews),
            'interests': interests
        }
        
        # Preparar datos del mensaje
        message_data = {
            'room_id': room_id,
            'user_id': str(user_id),
            'content': content,
            'is_file': bool(file_data),
            'created_at': datetime.utcnow().isoformat(),
            'user_profile': user_profile
        }
        
        # Si es un archivo, agregar información del archivo
        if file_data:
            message_data.update({
                'file_url': file_data.get('file_url'),
                'file_name': file_data.get('file_name'),
                'file_type': file_data.get('file_type'),
                'file_size': file_data.get('file_size')
            })
        
        # Insertar mensaje en la base de datos
        response = admin.table('chat_messages').insert(message_data).execute()
        
        if not response.data:
            return Response({'error': 'Error enviando mensaje'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Crear notificaciones para otros miembros del chat
        try:
            print(f"🔔 Iniciando creación de notificaciones para room_id: {room_id}")
            
            # Obtener información de la sala
            room_resp = admin.table('chat_rooms').select('*').eq('id', room_id).limit(1).execute()
            room = (getattr(room_resp, 'data', None) or [None])[0]
            
            print(f"🔔 Sala encontrada: {room}")
            
            if room:
                # Obtener todos los miembros de la sala excepto el remitente
                members_resp = admin.table('chat_members').select('user_id').eq('room_id', room_id).neq('user_id', str(user_id)).execute()
                members = getattr(members_resp, 'data', []) or []
                
                print(f"🔔 Miembros encontrados: {members}")
                
                # Obtener perfil completo del remitente
                sender_resp = admin.table('User').select('*').eq('userid', str(user_id)).limit(1).execute()
                sender = (getattr(sender_resp, 'data', None) or [None])[0]
                sender_name = f"{sender.get('nombre', '')} {sender.get('apellido', '')}".strip() if sender else 'Un usuario'
                
                # Obtener reseñas del usuario
                reviews_resp = admin.table('reviews').select('rating').eq('reviewed_user_id', str(user_id)).execute()
                reviews = getattr(reviews_resp, 'data', []) or []
                avg_rating = sum([review.get('rating', 0) for review in reviews]) / len(reviews) if reviews else 0
                
                # Obtener intereses del usuario si existen
                interests_resp = admin.table('user_interests').select('interest').eq('user_id', str(user_id)).execute()
                interests = [item.get('interest') for item in (getattr(interests_resp, 'data', []) or [])]
                
                print(f"🔔 Nombre del remitente: {sender_name}")
                
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
                
                print(f"🔔 Tipo de notificación: {notification_type}")
                
                # Crear notificaciones para cada miembro
                created_count = 0
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
                                'is_file': bool(file_data),
                                'user_profile': user_profile
                            }
                        }
                        
                        print(f"🔔 Creando notificación para {member_id}: {notification_data}")
                        insert_resp = admin.table('notifications').insert(notification_data).execute()
                        notification = (getattr(insert_resp, 'data', None) or [None])[0]
                        if notification:
                            created_count += 1
                            print(f"🔔 Notificación creada exitosamente: {notification['id']}")
                
                print(f"🔔 Total de notificaciones creadas: {created_count}")
            else:
                print(f"🔔 No se encontró la sala con ID: {room_id}")
        except Exception as notification_error:
            # No fallar si las notificaciones no se pueden crear
            print(f"🔔 Error creando notificaciones de chat: {notification_error}")
            logger.error(f"Error creando notificaciones de chat: {notification_error}")
        
        return Response({
            'message': 'Mensaje enviado',
            'message_id': response.data[0]['id']
        })
        
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")
        return Response({'error': 'Error interno del servidor'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_chat_messages(request, room_id):
    """Obtener mensajes de una sala de chat"""
    try:
        # Verificar que el usuario pertenece a la sala
        admin = get_supabase_admin()
        membership = admin.table('chat_members').select('*').eq('room_id', room_id).eq('user_id', str(request.user.id)).execute()
        
        if not membership.data:
            return Response({'error': 'No tienes acceso a esta sala'}, status=status.HTTP_403_FORBIDDEN)
        
        # Obtener mensajes con información de archivos
        messages = admin.table('chat_messages_with_files').select('*').eq('room_id', room_id).order('created_at', desc=False).execute()
        
        return Response(messages.data)
        
    except Exception as e:
        logger.error(f"Error obteniendo mensajes: {e}")
        return Response({'error': 'Error interno del servidor'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_user_chat_rooms(request):
    """Obtener salas de chat del usuario"""
    try:
        admin = get_supabase_admin()
        
        # Obtener salas donde el usuario es miembro
        rooms = admin.table('chat_rooms').select('''
            *,
            chat_members!inner(user_id),
            chat_messages(id, content, created_at, is_file, file_name, file_type)
        ''').eq('chat_members.user_id', str(request.user.id)).order('created_at', desc=True).execute()
        
        return Response(rooms.data)
        
    except Exception as e:
        logger.error(f"Error obteniendo salas: {e}")
        return Response({'error': 'Error interno del servidor'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([permissions.AllowAny])
def delete_chat_file(request, message_id):
    """Eliminar archivo de un mensaje"""
    try:
        admin = get_supabase_admin()
        
        # Obtener el mensaje
        message = admin.table('chat_messages').select('*').eq('id', message_id).eq('user_id', str(request.user.id)).execute()
        
        if not message.data:
            return Response({'error': 'Mensaje no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        
        message_data = message.data[0]
        
        if not message_data.get('is_file'):
            return Response({'error': 'Este mensaje no contiene un archivo'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Eliminar archivo del storage
        file_path = message_data.get('file_url', '').split('/')[-1]
        if file_path:
            try:
                admin.storage.from_('chat-files').remove([f"{request.user.id}/{file_path}"])
            except Exception as e:
                logger.warning(f"Error eliminando archivo del storage: {e}")
        
        # Actualizar mensaje para marcar archivo como eliminado
        admin.table('chat_messages').update({
            'file_url': None,
            'file_name': None,
            'file_type': None,
            'file_size': None,
            'is_file': False,
            'content': '[Archivo eliminado]'
        }).eq('id', message_id).execute()
        
        return Response({'message': 'Archivo eliminado'})
        
    except Exception as e:
        logger.error(f"Error eliminando archivo: {e}")
        return Response({'error': 'Error interno del servidor'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_room_file_stats(request, room_id):
    """Obtener estadísticas de archivos de una sala"""
    try:
        # Verificar que el usuario pertenece a la sala
        admin = get_supabase_admin()
        membership = admin.table('chat_members').select('*').eq('room_id', room_id).eq('user_id', str(request.user.id)).execute()
        
        if not membership.data:
            return Response({'error': 'No tienes acceso a esta sala'}, status=status.HTTP_403_FORBIDDEN)
        
        # Obtener estadísticas usando la función SQL
        stats = admin.rpc('get_room_file_stats', {'room_uuid': room_id}).execute()
        
        return Response(stats.data)
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return Response({'error': 'Error interno del servidor'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
