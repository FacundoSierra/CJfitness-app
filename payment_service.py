"""
Servicio simplificado para el sistema de pagos
Funciona con la estructura básica de la base de datos de Render
"""

from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
from models import db, Pago, Usuario, Plan, ConfiguracionPagoMensual

class PaymentService:
    def __init__(self):
        """Inicializa el servicio de pagos"""
        pass
    
    def configurar_pago_mensual(self, usuario_id: int, cantidad: float, 
                               metodo_pago: str, forma_pago: str = None,
                               dia_vencimiento: int = 1) -> Dict:
        """
        Configura el pago mensual para un usuario
        """
        try:
            # Validar usuario
            usuario = Usuario.query.get(usuario_id)
            if not usuario:
                return {'success': False, 'error': 'Usuario no encontrado'}
            
            # Validar día de vencimiento
            if not 1 <= dia_vencimiento <= 31:
                return {'success': False, 'error': 'El día de vencimiento debe estar entre 1 y 31'}
            
            # Buscar configuración existente
            config_existente = ConfiguracionPagoMensual.query.filter_by(
                usuario_id=usuario_id, activo=True
            ).first()
            
            if config_existente:
                # Actualizar configuración existente
                config_existente.cantidad_mensual = cantidad
                config_existente.metodo_pago = metodo_pago
                config_existente.forma_pago = forma_pago
                config_existente.dia_vencimiento = dia_vencimiento
                config_existente.fecha_ultima_modificacion = datetime.utcnow()
            else:
                # Crear nueva configuración
                nueva_config = ConfiguracionPagoMensual(
                    usuario_id=usuario_id,
                    cantidad_mensual=cantidad,
                    metodo_pago=metodo_pago,
                    forma_pago=forma_pago,
                    dia_vencimiento=dia_vencimiento
                )
                db.session.add(nueva_config)
            
            db.session.commit()
            
            return {
                'success': True,
                'mensaje': 'Configuración de pago mensual guardada correctamente'
            }
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error en configurar_pago_mensual: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def generar_pagos_mensuales(self, mes: str = None) -> Dict:
        """
        Genera los pagos mensuales para todos los usuarios activos
        mes: formato YYYY-MM, si no se especifica usa el mes actual
        """
        try:
            if not mes:
                hoy = date.today()
                mes = f"{hoy.year}-{hoy.month:02d}"
            
            # Obtener todas las configuraciones activas
            configuraciones = ConfiguracionPagoMensual.query.filter_by(activo=True).all()
            
            pagos_creados = 0
            errores = []
            
            for config in configuraciones:
                try:
                    # Verificar si ya existe un pago para este usuario en este mes
                    pago_existente = Pago.query.filter_by(
                        usuario_id=config.usuario_id,
                        mes_pago=mes
                    ).first()
                    
                    if pago_existente:
                        continue  # Ya existe un pago para este mes
                    
                    # Calcular fecha de vencimiento
                    año, mes_num = map(int, mes.split('-'))
                    dia_vencimiento = min(config.dia_vencimiento, 28)  # Evitar problemas con febrero
                    
                    try:
                        fecha_vencimiento = date(año, mes_num, dia_vencimiento)
                    except ValueError:
                        # Si el día no existe en el mes, usar el último día del mes
                        if mes_num == 2:
                            fecha_vencimiento = date(año, 2, 28)
                        else:
                            fecha_vencimiento = date(año, mes_num, 1) + timedelta(days=32)
                            fecha_vencimiento = fecha_vencimiento.replace(day=1) - timedelta(days=1)
                    
                    # Crear el pago mensual
                    nuevo_pago = Pago(
                        usuario_id=config.usuario_id,
                        fecha_pago=date.today(),  # Fecha de creación
                        cantidad=config.cantidad_mensual,
                        estado='pendiente',
                        metodo_pago=config.metodo_pago,
                        forma_pago=config.forma_pago,
                        mes_pago=mes,
                        fecha_vencimiento=fecha_vencimiento,
                        observaciones=f"Pago mensual {mes}"
                    )
                    
                    db.session.add(nuevo_pago)
                    pagos_creados += 1
                    
                except Exception as e:
                    errores.append(f"Usuario {config.usuario_id}: {str(e)}")
            
            db.session.commit()
            
            return {
                'success': True,
                'pagos_creados': pagos_creados,
                'errores': errores,
                'mes': mes
            }
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error en generar_pagos_mensuales: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def registrar_pago(self, usuario_id: int, cantidad: float, 
                      metodo_pago: str, forma_pago: str = None,
                      observaciones: str = None, mes_pago: str = None) -> Dict:
        """
        Registra un pago manual en el sistema
        """
        try:
            # Validar usuario
            usuario = Usuario.query.get(usuario_id)
            if not usuario:
                return {'success': False, 'error': 'Usuario no encontrado'}
            
            # Usar mes actual si no se especifica
            if not mes_pago:
                hoy = date.today()
                mes_pago = f"{hoy.year}-{hoy.month:02d}"
            
            # Crear pago
            nuevo_pago = Pago(
                usuario_id=usuario_id,
                fecha_pago=date.today(),
                cantidad=cantidad,
                estado='pagado',  # Los pagos manuales se marcan como pagados
                metodo_pago=metodo_pago,
                forma_pago=forma_pago,
                mes_pago=mes_pago,
                observaciones=observaciones
            )
            
            db.session.add(nuevo_pago)
            db.session.commit()
            
            return {
                'success': True,
                'pago_id': nuevo_pago.id,
                'mensaje': 'Pago registrado correctamente'
            }
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error en registrar_pago: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def obtener_pagos_usuario(self, usuario_id: int) -> List[Dict]:
        """Obtiene todos los pagos de un usuario"""
        try:
            pagos = Pago.query.filter_by(usuario_id=usuario_id).order_by(Pago.fecha_pago.desc()).all()
            
            return [{
                'id': pago.id,
                'fecha_pago': pago.fecha_pago.strftime('%Y-%m-%d'),
                'cantidad': float(pago.cantidad),
                'estado': pago.estado,
                'metodo_pago': pago.metodo_pago,
                'forma_pago': pago.forma_pago,
                'mes_pago': pago.mes_pago,
                'fecha_vencimiento': pago.fecha_vencimiento.strftime('%Y-%m-%d') if pago.fecha_vencimiento else None,
                'observaciones': pago.observaciones
            } for pago in pagos]
            
        except Exception as e:
            return []
    
    def obtener_pagos_admin(self, estado: str = None, fecha_inicio: str = None, 
                           fecha_fin: str = None, usuario_id: int = None, limit: int = None) -> List[Dict]:
        """Obtiene pagos para el dashboard del admin con filtros"""
        try:
            query = Pago.query
            
            # Aplicar filtros
            if estado:
                query = query.filter_by(estado=estado)
            if usuario_id:
                query = query.filter_by(usuario_id=usuario_id)
            if fecha_inicio:
                fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
                query = query.filter(Pago.fecha_pago >= fecha_inicio_obj)
            if fecha_fin:
                fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
                query = query.filter(Pago.fecha_pago <= fecha_fin_obj)
            
            # Ordenar y limitar
            query = query.order_by(Pago.fecha_pago.desc())
            if limit:
                query = query.limit(limit)
            
            pagos = query.all()
            
            return [{
                'id': pago.id,
                'usuario_id': pago.usuario_id,
                'usuario_nombre': pago.usuario.nombre + ' ' + pago.usuario.apellidos,
                'fecha_pago': pago.fecha_pago.strftime('%Y-%m-%d'),
                'cantidad': float(pago.cantidad),
                'estado': pago.estado,
                'metodo_pago': pago.metodo_pago,
                'forma_pago': pago.forma_pago,
                'mes_pago': pago.mes_pago,
                'fecha_vencimiento': pago.fecha_vencimiento.strftime('%Y-%m-%d') if pago.fecha_vencimiento else None,
                'observaciones': pago.observaciones
            } for pago in pagos]
            
        except Exception as e:
            return []
    
    def obtener_estadisticas_pagos(self) -> Dict:
        """Obtiene estadísticas de pagos para el dashboard del admin"""
        try:
            total_pagos = Pago.query.count()
            pagos_pendientes = Pago.query.filter_by(estado='pendiente').count()
            pagos_pagados = Pago.query.filter_by(estado='pagado').count()
            
            # Ingresos del mes actual
            hoy = date.today()
            primer_dia_mes = date(hoy.year, hoy.month, 1)
            
            ingresos_mes = db.session.query(db.func.sum(Pago.cantidad)).filter(
                Pago.fecha_pago >= primer_dia_mes,
                Pago.estado == 'pagado'
            ).scalar() or 0
            
            # Ingresos totales
            ingresos_totales = db.session.query(db.func.sum(Pago.cantidad)).filter(
                Pago.estado == 'pagado'
            ).scalar() or 0
            
            return {
                'total_pagos': total_pagos,
                'pagos_pendientes': pagos_pendientes,
                'pagos_pagados': pagos_pagados,
                'ingresos_mes': float(ingresos_mes),
                'ingresos_totales': float(ingresos_totales)
            }
            
        except Exception as e:
            return {
                'total_pagos': 0,
                'pagos_pendientes': 0,
                'pagos_pagados': 0,
                'ingresos_mes': 0.0,
                'ingresos_totales': 0.0
            }
    
    def verificar_estado_premium(self, usuario_id: int) -> Dict:
        """Verifica el estado premium de un usuario"""
        try:
            # Buscar pagos recientes del usuario
            pagos_recientes = Pago.query.filter_by(
                usuario_id=usuario_id,
                estado='pagado'
            ).order_by(Pago.fecha_pago.desc()).limit(1).first()
            
            if pagos_recientes:
                return {
                    'premium': True,
                    'ultimo_pago': pagos_recientes.fecha_pago.strftime('%Y-%m-%d'),
                    'cantidad': float(pagos_recientes.cantidad)
                }
            else:
                return {'premium': False}
                
        except Exception as e:
            return {'premium': False, 'error': str(e)}
    
    def cambiar_estado_pago(self, pago_id: int, nuevo_estado: str, admin_id: int = None) -> Dict:
        """Cambia el estado de un pago (pendiente -> pagado, pagado -> pendiente, etc.)"""
        try:
            pago = Pago.query.get(pago_id)
            if not pago:
                return {'success': False, 'error': 'Pago no encontrado'}
            
            # Validar estado válido
            estados_validos = ['pendiente', 'pagado', 'cancelado']
            if nuevo_estado not in estados_validos:
                return {'success': False, 'error': f'Estado inválido. Estados válidos: {", ".join(estados_validos)}'}
            
            # Si se está marcando como pagado, actualizar fecha de pago
            if nuevo_estado == 'pagado':
                pago.fecha_pago = date.today()
            
            pago.estado = nuevo_estado
            
            db.session.commit()
            
            return {
                'success': True,
                'mensaje': f'Estado del pago cambiado a {nuevo_estado}',
                'pago_id': pago_id,
                'nuevo_estado': nuevo_estado
            }
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error en cambiar_estado_pago: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def obtener_configuracion_pago_mensual(self, usuario_id: int) -> Dict:
        """Obtiene la configuración de pago mensual de un usuario"""
        try:
            config = ConfiguracionPagoMensual.query.filter_by(
                usuario_id=usuario_id, activo=True
            ).first()
            
            if not config:
                return {'success': False, 'error': 'No hay configuración de pago mensual'}
            
            return {
                'success': True,
                'configuracion': {
                    'id': config.id,
                    'cantidad_mensual': float(config.cantidad_mensual),
                    'metodo_pago': config.metodo_pago,
                    'forma_pago': config.forma_pago,
                    'dia_vencimiento': config.dia_vencimiento,
                    'fecha_creacion': config.fecha_creacion.strftime('%Y-%m-%d'),
                    'fecha_ultima_modificacion': config.fecha_ultima_modificacion.strftime('%Y-%m-%d')
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def cancelar_pago_mensual(self, usuario_id: int) -> Dict:
        """Cancela la configuración de pago mensual de un usuario"""
        try:
            config = ConfiguracionPagoMensual.query.filter_by(
                usuario_id=usuario_id, activo=True
            ).first()
            
            if not config:
                return {'success': False, 'error': 'No hay configuración de pago mensual activa'}
            
            config.activo = False
            db.session.commit()
            
            return {
                'success': True,
                'mensaje': 'Configuración de pago mensual cancelada'
            }
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def obtener_usuarios_con_pago_mensual(self) -> List[Dict]:
        """Obtiene todos los usuarios que tienen configuración de pago mensual activa"""
        try:
            configuraciones = ConfiguracionPagoMensual.query.filter_by(activo=True).all()
            
            return [{
                'usuario_id': config.usuario_id,
                'usuario_nombre': f"{config.usuario.nombre} {config.usuario.apellidos}",
                'cantidad_mensual': float(config.cantidad_mensual),
                'metodo_pago': config.metodo_pago,
                'forma_pago': config.forma_pago,
                'dia_vencimiento': config.dia_vencimiento,
                'fecha_creacion': config.fecha_creacion.strftime('%Y-%m-%d')
            } for config in configuraciones]
            
        except Exception as e:
            return []
    
    def eliminar_pago(self, pago_id: int, admin_id: int = None) -> Dict:
        """Elimina un pago del sistema"""
        try:
            pago = Pago.query.get(pago_id)
            if not pago:
                return {'success': False, 'error': 'Pago no encontrado'}
            
            # Guardar información antes de eliminar para el log
            info_pago = {
                'usuario_id': pago.usuario_id,
                'cantidad': float(pago.cantidad),
                'fecha_pago': pago.fecha_pago.strftime('%Y-%m-%d') if pago.fecha_pago else None
            }
            
            db.session.delete(pago)
            db.session.commit()
            
            return {
                'success': True,
                'mensaje': f'Pago de €{info_pago["cantidad"]} eliminado correctamente',
                'pago_id': pago_id,
                'info_eliminado': info_pago
            }
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error en eliminar_pago: {str(e)}")
            return {'success': False, 'error': str(e)}

# Instancia global del servicio
payment_service = PaymentService()
