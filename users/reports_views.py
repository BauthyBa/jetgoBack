from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from api.supabase_client import get_supabase_admin
import logging

logger = logging.getLogger(__name__)

class CreateUserReportView(APIView):
    """Vista para crear reportes de usuarios usando Supabase"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            reporter_id = request.data.get('reporter_id')
            reported_user_id = request.data.get('reported_user_id')
            reason = request.data.get('reason')
            description = request.data.get('description', '')
            evidence_image_url = request.data.get('evidence_image_url', '')

            logger.info(f'Creando reporte: reporter={reporter_id}, reported={reported_user_id}, reason={reason}')

            # Validaciones básicas
            if not reporter_id or not reported_user_id or not reason:
                logger.error('Faltan campos requeridos')
                return Response({
                    'ok': False, 
                    'error': 'reporter_id, reported_user_id y reason son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)

            if reporter_id == reported_user_id:
                logger.error('Intento de auto-reporte')
                return Response({
                    'ok': False, 
                    'error': 'No puedes reportarte a ti mismo'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validar motivo
            valid_reasons = [
                'Comportamiento inapropiado',
                'Cancelación sin aviso',
                'Conducta sospechosa o engañosa',
                'Incumplimiento de las normas de la app',
                'Problemas con el pago o gastos',
                'Conducción peligrosa o imprudente',
                'Falta de higiene o condiciones inapropiadas del vehículo',
                'Acoso o comportamiento sexual inapropiado',
                'Perfil falso o suplantación de identidad',
                'Otro motivo'
            ]

            if reason not in valid_reasons:
                logger.error(f'Motivo inválido: {reason}')
                return Response({
                    'ok': False, 
                    'error': 'Motivo de reporte no válido'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Crear reporte directamente (sin verificaciones complejas por ahora)
            try:
                admin = get_supabase_admin()
                
                report_data = {
                    'reporter_id': reporter_id,
                    'reported_user_id': reported_user_id,
                    'reason': reason,
                    'description': description,
                    'status': 'pending'
                }
                
                if evidence_image_url:
                    report_data['evidence_image_url'] = evidence_image_url
                
                logger.info(f'Insertando reporte: {report_data}')
                insert_resp = admin.table('user_reports').insert(report_data).execute()
                
                if hasattr(insert_resp, 'data') and insert_resp.data:
                    new_report = insert_resp.data[0]
                    logger.info(f'Reporte creado exitosamente: {new_report.get("id")}')
                    return Response({
                        'ok': True,
                        'report': new_report,
                        'message': 'Reporte enviado exitosamente. Será revisado por nuestro equipo.'
                    }, status=status.HTTP_201_CREATED)
                else:
                    logger.error(f'Error en respuesta de Supabase: {insert_resp}')
                    return Response({
                        'ok': False, 
                        'error': 'Error al crear el reporte en la base de datos'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            except Exception as e:
                logger.error(f'Error al crear reporte: {str(e)}')
                return Response({
                    'ok': False, 
                    'error': f'Error al crear reporte: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f'Error general en CreateUserReportView: {str(e)}')
            return Response({
                'ok': False, 
                'error': f'Error interno: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetUserReportsView(APIView):
    """Vista para obtener reportes de un usuario"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            user_id = request.query_params.get('user_id')
            report_type = request.query_params.get('type', 'received')  # 'received' o 'made'
            
            if not user_id:
                return Response({
                    'ok': False, 
                    'error': 'user_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            try:
                if report_type == 'made':
                    # Reportes hechos por el usuario
                    reports_resp = admin.table('user_reports').select('*').eq('reporter_id', user_id).order('created_at', desc=True).execute()
                else:
                    # Reportes recibidos por el usuario
                    reports_resp = admin.table('user_reports').select('*').eq('reported_user_id', user_id).order('created_at', desc=True).execute()
                
                reports = getattr(reports_resp, 'data', []) or []

                # Obtener estadísticas
                stats_resp = admin.table('user_report_stats').select('*').eq('reported_user_id', user_id).limit(1).execute()
                stats = (getattr(stats_resp, 'data', None) or [None])[0] or {
                    'total_reports': 0,
                    'pending_reports': 0,
                    'resolved_reports': 0,
                    'dismissed_reports': 0
                }

                return Response({
                    'ok': True,
                    'reports': reports,
                    'statistics': stats
                })

            except Exception as e:
                return Response({
                    'ok': False, 
                    'error': f'Error obteniendo reportes: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class CheckUserSuspensionView(APIView):
    """Vista para verificar si un usuario está suspendido"""
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

            try:
                # Verificar suspensiones activas
                suspension_resp = admin.table('user_suspensions').select('*').eq('user_id', user_id).eq('is_active', True).order('suspended_at', desc=True).limit(1).execute()
                suspension = (getattr(suspension_resp, 'data', None) or [None])[0]

                is_suspended = False
                suspension_info = None

                if suspension:
                    # Verificar si la suspensión sigue vigente
                    if suspension.get('is_permanent') or (suspension.get('expires_at') and suspension['expires_at'] > 'now()'):
                        is_suspended = True
                        suspension_info = {
                            'reason': suspension.get('reason'),
                            'suspended_at': suspension.get('suspended_at'),
                            'expires_at': suspension.get('expires_at'),
                            'is_permanent': suspension.get('is_permanent', False),
                            'notes': suspension.get('notes')
                        }

                return Response({
                    'ok': True,
                    'is_suspended': is_suspended,
                    'suspension_info': suspension_info
                })

            except Exception as e:
                return Response({
                    'ok': False, 
                    'error': f'Error verificando suspensión: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class GetReportReasonsView(APIView):
    """Vista para obtener los motivos de reporte disponibles"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        reasons = [
            {
                'value': 'Comportamiento inapropiado',
                'label': 'Comportamiento inapropiado',
                'description': 'Lenguaje ofensivo, actitudes agresivas o faltas de respeto en el chat o en persona'
            },
            {
                'value': 'Cancelación sin aviso',
                'label': 'Cancelación sin aviso',
                'description': 'El usuario canceló el viaje a último momento o no se presentó sin justificarlo'
            },
            {
                'value': 'Conducta sospechosa o engañosa',
                'label': 'Conducta sospechosa o engañosa',
                'description': 'El usuario dio información falsa, intentó estafar o comportarse de manera extraña'
            },
            {
                'value': 'Incumplimiento de las normas de la app',
                'label': 'Incumplimiento de las normas de la app',
                'description': 'No respetó las reglas del servicio o los términos de uso'
            },
            {
                'value': 'Problemas con el pago o gastos',
                'label': 'Problemas con el pago o gastos',
                'description': 'No pagó su parte del viaje o hubo conflictos con el dinero acordado'
            },
            {
                'value': 'Conducción peligrosa o imprudente',
                'label': 'Conducción peligrosa o imprudente',
                'description': 'En caso de que sea el conductor y maneje de forma riesgosa o irresponsable'
            },
            {
                'value': 'Falta de higiene o condiciones inapropiadas del vehículo',
                'label': 'Falta de higiene o condiciones inapropiadas del vehículo',
                'description': 'Si el viaje fue incómodo por falta de limpieza, olores, etc.'
            },
            {
                'value': 'Acoso o comportamiento sexual inapropiado',
                'label': 'Acoso o comportamiento sexual inapropiado',
                'description': 'Cualquier tipo de insinuación, acoso o conducta que genere incomodidad'
            },
            {
                'value': 'Perfil falso o suplantación de identidad',
                'label': 'Perfil falso o suplantación de identidad',
                'description': 'El usuario no coincide con su foto o datos del perfil'
            },
            {
                'value': 'Otro motivo',
                'label': 'Otro motivo',
                'description': 'Opción para escribir libremente una descripción del incidente'
            }
        ]

        return Response({
            'ok': True,
            'reasons': reasons
        })
