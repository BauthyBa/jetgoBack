from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from api.supabase_client import get_supabase_admin
from os import environ
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TripExpenseCreateView(APIView):
    """Vista para crear gastos de viaje"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            # Datos requeridos
            trip_id = request.data.get('trip_id')
            payer_id = request.data.get('payer_id')
            amount = request.data.get('amount')
            description = request.data.get('description', '').strip()
            category = request.data.get('category')

            if not all([trip_id, payer_id, amount, description, category]):
                return Response({
                    'ok': False, 
                    'error': 'trip_id, payer_id, amount, description y category son requeridos'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validar amount
            try:
                amount = float(amount)
                if amount <= 0:
                    return Response({
                        'ok': False, 
                        'error': 'El monto debe ser mayor a 0'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError):
                return Response({
                    'ok': False, 
                    'error': 'Amount debe ser un número válido'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Verificar que el viaje existe
            try:
                trip_resp = admin.table('trips').select('id,status,creator_id').eq('id', trip_id).limit(1).execute()
                trip = (getattr(trip_resp, 'data', None) or [None])[0]
                
                if not trip:
                    return Response({
                        'ok': False, 
                        'error': 'Viaje no encontrado'
                    }, status=status.HTTP_404_NOT_FOUND)
                    
            except Exception as e:
                logger.error(f"Error verificando viaje: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando el viaje'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Verificar que el usuario es miembro del viaje
            creator_id = str(trip.get('creator_id') or '')
            try:
                member_resp = admin.table('trip_members').select('user_id').eq('trip_id', trip_id).eq('user_id', payer_id).limit(1).execute()
                member = (getattr(member_resp, 'data', None) or [None])[0]
                is_creator = creator_id and str(payer_id) == creator_id
                
                if not member:
                    # Registrar al pagador (y al creador si falta) como miembros para poder seguir
                    to_seed = []
                    if is_creator:
                        to_seed.append({'trip_id': trip_id, 'user_id': str(payer_id), 'role': 'owner'})
                    else:
                        to_seed.append({'trip_id': trip_id, 'user_id': str(payer_id), 'role': 'member'})
                    if creator_id and creator_id != str(payer_id):
                        to_seed.append({'trip_id': trip_id, 'user_id': creator_id, 'role': 'owner'})
                    try:
                        admin.table('trip_members').insert(to_seed).execute()
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Error verificando membresía: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando membresía del viaje'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Obtener todos los miembros del viaje para crear las divisiones
            try:
                members_resp = admin.table('trip_members').select('user_id').eq('trip_id', trip_id).execute()
                members = getattr(members_resp, 'data', None) or []
                if not members:
                    # Si no hay registros, poblar con el creador y el pagador y continuar
                    seed_ids = []
                    creator_id = str(trip.get('creator_id') or '')
                    if creator_id:
                        seed_ids.append((creator_id, 'owner'))
                    if str(payer_id) and str(payer_id) != creator_id:
                        seed_ids.append((str(payer_id), 'member'))
                    if seed_ids:
                        try:
                            admin.table('trip_members').insert([
                                {'trip_id': trip_id, 'user_id': uid, 'role': role} for uid, role in seed_ids
                            ]).execute()
                            members = [{'user_id': uid} for uid, _ in seed_ids]
                        except Exception as se:
                            logger.warning(f"No se pudo inicializar miembros del viaje {trip_id}: {se}")
                            members = [{'user_id': str(payer_id)}]
                    else:
                        members = [{'user_id': str(payer_id)}]
                    
            except Exception as e:
                logger.error(f"Error obteniendo miembros: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error obteniendo miembros del viaje'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Preparar datos del gasto
            expense_data = {
                'trip_id': trip_id,
                'payer_id': payer_id,
                'amount': amount,
                'currency': request.data.get('currency', 'USD'),
                'description': description,
                'category': category,
                'expense_date': request.data.get('expense_date', datetime.now().isoformat()),
                'location': request.data.get('location', ''),
                'notes': request.data.get('notes', ''),
                'receipt_url': request.data.get('receipt_url'),
                'receipt_filename': request.data.get('receipt_filename'),
                'status': 'pending'
            }

            # Crear el gasto
            try:
                expense_resp = admin.table('trip_expenses').insert(expense_data).execute()
                expense = (getattr(expense_resp, 'data', None) or [None])[0]
                
                if not expense:
                    return Response({
                        'ok': False, 
                        'error': 'Error creando el gasto'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Crear divisiones para todos los miembros
                amount_per_person = amount / len(members)
                splits_data = []
                
                for member in members:
                    user_id = member['user_id']
                    # El que pagó no debe nada, los demás deben su parte
                    amount_owed = 0 if user_id == payer_id else amount_per_person
                    
                    splits_data.append({
                        'expense_id': expense['id'],
                        'user_id': user_id,
                        'amount_owed': amount_owed,
                        'amount_paid': amount_per_person if user_id == payer_id else 0,
                        'is_settled': user_id == payer_id
                    })

                # Insertar todas las divisiones
                splits_resp = admin.table('trip_expense_splits').insert(splits_data).execute()
                splits = getattr(splits_resp, 'data', None) or []

                return Response({
                    'ok': True, 
                    'data': {
                        'expense': expense,
                        'splits': splits
                    },
                    'message': 'Gasto creado exitosamente'
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error creando gasto: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': f'Error creando el gasto: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error general en TripExpenseCreateView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripExpenseListView(APIView):
    """Vista para listar gastos de un viaje"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            trip_id = request.query_params.get('trip_id')
            user_id = request.query_params.get('user_id')
            category = request.query_params.get('category')
            status_filter = request.query_params.get('status')
            limit = int(request.query_params.get('limit', 20))
            offset = int(request.query_params.get('offset', 0))

            if not trip_id:
                return Response({
                    'ok': False, 
                    'error': 'trip_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Construir query
            query = admin.table('trip_expenses').select('''
                *,
                payer:User!trip_expenses_payer_id_fkey(userid, nombre, apellido, avatar_url),
                splits:trip_expense_splits(
                    *,
                    user:User!trip_expense_splits_user_id_fkey(userid, nombre, apellido, avatar_url)
                ),
                comments:trip_expense_comments(
                    *,
                    user:User!trip_expense_comments_user_id_fkey(userid, nombre, apellido, avatar_url)
                )
            ''')

            # Aplicar filtros
            query = query.eq('trip_id', trip_id)
            
            if user_id:
                # Filtrar gastos donde el usuario está involucrado
                query = query.or_(f'payer_id.eq.{user_id},splits.user_id.eq.{user_id}')
            
            if category:
                query = query.eq('category', category)
            
            if status_filter:
                query = query.eq('status', status_filter)

            # Ordenar por fecha de gasto (más recientes primero)
            query = query.order('expense_date', desc=True)
            query = query.range(offset, offset + limit - 1)

            try:
                resp = query.execute()
                expenses = getattr(resp, 'data', None) or []
            except Exception as qerr:
                logger.warning(f"Fallo query enriquecida de gastos, usando fallback simple: {qerr}")
                # Fallback: seleccionar solo columnas básicas sin joins
                try:
                    resp = (
                        admin.table('trip_expenses')
                        .select('id,trip_id,payer_id,amount,currency,description,category,expense_date,created_at,updated_at,status')
                        .eq('trip_id', trip_id)
                        .order('expense_date', desc=True)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )
                    expenses = getattr(resp, 'data', None) or []
                except Exception as fb_err:
                    logger.error(f"Fallback de gastos también falló: {fb_err}")
                    return Response({
                        'ok': False,
                        'error': 'No se pudieron cargar los gastos'
                    }, status=status.HTTP_400_BAD_REQUEST)

            # Enriquecer splits cuando no vienen por join
            try:
                ids = [e.get('id') for e in expenses if e.get('id')]
                if ids:
                    splits_resp = admin.table('trip_expense_splits').select('expense_id,user_id,amount_owed,amount_paid,is_settled').in_('expense_id', ids).execute()
                    splits = getattr(splits_resp, 'data', None) or []
                    # Mapear usuarios de splits y payers
                    user_ids = {s.get('user_id') for s in splits if s.get('user_id')}
                    payer_ids = {e.get('payer_id') for e in expenses if e.get('payer_id')}
                    all_user_ids = {str(u) for u in (user_ids | payer_ids) if u}
                    user_map = {}
                    if all_user_ids:
                        users_resp = admin.table('User').select('userid,nombre,apellido').in_('userid', list(all_user_ids)).execute()
                        users = getattr(users_resp, 'data', None) or []
                        user_map = {u.get('userid'): u for u in users}
                    by_expense = {}
                    for s in splits:
                        eid = s.get('expense_id')
                        if not eid:
                            continue
                        if eid not in by_expense:
                            by_expense[eid] = []
                        u = user_map.get(str(s.get('user_id')))
                        s_copy = dict(s)
                        if u:
                            s_copy['user'] = {'userid': u.get('userid'), 'nombre': u.get('nombre'), 'apellido': u.get('apellido')}
                        by_expense[eid].append(s_copy)
                    for e in expenses:
                        if e.get('id') in by_expense:
                            e['splits'] = by_expense[e.get('id')]
                    # Enriquecer nombres de pagador si falta
                    for e in expenses:
                        pid = str(e.get('payer_id'))
                        if pid and not e.get('payer') and pid in user_map:
                            u = user_map[pid]
                            e['payer'] = {'userid': pid, 'nombre': u.get('nombre'), 'apellido': u.get('apellido')}
                            e['payer_full_name'] = f"{u.get('nombre','')} {u.get('apellido','')}".strip()
                            e['payer_name'] = u.get('nombre')
            except Exception as enrich_splits_err:
                logger.warning(f"No se pudieron enriquecer splits/nombres: {enrich_splits_err}")

            # Enriquecer con nombres de pagador si no vienen del join
            try:
                missing_payer_name = any(not e.get('payer') for e in expenses)
                if missing_payer_name:
                    payer_ids = {str(e.get('payer_id')) for e in expenses if e.get('payer_id')}
                    if payer_ids:
                        users_resp = admin.table('User').select('userid,nombre,apellido').in_('userid', list(payer_ids)).execute()
                        users = getattr(users_resp, 'data', None) or []
                        user_map = {u.get('userid'): u for u in users}
                        for e in expenses:
                            pid = str(e.get('payer_id'))
                            u = user_map.get(pid)
                            if u:
                                e['payer_name'] = f"{u.get('nombre','')}".strip()
                                e['payer_full_name'] = f"{u.get('nombre','')} {u.get('apellido','')}".strip()
            except Exception as enrich_err:
                logger.warning(f"No se pudieron enriquecer gastos con nombres de pagador: {enrich_err}")

            return Response({
                'ok': True,
                'expenses': expenses,
                'data': expenses,
                'count': len(expenses)
            })

        except Exception as e:
            logger.error(f"Error en TripExpenseListView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripExpenseDetailView(APIView):
    """Vista para obtener detalles de un gasto específico"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, expense_id, *args, **kwargs):
        try:
            admin = get_supabase_admin()

            resp = admin.table('trip_expenses').select('''
                *,
                payer:User!trip_expenses_payer_id_fkey(userid, nombre, apellido, avatar_url),
                splits:trip_expense_splits(
                    *,
                    user:User!trip_expense_splits_user_id_fkey(userid, nombre, apellido, avatar_url)
                ),
                comments:trip_expense_comments(
                    *,
                    user:User!trip_expense_comments_user_id_fkey(userid, nombre, apellido, avatar_url)
                ),
                payments:trip_expense_payments(
                    *,
                    from_user:User!trip_expense_payments_from_user_id_fkey(userid, nombre, apellido, avatar_url),
                    to_user:User!trip_expense_payments_to_user_id_fkey(userid, nombre, apellido, avatar_url)
                )
            ''').eq('id', expense_id).limit(1).execute()

            expense = (getattr(resp, 'data', None) or [None])[0]

            if not expense:
                return Response({
                    'ok': False, 
                    'error': 'Gasto no encontrado'
                }, status=status.HTTP_404_NOT_FOUND)

            return Response({
                'ok': True,
                'data': expense
            })

        except Exception as e:
            logger.error(f"Error en TripExpenseDetailView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripExpenseUpdateView(APIView):
    """Vista para actualizar un gasto existente"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def put(self, request, expense_id, *args, **kwargs):
        try:
            user_id = request.data.get('user_id')
            
            if not user_id:
                return Response({
                    'ok': False, 
                    'error': 'user_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Verificar que el gasto existe y el usuario tiene permisos
            try:
                expense_resp = admin.table('trip_expenses').select('payer_id').eq('id', expense_id).limit(1).execute()
                expense = (getattr(expense_resp, 'data', None) or [None])[0]
                
                if not expense:
                    return Response({
                        'ok': False, 
                        'error': 'Gasto no encontrado'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                if expense.get('payer_id') != user_id:
                    return Response({
                        'ok': False, 
                        'error': 'Solo el que pagó puede editar este gasto'
                    }, status=status.HTTP_403_FORBIDDEN)
                    
            except Exception as e:
                logger.error(f"Error verificando gasto: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando el gasto'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Preparar datos para actualizar
            update_data = {}
            allowed_fields = [
                'amount', 'currency', 'description', 'category', 
                'expense_date', 'location', 'notes', 'receipt_url', 'receipt_filename'
            ]

            for field in allowed_fields:
                if field in request.data:
                    update_data[field] = request.data[field]

            if not update_data:
                return Response({
                    'ok': False, 
                    'error': 'No hay datos para actualizar'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Actualizar el gasto
            try:
                resp = admin.table('trip_expenses').update(update_data).eq('id', expense_id).execute()
                updated_expense = (getattr(resp, 'data', None) or [None])[0]
                
                if not updated_expense:
                    return Response({
                        'ok': False, 
                        'error': 'Error actualizando el gasto'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                return Response({
                    'ok': True, 
                    'data': updated_expense,
                    'message': 'Gasto actualizado exitosamente'
                })
                
            except Exception as e:
                logger.error(f"Error actualizando gasto: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': f'Error actualizando el gasto: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error general en TripExpenseUpdateView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripExpenseDeleteView(APIView):
    """Vista para eliminar un gasto"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def delete(self, request, expense_id, *args, **kwargs):
        try:
            user_id = request.data.get('user_id')
            
            if not user_id:
                return Response({
                    'ok': False, 
                    'error': 'user_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Verificar que el gasto existe y el usuario tiene permisos
            try:
                expense_resp = admin.table('trip_expenses').select('payer_id').eq('id', expense_id).limit(1).execute()
                expense = (getattr(expense_resp, 'data', None) or [None])[0]
                
                if not expense:
                    return Response({
                        'ok': False, 
                        'error': 'Gasto no encontrado'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                if expense.get('payer_id') != user_id:
                    return Response({
                        'ok': False, 
                        'error': 'Solo el que pagó puede eliminar este gasto'
                    }, status=status.HTTP_403_FORBIDDEN)
                    
            except Exception as e:
                logger.error(f"Error verificando gasto: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': 'Error verificando el gasto'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Eliminar el gasto (las divisiones se eliminan por CASCADE)
            try:
                admin.table('trip_expenses').delete().eq('id', expense_id).execute()

                return Response({
                    'ok': True, 
                    'message': 'Gasto eliminado exitosamente'
                })
                
            except Exception as e:
                logger.error(f"Error eliminando gasto: {str(e)}")
                return Response({
                    'ok': False, 
                    'error': f'Error eliminando el gasto: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error general en TripExpenseDeleteView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TripExpenseCategoriesView(APIView):
    """Vista para obtener las categorías de gastos disponibles"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        default_categories = [
            {'id': 'comida', 'name': 'Comida', 'icon': '🍽️', 'color': '#F59E0B'},
            {'id': 'transporte', 'name': 'Transporte', 'icon': '🚗', 'color': '#3B82F6'},
            {'id': 'estadia', 'name': 'Estadía', 'icon': '🏨', 'color': '#10B981'},
            {'id': 'actividades', 'name': 'Actividades', 'icon': '🎯', 'color': '#8B5CF6'},
            {'id': 'compras', 'name': 'Compras', 'icon': '🛍️', 'color': '#EF4444'},
            {'id': 'otros', 'name': 'Otros', 'icon': '📝', 'color': '#6B7280'},
        ]
        try:
            admin = get_supabase_admin()
            resp = admin.table('expense_categories').select('*').eq('is_active', True).order('name').execute()
            categories = getattr(resp, 'data', None) or default_categories
        except Exception as e:
            logger.warning(f"No se pudo leer expense_categories, devolviendo por defecto: {e}")
            categories = default_categories

        return Response({
            'ok': True,
            'data': categories
        })


class TripExpenseSummaryView(APIView):
    """Vista para obtener resumen de gastos de un viaje"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            trip_id = request.query_params.get('trip_id')
            user_id = request.query_params.get('user_id')
            
            if not trip_id:
                return Response({
                    'ok': False, 
                    'error': 'trip_id es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)

            admin = get_supabase_admin()

            # Obtener resumen usando la función SQL
            try:
                summary_resp = admin.rpc('get_trip_expenses_summary', {'trip_uuid': trip_id}).execute()
                summary = (getattr(summary_resp, 'data', None) or [None])[0]
                
                if not summary:
                    summary = {
                        'total_expenses': 0,
                        'total_paid': 0,
                        'total_owed': 0,
                        'currency': 'USD',
                        'expense_count': 0
                    }
            except Exception as e:
                logger.error(f"Error obteniendo resumen: {str(e)}")
                # Fallback: calcular manualmente
                expenses_resp = admin.table('trip_expenses').select('amount,currency').eq('trip_id', trip_id).execute()
                expenses = getattr(expenses_resp, 'data', None) or []
                
                total_expenses = sum(float(exp.get('amount', 0)) for exp in expenses)
                currency = expenses[0].get('currency', 'USD') if expenses else 'USD'
                
                summary = {
                    'total_expenses': total_expenses,
                    'total_paid': total_expenses,
                    'total_owed': total_expenses,
                    'currency': currency,
                    'expense_count': len(expenses)
                }

            # Si se especifica user_id, obtener balance del usuario
            user_balance = None
            if user_id:
                try:
                    balance_resp = admin.rpc('calculate_user_balance', {
                        'trip_uuid': trip_id, 
                        'user_uuid': user_id
                    }).execute()
                    user_balance = (getattr(balance_resp, 'data', None) or [None])[0]
                except Exception as e:
                    logger.error(f"Error calculando balance del usuario: {str(e)}")
                    user_balance = {
                        'total_owed': 0,
                        'total_paid': 0,
                        'balance': 0
                    }

            return Response({
                'ok': True,
                'data': {
                    'summary': summary,
                    'user_balance': user_balance
                }
            })

        except Exception as e:
            logger.error(f"Error en TripExpenseSummaryView: {str(e)}")
            return Response({
                'ok': False, 
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
