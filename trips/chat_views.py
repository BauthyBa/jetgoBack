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
from datetime import datetime

logger = logging.getLogger(__name__)

# Tipos de archivo permitidos
ALLOWED_FILE_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf', 'text/plain',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

# Tamaño máximo de archivo (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


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
        
        # Validar tipo de archivo
        if file.content_type not in ALLOWED_FILE_TYPES:
            return Response({'error': 'Tipo de archivo no permitido'}, status=status.HTTP_400_BAD_REQUEST)
        
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
            upload_response = admin.storage.from_('chat-files').upload(
                file_path,
                file_content,
                file_options={
                    'content-type': file.content_type,
                    'cache-control': '3600'
                }
            )
            
            logger.info(f"Upload response: {upload_response}")
            
            # Verificar si hubo error en el upload
            if hasattr(upload_response, 'error') and upload_response.error:
                logger.error(f"Error subiendo archivo: {upload_response.error}")
                return Response({'error': 'Error subiendo archivo'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Obtener URL pública del archivo
            file_url = admin.storage.from_('chat-files').get_public_url(file_path)
            logger.info(f"File URL: {file_url}")
            
        except Exception as e:
            logger.error(f"Error subiendo archivo: {e}")
            return Response({'error': f'Error subiendo archivo: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Crear mensaje con archivo
        message_data = {
            'room_id': room_id,
            'user_id': str(user_id),
            'content': f"📎 {file.name}",
            'is_file': True,
            'file_url': file_url,
            'file_name': file.name,
            'file_type': file.content_type,
            'file_size': file.size,
            'created_at': datetime.utcnow().isoformat()
        }
        
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
        
        # Preparar datos del mensaje
        message_data = {
            'room_id': room_id,
            'user_id': str(user_id),
            'content': content,
            'is_file': bool(file_data),
            'created_at': datetime.utcnow().isoformat()
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
