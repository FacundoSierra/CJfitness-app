import logging
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
from collections import defaultdict


def init_app(app):
    from models import db, Usuario, Ejercicio, Rutina, Bloque, EjercicioAsignado, Pago, SeguimientoEjercicio
    from utils import log_activity, log_error, handle_db_error, admin_required, login_required
    from payment_service import payment_service

    logger = logging.getLogger('fitness_app')

    # ------------------ ADMIN VER RUTINAS ------------------

    @app.route('/ver_rutinas/<int:user_id>')
    @admin_required
    @handle_db_error
    def ver_rutinas_usuario(user_id):
        usuario = db.session.get(Usuario, user_id)
        if not usuario:
            return "Usuario no encontrado", 404

        # Obtener parámetros de vista y mes
        vista = request.args.get("vista", "mensual")  # diaria, semanal, mensual
        mes_str = request.args.get("mes")
        fecha_especifica = request.args.get("fecha")

        hoy = datetime.today()

        if fecha_especifica:
            try:
                fecha_obj = datetime.strptime(fecha_especifica, "%Y-%m-%d").date()
            except ValueError:
                fecha_obj = hoy.date()
        elif mes_str:
            try:
                año, mes = map(int, mes_str.split("-"))
                fecha_obj = datetime(año, mes, 1).date()
            except ValueError:
                fecha_obj = hoy.date()
        else:
            fecha_obj = hoy.date()

        # Preparar datos según la vista
        if vista == "diaria":
            # Vista diaria - solo un día
            rutinas = Rutina.query.filter_by(
                usuario_id=user_id,
                fecha=fecha_obj
            ).order_by(Rutina.fecha).all()

            # Agrupar por bloques para el día
            bloques_dia = []
            for r in rutinas:
                for b in r.bloques:
                    ejercicios = []
                    for e in b.ejercicios:
                        ejercicios.append({
                            "nombre_manual": e.nombre_manual,
                            "series_reps": e.series_reps,
                            "rpe": e.rpe,
                            "carga": e.carga,
                            "ejercicio": {"nombre": e.ejercicio.nombre} if e.ejercicio else None,
                            "categoria": e.categoria,
                            "subcategoria": e.subcategoria
                        })
                    bloques_dia.append({
                        "nombre_bloque": b.nombre_bloque,
                        "categoria": b.categoria,
                        "ejercicios": ejercicios
                    })

            datos_vista = {
                "tipo": "diaria",
                "fecha": fecha_obj,
                "bloques": bloques_dia
            }

        elif vista == "semanal":
            # Vista semanal - semana completa
            lunes = fecha_obj - timedelta(days=fecha_obj.weekday())
            domingo = lunes + timedelta(days=6)

            rutinas = Rutina.query.filter(
                Rutina.usuario_id == user_id,
                Rutina.fecha >= lunes,
                Rutina.fecha <= domingo
            ).order_by(Rutina.fecha).all()

            # Agrupar por día de la semana
            dias_semana = {}
            for i in range(7):
                fecha_dia = lunes + timedelta(days=i)
                dias_semana[fecha_dia] = []

            for r in rutinas:
                bloques_dia = []
                for b in r.bloques:
                    ejercicios = []
                    for e in b.ejercicios:
                        ejercicios.append({
                            "nombre_manual": e.nombre_manual,
                            "series_reps": e.series_reps,
                            "rpe": e.rpe,
                            "carga": e.carga,
                            "ejercicio": {"nombre": e.ejercicio.nombre} if e.ejercicio else None,
                            "categoria": e.categoria,
                            "subcategoria": e.subcategoria
                        })
                    bloques_dia.append({
                        "nombre_bloque": b.nombre_bloque,
                        "categoria": b.categoria,
                        "ejercicios": ejercicios
                    })
                dias_semana[r.fecha] = bloques_dia

            datos_vista = {
                "tipo": "semanal",
                "inicio": lunes,
                "fin": domingo,
                "dias": dias_semana
            }

        else:  # vista == "mensual"
            # Vista mensual - por semanas (original)
            inicio = fecha_obj.replace(day=1)
            fin = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)

            rutinas = Rutina.query.filter(
                Rutina.usuario_id == user_id,
                Rutina.fecha >= inicio,
                Rutina.fecha < fin
            ).order_by(Rutina.fecha).all()

            # Agrupar por semana (lunes como clave)
            semanas_ordenadas = defaultdict(list)
            for r in rutinas:
                lunes = r.fecha - timedelta(days=r.fecha.weekday())
                semanas_ordenadas[lunes].append(r)

            # Convertir a estructura que el template entienda
            semanas_final = []
            for lunes, rutinas_semana in sorted(semanas_ordenadas.items()):
                bloques_semana = []
                for r in rutinas_semana:
                    bloques = []
                    for b in r.bloques:
                        ejercicios = []
                        for e in b.ejercicios:
                            ejercicios.append({
                                "nombre_manual": e.nombre_manual,
                                "series_reps": e.series_reps,
                                "rpe": e.rpe,
                                "carga": e.carga,
                                "ejercicio": {"nombre": e.ejercicio.nombre} if e.ejercicio else None,
                                "categoria": e.categoria,
                                "subcategoria": e.subcategoria
                            })
                        bloques.append({
                            "nombre_bloque": b.nombre_bloque,
                            "categoria": b.categoria,
                            "ejercicios": ejercicios
                        })
                    bloques_semana.append({
                        "fecha": r.fecha.strftime("%Y-%m-%d"),
                        "bloques": bloques
                    })

                semanas_final.append({
                    "inicio": lunes,
                    "fin": lunes + timedelta(days=6),
                    "rutinas": bloques_semana
                })

            datos_vista = {
                "tipo": "mensual",
                "semanas": semanas_final
            }

        mes_actual = fecha_obj.strftime("%Y-%m")
        fecha_actual = fecha_obj.strftime("%Y-%m-%d")

        return render_template("admin_ver_rutinas_usuario.html",
                               usuario=usuario,
                               datos_vista=datos_vista,
                               vista_actual=vista,
                               mes_actual=mes_actual,
                               fecha_actual=fecha_actual,
                               active_page='entrenamientos')

    # ------------------ ADMIN API_EJERCICIOS ------------------

    @app.route('/api_ejercicios')
    def api_ejercicios():
        ejercicios = Ejercicio.query.all()
        data = {}
        for e in ejercicios:
            categoria = e.categoria or "Sin categoría"
            subcategoria = e.subcategoria or "Sin subcategoría"
            nombre = e.nombre
            data.setdefault(categoria, {}).setdefault(subcategoria, []).append(nombre)
        return jsonify(data)

    # ------------------ API ESTADÍSTICAS REALES ------------------

    @app.route('/api/stats/dashboard')
    @admin_required
    @handle_db_error
    def api_dashboard_stats():
        """Obtener estadísticas reales del dashboard"""
        try:
            # Estadísticas de usuarios
            total_usuarios = Usuario.query.count()
            usuarios_hoy = Usuario.query.filter(
                Usuario.id > 0,  # Placeholder para fecha de registro
                # En un modelo real tendrías: Usuario.fecha_registro >= datetime.today().date()
            ).count()

            # Estadísticas de ejercicios
            total_ejercicios = Ejercicio.query.count()

            # Estadísticas de rutinas
            total_rutinas = Rutina.query.count()
            rutinas_esta_semana = Rutina.query.filter(
                Rutina.fecha >= datetime.today().date() - timedelta(days=7)
            ).count()

            # Estadísticas de pagos
            total_pagos_mes = Pago.query.filter(
                Pago.fecha_pago >= datetime.today().replace(day=1).date()
            ).count()

            # Calcular ingresos del mes
            pagos_mes = Pago.query.filter(
                Pago.fecha_pago >= datetime.today().replace(day=1).date()
            ).all()
            ingresos_mes = sum(float(pago.cantidad) for pago in pagos_mes if pago.cantidad)

            # Calcular ingresos del mes anterior para comparación
            mes_anterior = datetime.today().replace(day=1) - timedelta(days=1)
            inicio_mes_anterior = mes_anterior.replace(day=1)
            pagos_mes_anterior = Pago.query.filter(
                Pago.fecha_pago >= inicio_mes_anterior.date(),
                Pago.fecha_pago < datetime.today().replace(day=1).date()
            ).all()
            ingresos_mes_anterior = sum(float(pago.cantidad) for pago in pagos_mes_anterior if pago.cantidad)

            # Calcular cambio porcentual
            if ingresos_mes_anterior > 0:
                cambio_porcentual = ((ingresos_mes - ingresos_mes_anterior) / ingresos_mes_anterior) * 100
            else:
                cambio_porcentual = 100 if ingresos_mes > 0 else 0

            # Pagos pendientes
            pagos_pendientes = Pago.query.filter_by(estado='pendiente').count()

            # Pagos pagados este mes
            pagos_pagados_mes = Pago.query.filter(
                Pago.fecha_pago >= datetime.today().replace(day=1).date(),
                Pago.estado == 'pagado'
            ).count()

            # Actividad de la semana (últimos 7 días)
            actividad_semana = []
            for i in range(7):
                fecha = datetime.today().date() - timedelta(days=i)
                rutinas_dia = Rutina.query.filter_by(fecha=fecha).count()
                actividad_semana.append({
                    'fecha': fecha.strftime('%a'),
                    'rutinas': rutinas_dia
                })

            # Ordenar por fecha (más reciente primero)
            actividad_semana.reverse()

            stats = {
                'usuarios': {
                    'total': total_usuarios,
                    'nuevos_hoy': usuarios_hoy,
                    'cambio_mes': 12.5  # Placeholder - se puede calcular con fechas reales
                },
                'ejercicios': {
                    'total': total_ejercicios,
                    'cambio_mes': 5.2,  # Placeholder
                    'mas_popular': 'Press de Banca'  # Placeholder - se puede calcular
                },
                'rutinas': {
                    'total': total_rutinas,
                    'esta_semana': rutinas_esta_semana,
                    'cambio_semana': 8.7  # Placeholder
                },
                'pagos': {
                    'total_mes': total_pagos_mes,
                    'ingresos_mes': ingresos_mes or 0,
                    'cambio_mes': round(cambio_porcentual, 1),
                    'pendientes': pagos_pendientes,
                    'pagados_mes': pagos_pagados_mes,
                    'ingresos_mes_anterior': ingresos_mes_anterior or 0
                },
                'actividad': {
                    'labels': [item['fecha'] for item in actividad_semana],
                    'data': [item['rutinas'] for item in actividad_semana]
                }
            }

            return jsonify(stats)

        except Exception as e:
            log_error(f"Error obteniendo estadísticas: {e}", session.get('user_id'))
            return jsonify({'error': 'Error obteniendo estadísticas'}), 500

    @app.route('/api/stats/users')
    @admin_required
    @handle_db_error
    def api_users_stats():
        """Obtener estadísticas detalladas de usuarios"""
        try:
            total_usuarios = Usuario.query.count()
            usuarios_admin = Usuario.query.filter_by(rol='admin').count()
            usuarios_normales = Usuario.query.filter_by(rol='user').count()

            # Usuarios por mes (últimos 6 meses)
            usuarios_por_mes = []
            for i in range(6):
                fecha = datetime.today().replace(day=1) - timedelta(days=30*i)
                # Placeholder - en un modelo real tendrías fecha de registro
                usuarios_por_mes.append({
                    'mes': fecha.strftime('%b %Y'),
                    'total': total_usuarios  # Placeholder
                })

            return jsonify({
                'total': total_usuarios,
                'admins': usuarios_admin,
                'usuarios': usuarios_normales,
                'por_mes': usuarios_por_mes
            })

        except Exception as e:
            log_error(f"Error obteniendo estadísticas de usuarios: {e}", session.get('user_id'))
            return jsonify({'error': 'Error obteniendo estadísticas'}), 500

    @app.route('/api/stats/exercises')
    @admin_required
    @handle_db_error
    def api_exercises_stats():
        """Obtener estadísticas detalladas de ejercicios"""
        try:
            total_ejercicios = Ejercicio.query.count()

            # Ejercicios por categoría
            ejercicios_por_categoria = db.session.query(
                Ejercicio.categoria,
                db.func.count(Ejercicio.id).label('total')
            ).group_by(Ejercicio.categoria).all()

            # Ejercicios por subcategoría
            ejercicios_por_subcategoria = db.session.query(
                Ejercicio.subcategoria,
                db.func.count(Ejercicio.id).label('total')
            ).group_by(Ejercicio.subcategoria).all()

            return jsonify({
                'total': total_ejercicios,
                'por_categoria': [{'categoria': cat, 'total': total} for cat, total in ejercicios_por_categoria],
                'por_subcategoria': [{'subcategoria': sub, 'total': total} for sub, total in ejercicios_por_subcategoria]
            })

        except Exception as e:
            log_error(f"Error obteniendo estadísticas de ejercicios: {e}", session.get('user_id'))
            return jsonify({'error': 'Error obteniendo estadísticas'}), 500

    @app.route('/api/stats/payments')
    @admin_required
    @handle_db_error
    def api_payments_stats():
        """Obtener estadísticas detalladas de pagos"""
        try:
            # Estadísticas generales
            total_pagos = Pago.query.count()
            pagos_pendientes = Pago.query.filter_by(estado='pendiente').count()
            pagos_pagados = Pago.query.filter_by(estado='pagado').count()

            # Ingresos totales
            ingresos_totales = db.session.query(db.func.sum(Pago.cantidad)).filter_by(estado='pagado').scalar() or 0
            ingresos_totales = float(ingresos_totales)

            # Ingresos del mes actual
            inicio_mes = datetime.today().replace(day=1).date()
            ingresos_mes = db.session.query(db.func.sum(Pago.cantidad)).filter(
                Pago.fecha_pago >= inicio_mes,
                Pago.estado == 'pagado'
            ).scalar() or 0
            ingresos_mes = float(ingresos_mes)

            # Ingresos del mes anterior
            mes_anterior = datetime.today().replace(day=1) - timedelta(days=1)
            inicio_mes_anterior = mes_anterior.replace(day=1)
            ingresos_mes_anterior = db.session.query(db.func.sum(Pago.cantidad)).filter(
                Pago.fecha_pago >= inicio_mes_anterior,
                Pago.fecha_pago < inicio_mes,
                Pago.estado == 'pagado'
            ).scalar() or 0
            ingresos_mes_anterior = float(ingresos_mes_anterior)

            # Calcular cambio porcentual
            if ingresos_mes_anterior > 0:
                cambio_porcentual = ((ingresos_mes - ingresos_mes_anterior) / ingresos_mes_anterior) * 100
            else:
                cambio_porcentual = 100 if ingresos_mes > 0 else 0

            # Pagos por mes (últimos 6 meses)
            pagos_por_mes = []
            for i in range(6):
                fecha = datetime.today().replace(day=1) - timedelta(days=30*i)
                inicio_mes_calc = fecha.date()
                fin_mes_calc = (fecha + timedelta(days=32)).replace(day=1).date()

                ingresos_mes_calc = db.session.query(db.func.sum(Pago.cantidad)).filter(
                    Pago.fecha_pago >= inicio_mes_calc,
                    Pago.fecha_pago < fin_mes_calc,
                    Pago.estado == 'pagado'
                ).scalar() or 0
                ingresos_mes_calc = float(ingresos_mes_calc)

                pagos_por_mes.append({
                    'mes': fecha.strftime('%b %Y'),
                    'ingresos': ingresos_mes_calc,
                    'pagos': Pago.query.filter(
                        Pago.fecha_pago >= inicio_mes_calc,
                        Pago.fecha_pago < fin_mes_calc
                    ).count()
                })

            # Pagos por estado
            pagos_por_estado = [
                {'estado': 'Pagado', 'total': pagos_pagados, 'color': '#28a745'},
                {'estado': 'Pendiente', 'total': pagos_pendientes, 'color': '#ffc107'}
            ]

            return jsonify({
                'resumen': {
                    'total_pagos': total_pagos,
                    'pagos_pendientes': pagos_pendientes,
                    'pagos_pagados': pagos_pagados,
                    'ingresos_totales': ingresos_totales,
                    'ingresos_mes': ingresos_mes,
                    'ingresos_mes_anterior': ingresos_mes_anterior,
                    'cambio_porcentual': round(cambio_porcentual, 1)
                },
                'por_mes': pagos_por_mes,
                'por_estado': pagos_por_estado
            })

        except Exception as e:
            log_error(f"Error obteniendo estadísticas de pagos: {e}", session.get('user_id'))
            return jsonify({'error': 'Error obteniendo estadísticas'}), 500

    # ------------------ API PLANES / SUSCRIPCIÓN ------------------

    @app.route('/api/planes')
    def api_planes():
        """API para obtener planes disponibles"""
        try:
            planes = payment_service.obtener_planes_disponibles()
            return jsonify({'success': True, 'planes': planes})
        except Exception as e:
            log_error(e, session.get('user_id'))
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/suscripcion/crear', methods=['POST'])
    @login_required
    def api_crear_suscripcion():
        """API para crear una nueva suscripción"""
        try:
            data = request.get_json()
            plan_id = data.get('plan_id')
            metodo_pago_id = data.get('metodo_pago_id')

            if not plan_id or not metodo_pago_id:
                return jsonify({'success': False, 'error': 'Datos incompletos'}), 400

            resultado = payment_service.crear_suscripcion(
                session['user_id'],
                int(plan_id),
                metodo_pago_id
            )

            if resultado['success']:
                return jsonify(resultado)
            else:
                return jsonify(resultado), 400

        except Exception as e:
            log_error(e, session.get('user_id'))
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/suscripcion/cancelar', methods=['POST'])
    @login_required
    def api_cancelar_suscripcion():
        """API para cancelar una suscripción"""
        try:
            data = request.get_json()
            suscripcion_id = data.get('suscripcion_id')

            if not suscripcion_id:
                return jsonify({'success': False, 'error': 'ID de suscripción requerido'}), 400

            resultado = payment_service.cancelar_suscripcion(
                int(suscripcion_id),
                session['user_id']
            )

            return jsonify(resultado)

        except Exception as e:
            log_error(e, session.get('user_id'))
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/usuario/estado_premium')
    @login_required
    def api_estado_premium():
        """API para verificar el estado premium del usuario"""
        try:
            estado = payment_service.verificar_estado_premium(session['user_id'])
            return jsonify(estado)
        except Exception as e:
            log_error(e, session.get('user_id'))
            return jsonify({'premium': False, 'error': str(e)}), 500

    # ------------------ WEBHOOK STRIPE ------------------

    @app.route('/webhook/stripe', methods=['POST'])
    def webhook_stripe():
        """Webhook para recibir notificaciones de Stripe"""
        try:
            payload = request.data
            signature = request.headers.get('Stripe-Signature')

            if not signature:
                return jsonify({'error': 'Firma no encontrada'}), 400

            resultado = payment_service.procesar_webhook_stripe(payload, signature)

            if resultado['success']:
                return jsonify({'success': True}), 200
            else:
                return jsonify(resultado), 400

        except Exception as e:
            log_error(e, None)
            return jsonify({'error': str(e)}), 500

    # ------------------ API PAGOS ------------------

    @app.route('/api/pagos/usuario/<int:usuario_id>')
    @login_required
    def api_pagos_usuario(usuario_id):
        """API para obtener pagos de un usuario específico"""
        if session.get('user_rol') != 'admin' and session.get('user_id') != usuario_id:
            return jsonify({'success': False, 'error': 'Acceso denegado'})

        pagos = payment_service.obtener_pagos_usuario(usuario_id)
        return jsonify({'success': True, 'pagos': pagos})

    @app.route('/api/pagos/admin')
    @admin_required
    def api_pagos_admin():
        """API para obtener pagos filtrados para el admin"""
        estado = request.args.get('estado')
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        usuario_id = request.args.get('usuario_id', type=int)

        pagos = payment_service.obtener_pagos_admin(
            estado=estado,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            usuario_id=usuario_id
        )

        return jsonify({'success': True, 'pagos': pagos})

    @app.route('/api/pagos/estadisticas')
    @admin_required
    def api_estadisticas_pagos():
        """API para obtener estadísticas de pagos"""
        stats = payment_service.obtener_estadisticas_pagos()
        return jsonify({'success': True, 'estadisticas': stats})

    @app.route('/api/pagos_mensuales/usuario/<int:usuario_id>')
    @admin_required
    def api_configuracion_pago_mensual(usuario_id):
        """API para obtener la configuración de pago mensual de un usuario"""
        resultado = payment_service.obtener_configuracion_pago_mensual(usuario_id)
        return jsonify(resultado)

    # ------------------ SEGUIMIENTO DE EJERCICIOS ------------------

    @app.route('/api/ejercicio/<int:ejercicio_asignado_id>/registrar', methods=['POST'])
    @login_required
    @handle_db_error
    def registrar_ejercicio(ejercicio_asignado_id):
        """Registrar el progreso de un ejercicio por parte del usuario"""
        try:
            usuario_id = session['user_id']
            data = request.get_json()

            # Obtener el ejercicio asignado
            ejercicio_asignado = EjercicioAsignado.query.get(ejercicio_asignado_id)
            if not ejercicio_asignado:
                return jsonify({'error': 'Ejercicio no encontrado'}), 404

            # Verificar que el ejercicio pertenece al usuario
            rutina = Rutina.query.get(ejercicio_asignado.bloque.rutina_id)
            if rutina.usuario_id != usuario_id:
                return jsonify({'error': 'No tienes permisos para este ejercicio'}), 403

            # Determinar fecha de ejecución: usar la proporcionada o por defecto hoy
            fecha_str = (data or {}).get('fecha_ejecucion')
            if fecha_str:
                try:
                    fecha_ejecucion = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                except ValueError:
                    return jsonify({'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}), 400
            else:
                fecha_ejecucion = datetime.today().date()

            # Validar que la fecha pertenezca a la misma semana o sea igual a la fecha de la rutina
            # Permitimos registrar para la fecha exacta de la rutina o, si se quiere flexibilidad,
            # cualquier fecha. Aquí aplicamos validación suave: advertimos si se desvía más de 7 días.
            try:
                fecha_rutina = rutina.fecha
                delta_dias = abs((fecha_ejecucion - fecha_rutina).days)
                if delta_dias > 7:
                    # No bloqueamos, pero informamos al cliente
                    pass
            except Exception:
                pass

            # Validaciones ligeras de payload
            rpe_real = (data or {}).get('rpe_real', '')
            carga_real = (data or {}).get('carga_real', '')
            if isinstance(rpe_real, (int, float)):
                if rpe_real < 0 or rpe_real > 10:
                    return jsonify({'error': 'RPE debe estar entre 0 y 10'}), 400
            if isinstance(carga_real, (int, float)):
                if carga_real < 0:
                    return jsonify({'error': 'La carga no puede ser negativa'}), 400

            # Buscar si ya existe un seguimiento para la fecha indicada
            seguimiento = SeguimientoEjercicio.query.filter_by(
                usuario_id=usuario_id,
                ejercicio_asignado_id=ejercicio_asignado_id,
                fecha_ejecucion=fecha_ejecucion
            ).first()

            if seguimiento:
                # Actualizar seguimiento existente
                seguimiento.series_reps_reales = data.get('series_reps_reales', '')
                seguimiento.rpe_real = rpe_real
                seguimiento.carga_real = carga_real
                seguimiento.notas = data.get('notas', '')
                seguimiento.completado = data.get('completado', False)
                if seguimiento.completado:
                    seguimiento.fecha_completado = datetime.utcnow()
                seguimiento.fecha_actualizacion = datetime.utcnow()
            else:
                # Crear nuevo seguimiento
                seguimiento = SeguimientoEjercicio(
                    usuario_id=usuario_id,
                    ejercicio_asignado_id=ejercicio_asignado_id,
                    fecha_ejecucion=fecha_ejecucion,
                    series_reps_planificadas=ejercicio_asignado.series_reps,
                    rpe_planificado=ejercicio_asignado.rpe,
                    carga_planificada=ejercicio_asignado.carga,
                    series_reps_reales=data.get('series_reps_reales', ''),
                    rpe_real=rpe_real,
                    carga_real=carga_real,
                    notas=data.get('notas', ''),
                    completado=data.get('completado', False),
                    fecha_completado=datetime.utcnow() if data.get('completado', False) else None
                )
                db.session.add(seguimiento)

            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Progreso registrado correctamente',
                'seguimiento_id': seguimiento.id
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error registrando ejercicio: {str(e)}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/api/registrar_dia', methods=['POST'])
    @login_required
    @handle_db_error
    def registrar_dia():
        """Guardar en lote el progreso de todos los ejercicios de un día.
        Payload: { fecha_ejecucion: 'YYYY-MM-DD', ejercicios: [{id, series_reps_reales, rpe_real, carga_real, notas, completado}] }
        """
        try:
            usuario_id = session['user_id']
            data = request.get_json() or {}
            fecha_str = data.get('fecha_ejecucion')
            ejercicios = data.get('ejercicios', [])
            if not fecha_str or not ejercicios:
                return jsonify({'success': False, 'message': 'Fecha y ejercicios requeridos'}), 400
            try:
                fecha_ejecucion = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'success': False, 'message': 'Fecha inválida'}), 400

            ids = [e.get('id') for e in ejercicios if e.get('id')]
            asignados = {ea.id: ea for ea in EjercicioAsignado.query.filter(EjercicioAsignado.id.in_(ids)).all()}

            for item in ejercicios:
                ej_id = item.get('id')
                ea = asignados.get(ej_id)
                if not ea:
                    continue
                rutina = Rutina.query.get(ea.bloque.rutina_id)
                if rutina.usuario_id != usuario_id:
                    continue

                seguimiento = SeguimientoEjercicio.query.filter_by(
                    usuario_id=usuario_id,
                    ejercicio_asignado_id=ej_id,
                    fecha_ejecucion=fecha_ejecucion
                ).first()

                rpe_real = item.get('rpe_real', '')
                carga_real = item.get('carga_real', '')

                if seguimiento:
                    seguimiento.series_reps_reales = item.get('series_reps_reales', '')
                    seguimiento.rpe_real = rpe_real
                    seguimiento.carga_real = carga_real
                    seguimiento.notas = item.get('notas', '')
                    seguimiento.completado = item.get('completado', False)
                    if seguimiento.completado:
                        seguimiento.fecha_completado = datetime.utcnow()
                    seguimiento.fecha_actualizacion = datetime.utcnow()
                else:
                    seg = SeguimientoEjercicio(
                        usuario_id=usuario_id,
                        ejercicio_asignado_id=ej_id,
                        fecha_ejecucion=fecha_ejecucion,
                        series_reps_planificadas=ea.series_reps,
                        rpe_planificado=ea.rpe,
                        carga_planificada=ea.carga,
                        series_reps_reales=item.get('series_reps_reales', ''),
                        rpe_real=rpe_real,
                        carga_real=carga_real,
                        notas=item.get('notas', ''),
                        completado=item.get('completado', False),
                        fecha_completado=datetime.utcnow() if item.get('completado', False) else None
                    )
                    db.session.add(seg)

            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error registrar_dia: {e}")
            return jsonify({'success': False, 'message': 'Error interno'}), 500

    @app.route('/api/ejercicio/<int:ejercicio_asignado_id>/seguimiento', methods=['GET'])
    @login_required
    @handle_db_error
    def obtener_seguimiento_ejercicio(ejercicio_asignado_id):
        """Obtener el seguimiento de un ejercicio específico"""
        try:
            usuario_id = session['user_id']
            fecha_str = request.args.get('fecha')

            # Obtener el ejercicio asignado
            ejercicio_asignado = EjercicioAsignado.query.get(ejercicio_asignado_id)
            if not ejercicio_asignado:
                return jsonify({'error': 'Ejercicio no encontrado'}), 404

            # Verificar que el ejercicio pertenece al usuario
            rutina = Rutina.query.get(ejercicio_asignado.bloque.rutina_id)
            if rutina.usuario_id != usuario_id:
                return jsonify({'error': 'No tienes permisos para este ejercicio'}), 403

            # Obtener seguimientos del ejercicio
            query = SeguimientoEjercicio.query.filter_by(
                usuario_id=usuario_id,
                ejercicio_asignado_id=ejercicio_asignado_id
            )
            seg_en_fecha = None
            if fecha_str:
                try:
                    fecha_busqueda = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                    seg_en_fecha = query.filter_by(fecha_ejecucion=fecha_busqueda).first()
                except ValueError:
                    return jsonify({'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}), 400
            seguimientos = query.order_by(SeguimientoEjercicio.fecha_ejecucion.desc()).all()

            seguimientos_data = []
            for seg in seguimientos:
                seguimientos_data.append({
                    'id': seg.id,
                    'fecha_ejecucion': seg.fecha_ejecucion.strftime('%Y-%m-%d'),
                    'series_reps_planificadas': seg.series_reps_planificadas,
                    'rpe_planificado': seg.rpe_planificado,
                    'carga_planificada': seg.carga_planificada,
                    'series_reps_reales': seg.series_reps_reales,
                    'rpe_real': seg.rpe_real,
                    'carga_real': seg.carga_real,
                    'notas': seg.notas,
                    'completado': seg.completado,
                    'fecha_completado': seg.fecha_completado.strftime('%Y-%m-%d %H:%M') if seg.fecha_completado else None
                })

            return jsonify({
                'ejercicio': {
                    'id': ejercicio_asignado.id,
                    'nombre': ejercicio_asignado.ejercicio.nombre if ejercicio_asignado.ejercicio else ejercicio_asignado.nombre_manual,
                    'categoria': ejercicio_asignado.categoria,
                    'subcategoria': ejercicio_asignado.subcategoria
                },
                'seguimientos': seguimientos_data,
                'existe_en_fecha': seg_en_fecha is not None,
                'seguimiento_en_fecha': (
                    {
                        'id': seg_en_fecha.id,
                        'fecha_ejecucion': seg_en_fecha.fecha_ejecucion.strftime('%Y-%m-%d'),
                        'series_reps_planificadas': seg_en_fecha.series_reps_planificadas,
                        'rpe_planificado': seg_en_fecha.rpe_planificado,
                        'carga_planificada': seg_en_fecha.carga_planificada,
                        'series_reps_reales': seg_en_fecha.series_reps_reales,
                        'rpe_real': seg_en_fecha.rpe_real,
                        'carga_real': seg_en_fecha.carga_real,
                        'notas': seg_en_fecha.notas,
                        'completado': seg_en_fecha.completado,
                        'fecha_completado': seg_en_fecha.fecha_completado.strftime('%Y-%m-%d %H:%M') if seg_en_fecha.fecha_completado else None
                    }
                    if seg_en_fecha else None
                )
            })

        except Exception as e:
            logger.error(f"Error obteniendo seguimiento: {str(e)}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/api/usuario/<int:user_id>/progreso', methods=['GET'])
    @admin_required
    @handle_db_error
    def obtener_progreso_usuario(user_id):
        """Obtener el progreso de un usuario específico (solo admin)"""
        try:
            # Obtener usuario
            usuario = Usuario.query.get(user_id)
            if not usuario:
                return jsonify({'error': 'Usuario no encontrado'}), 404

            # Obtener seguimientos del usuario
            seguimientos = SeguimientoEjercicio.query.filter_by(usuario_id=user_id).order_by(
                SeguimientoEjercicio.fecha_ejecucion.desc()
            ).all()

            progreso_data = []
            for seg in seguimientos:
                progreso_data.append({
                    'id': seg.id,
                    'fecha_ejecucion': seg.fecha_ejecucion.strftime('%Y-%m-%d'),
                    'ejercicio': {
                        'id': seg.ejercicio_asignado.id,
                        'nombre': seg.ejercicio_asignado.ejercicio.nombre if seg.ejercicio_asignado.ejercicio else seg.ejercicio_asignado.nombre_manual,
                        'categoria': seg.ejercicio_asignado.categoria,
                        'subcategoria': seg.ejercicio_asignado.subcategoria
                    },
                    'planificado': {
                        'series_reps': seg.series_reps_planificadas,
                        'rpe': seg.rpe_planificado,
                        'carga': seg.carga_planificada
                    },
                    'realizado': {
                        'series_reps': seg.series_reps_reales,
                        'rpe': seg.rpe_real,
                        'carga': seg.carga_real
                    },
                    'notas': seg.notas,
                    'completado': seg.completado,
                    'fecha_completado': seg.fecha_completado.strftime('%Y-%m-%d %H:%M') if seg.fecha_completado else None
                })

            return jsonify({
                'usuario': {
                    'id': usuario.id,
                    'nombre': usuario.nombre,
                    'apellidos': usuario.apellidos
                },
                'progreso': progreso_data
            })

        except Exception as e:
            logger.error(f"Error obteniendo progreso: {str(e)}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/api/marcar-dia-completado', methods=['POST'])
    @login_required
    @handle_db_error
    def marcar_dia_completado():
        """Marcar todos los ejercicios de un día como completados"""
        try:
            data = request.get_json()
            fecha_str = data.get('fecha')

            if not fecha_str:
                return jsonify({'success': False, 'message': 'Fecha requerida'}), 400

            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            usuario_id = session['user_id']

            # Obtener rutinas del usuario en esa fecha
            rutinas = Rutina.query.filter_by(usuario_id=usuario_id, fecha=fecha).all()
            total_marcados = 0

            for rutina in rutinas:
                for bloque in rutina.bloques:
                    for ejercicio_asignado in bloque.ejercicios:
                        # Buscar o crear seguimiento
                        seg = SeguimientoEjercicio.query.filter_by(
                            usuario_id=usuario_id,
                            ejercicio_asignado_id=ejercicio_asignado.id,
                            fecha_ejecucion=fecha
                        ).first()

                        if seg:
                            if not seg.completado:
                                seg.completado = True
                                seg.fecha_completado = datetime.utcnow()
                                seg.fecha_actualizacion = datetime.utcnow()
                                total_marcados += 1
                        else:
                            seg = SeguimientoEjercicio(
                                usuario_id=usuario_id,
                                ejercicio_asignado_id=ejercicio_asignado.id,
                                fecha_ejecucion=fecha,
                                series_reps_planificadas=ejercicio_asignado.series_reps,
                                rpe_planificado=ejercicio_asignado.rpe,
                                carga_planificada=ejercicio_asignado.carga,
                                completado=True,
                                fecha_completado=datetime.utcnow()
                            )
                            db.session.add(seg)
                            total_marcados += 1

            db.session.commit()
            logger.info(f"Usuario {usuario_id} marcó {total_marcados} ejercicios como completados el {fecha}")

            return jsonify({
                'success': True,
                'message': f'Día {fecha} marcado como completado ({total_marcados} ejercicios)',
                'total_marcados': total_marcados
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error marcando día como completado: {str(e)}")
            return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500
