import logging
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
from calendar import monthrange
from collections import defaultdict
from sqlalchemy import func


def init_app(app):
    from models import db, Usuario, Ejercicio, Rutina, Bloque, EjercicioAsignado, Plan, Pago, ConfiguracionPagoMensual, SeguimientoEjercicio
    from utils import log_activity, log_error, handle_db_error, admin_required
    from payment_service import payment_service

    logger = logging.getLogger('fitness_app')

    # ------------------ ADMIN DASHBOARD ------------------

    @app.route('/admin_dashboard')
    @admin_required
    @handle_db_error
    def admin_dashboard():
        # Obtener estadísticas reales
        total_usuarios = Usuario.query.filter(Usuario.rol != 'admin').count()
        total_ejercicios = Ejercicio.query.count()
        total_rutinas = Rutina.query.count()

        # Obtener estadísticas de seguimiento
        total_seguimientos = SeguimientoEjercicio.query.count()
        ejercicios_completados = SeguimientoEjercicio.query.filter_by(completado=True).count()
        usuarios_activos = db.session.query(SeguimientoEjercicio.usuario_id).distinct().count()

        # Obtener usuarios recientes
        ultimos_usuarios = Usuario.query.filter(Usuario.rol != 'admin').order_by(Usuario.id.desc()).limit(5).all()

        # Obtener estadísticas de pagos
        try:
            stats_pagos = payment_service.obtener_estadisticas_pagos()
            ingresos_mes = stats_pagos.get('ingresos_mes', 0)
            pagos_mes = stats_pagos.get('pagos_pagados', 0)
        except Exception as e:
            log_error(e, "Error obteniendo estadísticas de pagos en dashboard")
            ingresos_mes = 0
            pagos_mes = 0

        # Obtener progreso reciente de usuarios
        progreso_reciente = db.session.query(
            SeguimientoEjercicio,
            Usuario,
            EjercicioAsignado
        ).join(Usuario, SeguimientoEjercicio.usuario_id == Usuario.id)\
         .join(EjercicioAsignado, SeguimientoEjercicio.ejercicio_asignado_id == EjercicioAsignado.id)\
         .order_by(SeguimientoEjercicio.fecha_actualizacion.desc())\
         .limit(10).all()

        # Pagos pendientes y próximos vencimientos
        hoy = datetime.utcnow().date()
        en_7_dias = hoy + timedelta(days=7)
        pagos_pendientes = Pago.query.filter_by(estado='pendiente').count()
        pagos_proximos = Pago.query.filter(
            Pago.estado == 'pendiente',
            Pago.fecha_vencimiento <= en_7_dias,
            Pago.fecha_vencimiento >= hoy
        ).order_by(Pago.fecha_vencimiento).limit(5).all()

        # Usuarios sin rutina asignada en los últimos 7 días
        desde_semana = datetime.utcnow().date() - timedelta(days=7)
        usuarios_con_rutina_ids = db.session.query(Rutina.usuario_id).filter(
            Rutina.fecha >= desde_semana
        ).distinct().subquery()
        usuarios_sin_rutina = Usuario.query.filter(
            Usuario.rol != 'admin',
            ~Usuario.id.in_(usuarios_con_rutina_ids)
        ).count()

        # Log de actividad
        log_activity("Acceso al dashboard admin", session['user_id'])

        return render_template('admin_dashboard.html',
                               username=session.get('username'),
                               total_usuarios=total_usuarios,
                               total_ejercicios=total_ejercicios,
                               total_rutinas=total_rutinas,
                               total_seguimientos=total_seguimientos,
                               ejercicios_completados=ejercicios_completados,
                               usuarios_activos=usuarios_activos,
                               ingresos_mes=ingresos_mes,
                               pagos_mes=pagos_mes,
                               ultimos_usuarios=ultimos_usuarios,
                               progreso_reciente=progreso_reciente,
                               pagos_pendientes=pagos_pendientes,
                               pagos_proximos=pagos_proximos,
                               usuarios_sin_rutina=usuarios_sin_rutina,
                               active_page='panel')

    @app.route('/admin_usuarios')
    @admin_required
    @handle_db_error
    def admin_usuarios():
        usuarios = Usuario.query.filter(Usuario.rol != 'admin').order_by(Usuario.id.desc()).all()
        return render_template('admin_usuarios.html', usuarios=usuarios, active_page='usuarios')

    # ------------------ ADMIN ENTRENAMIENTOS ------------------

    @app.route('/admin_entrenamientos')
    @admin_required
    @handle_db_error
    def admin_entrenamientos():
        usuarios = Usuario.query.filter(Usuario.rol != 'admin').all()
        return render_template('admin_entrenamientos.html', usuarios=usuarios, active_page='entrenamientos')

    # ------------------ ADMIN ASIGNAR ------------------

    @app.route('/admin_entrenamientos/<int:user_id>/asignar', methods=['GET', 'POST'])
    @admin_required
    @handle_db_error
    def asignar_rutinas_usuario(user_id):
        usuario = Usuario.query.get(user_id)
        if not usuario:
            return "Usuario no encontrado", 404

        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

        if request.method == 'POST':
            Rutina.query.filter_by(usuario_id=user_id).delete()
            db.session.commit()

            hoy = datetime.today()
            dia_a_fecha = {dias[i]: hoy + timedelta(days=i - hoy.weekday()) for i in range(7)}

            for dia in dias:
                bloques_html = [key for key in request.form if key.startswith(f'ejercicio_{dia}_')]
                bloques_ids = set(k.split('_')[2].split('[')[0] for k in bloques_html)

                for bloque_id in bloques_ids:
                    ejercicios = request.form.getlist(f'ejercicio_{dia}_{bloque_id}[]')
                    series = request.form.getlist(f'series_{dia}_{bloque_id}[]')
                    rpes = request.form.getlist(f'rpe_{dia}_{bloque_id}[]')
                    cargas = request.form.getlist(f'carga_{dia}_{bloque_id}[]')
                    categoria = request.form.get(f'bloque_{dia}_{bloque_id}_categoria')
                    subcategoria = request.form.get(f'bloque_{dia}_{bloque_id}_subcategoria')
                    fecha_rutina = dia_a_fecha[dia].date()

                    rutina = Rutina(usuario_id=user_id, fecha=fecha_rutina)
                    db.session.add(rutina)
                    db.session.commit()

                    bloque = Bloque(rutina_id=rutina.id, nombre_bloque=f'Bloque {bloque_id}', categoria=categoria)
                    db.session.add(bloque)
                    db.session.commit()

                    for i in range(len(ejercicios)):
                        nombre_ejercicio = ejercicios[i]
                        ejercicio_obj = Ejercicio.query.filter_by(nombre=nombre_ejercicio).first()
                        ejercicio_id = ejercicio_obj.id if ejercicio_obj else None

                        asignado = EjercicioAsignado(
                            bloque_id=bloque.id,
                            ejercicio_id=ejercicio_id,
                            nombre_manual=nombre_ejercicio if not ejercicio_id else None,
                            series_reps=series[i],
                            rpe=rpes[i],
                            carga=cargas[i]
                        )
                        db.session.add(asignado)

            db.session.commit()
            return redirect(url_for('admin_entrenamientos'))

        return render_template('admin_asignar_rutina_usuario.html',
                               usuario=usuario,
                               dias=dias,
                               active_page='entrenamientos')

    # ------------------ ADMIN CALENDARIO ------------------

    @app.route('/admin_entrenamientos/<int:user_id>/calendario', methods=['GET'])
    @admin_required
    @handle_db_error
    def calendario_entrenamientos_usuario(user_id):
        usuario = Usuario.query.get(user_id)
        if not usuario:
            return "Usuario no encontrado", 404

        # Obtener el mes solicitado o usar el actual
        mes_param = request.args.get('mes')
        hoy = datetime.today()

        if mes_param:
            try:
                año, mes = map(int, mes_param.split("-"))
                base = datetime(año, mes, 1)
            except ValueError:
                base = hoy
        else:
            base = hoy

        # Calcular rango del mes
        año, mes = base.year, base.month
        primer_dia_mes = datetime(año, mes, 1)
        _, ultimo_dia = monthrange(año, mes)  # (weekday_inicio, días_totales)

        # Día de la semana en que inicia (0 = lunes)
        inicio_semana = primer_dia_mes.weekday()
        total_celdas = inicio_semana + ultimo_dia
        total_filas = (total_celdas + 6) // 7  # redondear filas necesarias

        # Generar todas las fechas del calendario
        dias_calendario = []
        dia_actual = primer_dia_mes - timedelta(days=inicio_semana)

        for _ in range(total_filas):
            semana = []
            for _ in range(7):
                fecha = dia_actual.date()
                rutina = Rutina.query.filter_by(usuario_id=user_id, fecha=fecha).first()
                semana.append({
                    "fecha": fecha,
                    "es_del_mes": fecha.month == mes,
                    "rutina": rutina
                })
                dia_actual += timedelta(days=1)
            dias_calendario.append(semana)

        nombre_mes = base.strftime("%B de %Y")  # nombre completo y año
        mes_actual = base.strftime("%Y-%m")

        return render_template('admin_asignar_calendario.html',
                               usuario=usuario,
                               dias_calendario=dias_calendario,
                               nombre_mes=nombre_mes,
                               mes_actual=mes_actual,
                               active_page='entrenamientos')

    # ------------------ ADMIN GUARDAR ------------------

    @app.route('/admin_entrenamientos/<int:user_id>/guardar', methods=['POST'])
    @admin_required
    @handle_db_error
    def guardar_rutina_fecha(user_id):
        try:
            fecha_str = request.form.get("fecha")
            if not fecha_str:
                flash("Error: No se recibió la fecha", "danger")
                return redirect(url_for('calendario_entrenamientos_usuario', user_id=user_id))

            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            logger.info(f"Guardando rutina para usuario {user_id} en fecha {fecha}")

            # Eliminar rutina anterior (si existe) — cascade borra bloques y ejercicios asignados
            rutina_ant = Rutina.query.filter_by(usuario_id=user_id, fecha=fecha).first()
            if rutina_ant:
                logger.info(f"Eliminando rutina anterior para {fecha}")
                db.session.delete(rutina_ant)
                db.session.commit()

            # Crear nueva rutina
            rutina = Rutina(usuario_id=user_id, fecha=fecha)
            db.session.add(rutina)
            db.session.commit()
            logger.info(f"Nueva rutina creada con ID: {rutina.id}")

            # Detectar los bloques por el botón de añadir bloque
            bloque_indices = []
            for key in request.form:
                if key.startswith("ejercicio_") and key.endswith("[]"):
                    bloque_id = key.split("_")[1].replace("[]", "")
                    if bloque_id not in bloque_indices:
                        bloque_indices.append(bloque_id)

            logger.debug(f"Bloques detectados: {bloque_indices}")

            for bloque_id in bloque_indices:
                # Obtener la categoría del bloque desde el formulario
                categoria_bloque = request.form.get(f"categoria_bloque_{bloque_id}")
                if not categoria_bloque:
                    categoria_bloque = "General"  # Valor por defecto si no se especifica

                bloque = Bloque(
                    rutina_id=rutina.id,
                    nombre_bloque=f'Bloque {bloque_id}',
                    categoria=categoria_bloque
                )
                db.session.add(bloque)
                db.session.commit()
                logger.debug(f"Bloque {bloque_id} creado con ID: {bloque.id}, categoría: {categoria_bloque}")

                ejercicios = request.form.getlist(f"ejercicio_{bloque_id}[]")
                series_jsons = request.form.getlist(f"series_json_{bloque_id}[]")
                categorias_ej = request.form.getlist(f"categoria_ej_{bloque_id}[]")
                subcategorias_ej = request.form.getlist(f"subcategoria_ej_{bloque_id}[]")

                logger.debug(f"Bloque {bloque_id}: {len(ejercicios)} ejercicios, {len(series_jsons)} series_json")

                for i in range(len(ejercicios)):
                    ejercicio = ejercicios[i]
                    ejercicio_obj = Ejercicio.query.filter_by(nombre=ejercicio).first()
                    ejercicio_id = ejercicio_obj.id if ejercicio_obj else None
                    categoria_ej = categorias_ej[i] if i < len(categorias_ej) else None
                    subcategoria_ej = subcategorias_ej[i] if i < len(subcategorias_ej) else None
                    sj = series_jsons[i] if i < len(series_jsons) else None

                    asignado = EjercicioAsignado(
                        bloque_id=bloque.id,
                        ejercicio_id=ejercicio_id,
                        nombre_manual=ejercicio if not ejercicio_id else None,
                        series_json=sj,
                        categoria=categoria_ej,
                        subcategoria=subcategoria_ej
                    )
                    db.session.add(asignado)

            db.session.commit()
            logger.info(f"Rutina guardada correctamente para usuario {user_id} en fecha {fecha}")
            flash("Rutina asignada correctamente", "success")
            return redirect(url_for('calendario_entrenamientos_usuario', user_id=user_id, mes=fecha.strftime("%Y-%m")))

        except Exception as e:
            db.session.rollback()
            log_error(e, f"Error guardando rutina para usuario {user_id}")
            flash(f"Error al guardar la rutina: {str(e)}", "danger")
            return redirect(url_for('calendario_entrenamientos_usuario', user_id=user_id))

    # ------------------ ADMIN EDITAR ------------------

    @app.route('/admin_entrenamientos/<int:user_id>/editar', methods=['POST'])
    @admin_required
    @handle_db_error
    def editar_rutina(user_id):
        try:
            fecha_str = request.form.get("fecha_editar")
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()

            logger.info(f"Editando rutina para usuario {user_id} en fecha {fecha}")

            # Eliminar rutina anterior — cascade borra bloques y ejercicios asignados
            rutina_ant = Rutina.query.filter_by(usuario_id=user_id, fecha=fecha).first()
            if rutina_ant:
                logger.info(f"Eliminando rutina anterior con {len(rutina_ant.bloques)} bloques")
                db.session.delete(rutina_ant)
                db.session.commit()

            # Crear nueva rutina
            rutina = Rutina(usuario_id=user_id, fecha=fecha)
            db.session.add(rutina)
            db.session.commit()
            logger.info(f"Nueva rutina creada con ID: {rutina.id}")

            # Detectar todos los bloques enviados
            bloque_ids = []
            for key in request.form:
                if key.startswith("ejercicio_") and key.endswith("[]"):
                    bloque_id = key.split("_")[1].replace("[]", "")
                    if bloque_id not in bloque_ids:
                        bloque_ids.append(bloque_id)

            logger.info(f"Bloques detectados: {bloque_ids}")

            for bloque_id in bloque_ids:
                # Obtener la categoría del bloque
                categoria_bloque = request.form.get(f"categoria_bloque_{bloque_id}")
                if not categoria_bloque:
                    categoria_bloque = "General"  # Categoría por defecto

                logger.info(f"Creando bloque {bloque_id} con categoría: {categoria_bloque}")

                bloque = Bloque(
                    rutina_id=rutina.id,
                    nombre_bloque=f'Bloque {bloque_id}',
                    categoria=categoria_bloque
                )
                db.session.add(bloque)
                db.session.commit()
                logger.info(f"Bloque {bloque_id} creado con ID: {bloque.id}")

                ejercicios = request.form.getlist(f"ejercicio_{bloque_id}[]")
                series = request.form.getlist(f"series_{bloque_id}[]")
                rpes = request.form.getlist(f"rpe_{bloque_id}[]")
                cargas = request.form.getlist(f"carga_{bloque_id}[]")
                categorias_ej = request.form.getlist(f"categoria_ej_{bloque_id}[]")
                subcategorias_ej = request.form.getlist(f"subcategoria_ej_{bloque_id}[]")

                logger.info(f"Ejercicios para bloque {bloque_id}: {ejercicios}")

                for i in range(len(ejercicios)):
                    ejercicio = ejercicios[i]
                    ejercicio_obj = Ejercicio.query.filter_by(nombre=ejercicio).first()
                    ejercicio_id = ejercicio_obj.id if ejercicio_obj else None
                    categoria_ej = categorias_ej[i] if i < len(categorias_ej) else None
                    subcategoria_ej = subcategorias_ej[i] if i < len(subcategorias_ej) else None

                    asignado = EjercicioAsignado(
                        bloque_id=bloque.id,
                        ejercicio_id=ejercicio_id,
                        nombre_manual=ejercicio if not ejercicio_id else None,
                        series_reps=series[i],
                        rpe=rpes[i],
                        carga=cargas[i],
                        categoria=categoria_ej,
                        subcategoria=subcategoria_ej
                    )
                    db.session.add(asignado)

            db.session.commit()
            logger.info(f"✅ Rutina actualizada exitosamente para {fecha}")
            flash(f'✅ Rutina actualizada para {fecha.strftime("%d/%m/%Y")}', 'success')
            return redirect(url_for('ver_rutinas_usuario', user_id=user_id))

        except Exception as e:
            logger.error(f"Error editando rutina: {str(e)}")
            db.session.rollback()
            flash(f'❌ Error al editar la rutina: {str(e)}', 'danger')
            return redirect(url_for('ver_rutinas_usuario', user_id=user_id))

    @app.route('/admin_entrenamientos/<int:user_id>/eliminar', methods=['POST'])
    @admin_required
    @handle_db_error
    def eliminar_rutina(user_id):
        fecha_str = request.form.get("fecha_eliminar")
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()

        # Buscar y eliminar la rutina
        rutina = Rutina.query.filter_by(usuario_id=user_id, fecha=fecha).first()
        if rutina:
            # Eliminar ejercicios asignados primero
            for bloque in rutina.bloques:
                EjercicioAsignado.query.filter_by(bloque_id=bloque.id).delete()
                db.session.delete(bloque)

            # Eliminar la rutina
            db.session.delete(rutina)
            db.session.commit()

            flash(f'✅ Rutina eliminada para {fecha.strftime("%d/%m/%Y")}', 'success')
        else:
            flash('❌ No se encontró la rutina para eliminar', 'danger')

        return redirect(url_for('ver_rutinas_usuario', user_id=user_id))

    # ------------------ ADMIN ESTADISTICAS ------------------

    @app.route('/admin_estadisticas')
    @admin_required
    def admin_estadisticas():
        return render_template('admin_en_construccion.html',
                               titulo="Estadísticas",
                               mensaje="Próximamente podrás ver estadísticas detalladas aquí.",
                               active_page='estadisticas')

    # --------------------- ADMIN BORRAR/EDITAR USUARIO ---------------------------------------------

    @app.route('/admin/usuarios/borrar/<int:user_id>', methods=['POST'])
    @admin_required
    @handle_db_error
    def borrar_usuario(user_id):
        user = Usuario.query.get_or_404(user_id)
        try:
            db.session.delete(user)
            db.session.commit()
            flash(f"Usuario {user.nombre} {user.apellidos} eliminado correctamente.", "success")
        except Exception as e:
            db.session.rollback()
            flash("No se pudo eliminar el usuario. Intenta de nuevo.", "danger")
        return redirect(url_for('admin_usuarios'))

    @app.route('/admin/usuarios/editar/<int:user_id>', methods=['GET', 'POST'])
    @admin_required
    @handle_db_error
    def editar_usuario(user_id):
        user = Usuario.query.get_or_404(user_id)
        if request.method == 'POST':
            user.nombre = request.form['nombre']
            user.apellidos = request.form['apellidos']
            user.email = request.form['email']
            user.telefono = request.form['telefono']
            try:
                db.session.commit()
                flash("Usuario actualizado correctamente.", "success")
                return redirect(url_for('admin_usuarios'))
            except Exception as e:
                db.session.rollback()
                flash("No se pudo actualizar el usuario.", "danger")
                return redirect(url_for('admin_usuarios'))

    # --------------------- PAGOS ---------------------------------------------

    @app.route('/admin_pagos/nuevo', methods=['POST'])
    @admin_required
    @handle_db_error
    def admin_pagos_nuevo():
        try:
            usuario_id = request.form['usuario_id']
            cantidad = request.form['cantidad']
            metodo_pago = request.form['metodo_pago']
            forma_pago = request.form.get('forma_pago', '')
            observaciones = request.form.get('observaciones', '')

            # Validaciones
            if not usuario_id or not cantidad or not metodo_pago:
                flash('Usuario, cantidad y método de pago son obligatorios', 'danger')
                return redirect(url_for('admin_pagos'))

            # Verificar que el usuario existe
            usuario = Usuario.query.get(usuario_id)
            if not usuario:
                flash('Usuario no encontrado', 'danger')
                return redirect(url_for('admin_pagos'))

            # Validar cantidad
            try:
                cantidad_float = float(cantidad)
                if cantidad_float <= 0:
                    flash('La cantidad debe ser mayor a 0', 'danger')
                    return redirect(url_for('admin_pagos'))
            except ValueError:
                flash('La cantidad debe ser un número válido', 'danger')
                return redirect(url_for('admin_pagos'))

            # Registrar el pago usando el servicio
            resultado = payment_service.registrar_pago(
                usuario_id=int(usuario_id),
                cantidad=cantidad_float,
                metodo_pago=metodo_pago,
                forma_pago=forma_pago,
                observaciones=observaciones
            )

            if resultado['success']:
                # Log de actividad
                log_activity(f"Pago registrado: €{cantidad_float} para {usuario.nombre}", session['user_id'])
                flash(f'Pago de €{cantidad_float} registrado correctamente para {usuario.nombre}', 'success')
            else:
                flash(f'Error al registrar el pago: {resultado["error"]}', 'danger')

        except Exception as e:
            db.session.rollback()
            log_error(f"Error creando pago: {e}", session.get('user_id'))
            flash('Error al crear el pago. Intenta de nuevo.', 'danger')

        return redirect(url_for('admin_pagos'))

    @app.route('/admin_pagos/eliminar/<int:pago_id>', methods=['POST'])
    @admin_required
    @handle_db_error
    def admin_pagos_eliminar(pago_id):
        try:
            pago = Pago.query.get_or_404(pago_id)

            # Guardar información para el log
            info_pago = f"ID {pago_id}, Usuario: {pago.usuario.nombre}, Cantidad: €{pago.cantidad}, Estado: {pago.estado}"

            # Eliminar el pago
            db.session.delete(pago)
            db.session.commit()

            # Log de actividad
            log_activity(f"Pago eliminado: {info_pago}", session['user_id'])

            flash('Pago eliminado correctamente', 'success')

        except Exception as e:
            db.session.rollback()
            log_error(f"Error eliminando pago {pago_id}: {e}", session.get('user_id'))
            flash('Error al eliminar el pago. Intenta de nuevo.', 'danger')

        return redirect(url_for('admin_pagos'))

    @app.route('/admin_pagos/editar/<int:pago_id>', methods=['POST'])
    @admin_required
    @handle_db_error
    def admin_pagos_editar(pago_id):
        try:
            pago = Pago.query.get_or_404(pago_id)

            # Obtener datos del formulario
            nuevo_estado = request.form['estado']
            nueva_fecha = request.form['fecha_pago']
            nueva_cantidad = request.form['cantidad']
            nuevas_observaciones = request.form['observaciones']

            # Validaciones
            if not nueva_fecha or not nueva_cantidad:
                flash('Todos los campos obligatorios deben estar completos', 'danger')
                return redirect(url_for('admin_pagos'))

            # Validar cantidad
            try:
                cantidad_float = float(nueva_cantidad)
                if cantidad_float <= 0:
                    flash('La cantidad debe ser mayor a 0', 'danger')
                    return redirect(url_for('admin_pagos'))
            except ValueError:
                flash('La cantidad debe ser un número válido', 'danger')
                return redirect(url_for('admin_pagos'))

            # Validar fecha
            try:
                fecha_pago_obj = datetime.strptime(nueva_fecha, '%Y-%m-%d').date()
                if fecha_pago_obj > datetime.today().date():
                    flash('La fecha de pago no puede ser futura', 'warning')
            except ValueError:
                flash('Formato de fecha inválido', 'danger')
                return redirect(url_for('admin_pagos'))

            # Guardar valores anteriores para el log
            estado_anterior = pago.estado
            cantidad_anterior = pago.cantidad

            # Actualizar el pago
            pago.estado = nuevo_estado
            pago.fecha_pago = fecha_pago_obj
            pago.cantidad = cantidad_float
            pago.observaciones = nuevas_observaciones

            db.session.commit()

            # Log de actividad
            log_activity(
                f"Pago actualizado: ID {pago_id}, Estado: {estado_anterior} → {nuevo_estado}, "
                f"Cantidad: €{cantidad_anterior} → €{cantidad_float}",
                session['user_id']
            )

            flash('Pago actualizado correctamente', 'success')

        except Exception as e:
            db.session.rollback()
            log_error(f"Error actualizando pago {pago_id}: {e}", session.get('user_id'))
            flash('Error al actualizar el pago. Intenta de nuevo.', 'danger')

        return redirect(url_for('admin_pagos'))

    # --------------------- EJERCICIOS ---------------------------------------------

    @app.route('/admin_ejercicios')
    @admin_required
    @handle_db_error
    def admin_ejercicios():
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '').strip()
        sort = request.args.get('sort', 'nombre')
        order = request.args.get('order', 'asc')

        query = Ejercicio.query
        if search:
            search_like = f"%{search}%"
            query = query.filter(
                (Ejercicio.nombre.ilike(search_like)) |
                (Ejercicio.categoria.ilike(search_like)) |
                (Ejercicio.subcategoria.ilike(search_like))
            )

        sort_column = getattr(Ejercicio, sort, Ejercicio.nombre)
        if order == 'desc':
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)

        ejercicios_pagination = query.paginate(page=page, per_page=30)

        return render_template('admin_ejercicios.html',
                               ejercicios_pagination=ejercicios_pagination,
                               search=search, sort=sort, order=order)

    @app.route('/admin_ejercicios/nuevo', methods=['POST'])
    @admin_required
    @handle_db_error
    def admin_ejercicios_nuevo():
        nombre = request.form['nombre']
        categoria = request.form['categoria']
        subcategoria = request.form['subcategoria']
        ejercicio = Ejercicio(nombre=nombre, categoria=categoria, subcategoria=subcategoria)
        db.session.add(ejercicio)
        db.session.commit()
        flash('Ejercicio añadido', 'success')
        return redirect(url_for('admin_ejercicios'))

    @app.route('/admin_ejercicios/eliminar/<int:e_id>', methods=['POST'])
    @admin_required
    @handle_db_error
    def admin_ejercicios_eliminar(e_id):
        ejercicio = Ejercicio.query.get_or_404(e_id)
        db.session.delete(ejercicio)
        db.session.commit()
        flash('Ejercicio eliminado', 'success')
        return redirect(url_for('admin_ejercicios'))

    @app.route('/admin_ejercicios/editar/<int:e_id>', methods=['POST'])
    @admin_required
    @handle_db_error
    def admin_ejercicios_editar(e_id):
        ejercicio = Ejercicio.query.get_or_404(e_id)
        ejercicio.nombre = request.form['nombre']
        ejercicio.categoria = request.form['categoria']
        ejercicio.subcategoria = request.form['subcategoria']
        db.session.commit()
        flash('Ejercicio actualizado', 'success')
        return redirect(url_for('admin_ejercicios'))

    @app.route('/admin_ejercicios_buscar')
    @admin_required
    @handle_db_error
    def admin_ejercicios_buscar():
        query = request.args.get('q', '').strip()

        if not query:
            return jsonify({'success': False, 'error': 'Término de búsqueda requerido'})

        try:
            # Buscar en todos los ejercicios sin paginación
            search_like = f"%{query}%"
            ejercicios = Ejercicio.query.filter(
                (Ejercicio.nombre.ilike(search_like)) |
                (Ejercicio.categoria.ilike(search_like)) |
                (Ejercicio.subcategoria.ilike(search_like))
            ).order_by(Ejercicio.nombre).all()

            # Convertir a formato JSON
            ejercicios_data = []
            for ejercicio in ejercicios:
                ejercicios_data.append({
                    'id': ejercicio.id,
                    'nombre': ejercicio.nombre,
                    'categoria': ejercicio.categoria,
                    'subcategoria': ejercicio.subcategoria
                })

            return jsonify({
                'success': True,
                'ejercicios': ejercicios_data,
                'total': len(ejercicios_data)
            })

        except Exception as e:
            logger.error(f"Error en búsqueda de ejercicios: {str(e)}")
            return jsonify({'success': False, 'error': 'Error en la búsqueda'})

    # ------------------ PAGOS ADMIN ------------------

    @app.route('/admin_pagos')
    @admin_required
    def admin_pagos():
        """Dashboard de pagos para el admin"""
        # Obtener estadísticas
        stats = payment_service.obtener_estadisticas_pagos()

        # Obtener pagos recientes
        pagos_recientes = payment_service.obtener_pagos_admin(limit=10)

        return render_template('admin_pagos.html', stats=stats, pagos_recientes=pagos_recientes)

    @app.route('/admin_pagos/registrar', methods=['GET', 'POST'])
    @admin_required
    def admin_registrar_pago():
        """Página para que el admin registre un nuevo pago"""

        if request.method == 'POST':
            try:
                usuario_id = request.form['usuario_id']
                cantidad = request.form['cantidad']
                metodo_pago = request.form['metodo_pago']
                forma_pago = request.form.get('forma_pago', '')
                observaciones = request.form.get('observaciones', '')

                # Validaciones
                if not usuario_id or not cantidad or not metodo_pago:
                    flash('Usuario, cantidad y método de pago son obligatorios', 'danger')
                    return redirect(url_for('admin_registrar_pago'))

                # Verificar que el usuario existe
                usuario = Usuario.query.get(usuario_id)
                if not usuario:
                    flash('Usuario no encontrado', 'danger')
                    return redirect(url_for('admin_registrar_pago'))

                # Validar cantidad
                try:
                    cantidad_float = float(cantidad)
                    if cantidad_float <= 0:
                        flash('La cantidad debe ser mayor a 0', 'danger')
                        return redirect(url_for('admin_registrar_pago'))
                except ValueError:
                    flash('La cantidad debe ser un número válido', 'danger')
                    return redirect(url_for('admin_registrar_pago'))

                # Registrar el pago usando el servicio
                resultado = payment_service.registrar_pago(
                    usuario_id=int(usuario_id),
                    cantidad=cantidad_float,
                    metodo_pago=metodo_pago,
                    forma_pago=forma_pago,
                    observaciones=observaciones
                )

                if resultado['success']:
                    # Log de actividad
                    log_activity(f"Pago registrado: €{cantidad_float} para {usuario.nombre}", session['user_id'])
                    flash(f'Pago de €{cantidad_float} registrado correctamente para {usuario.nombre}', 'success')
                    return redirect(url_for('admin_pagos'))
                else:
                    flash(f'Error al registrar el pago: {resultado["error"]}', 'danger')

            except Exception as e:
                log_error(f"Error en admin_registrar_pago: {e}", session.get('user_id'))
                flash(f'Error interno del servidor: {str(e)}', 'danger')

        # GET: Mostrar formulario
        usuarios = Usuario.query.order_by(Usuario.nombre).all()

        return render_template('admin_registrar_pago.html', usuarios=usuarios)

    @app.route('/admin_pagos/<int:pago_id>/cambiar_estado', methods=['POST'])
    @admin_required
    def admin_cambiar_estado_pago(pago_id):
        """Cambia el estado de un pago (pendiente -> pagado, etc.)"""
        try:
            data = request.get_json()
            nuevo_estado = data.get('nuevo_estado')

            if not nuevo_estado:
                return jsonify({'success': False, 'error': 'Nuevo estado no especificado'})

            resultado = payment_service.cambiar_estado_pago(
                pago_id=pago_id,
                nuevo_estado=nuevo_estado,
                admin_id=session.get('user_id')
            )

            return jsonify(resultado)

        except Exception as e:
            return jsonify({'success': False, 'error': f'Error interno: {str(e)}'})

    @app.route('/admin_pagos/<int:pago_id>/eliminar', methods=['POST'])
    @admin_required
    def admin_eliminar_pago(pago_id):
        """Elimina un pago del sistema"""
        try:
            resultado = payment_service.eliminar_pago(
                pago_id=pago_id,
                admin_id=session.get('user_id')
            )

            return jsonify(resultado)

        except Exception as e:
            return jsonify({'success': False, 'error': f'Error interno: {str(e)}'})

    @app.route('/admin_pagos/<int:pago_id>/cancelar', methods=['POST'])
    @admin_required
    def admin_cancelar_pago(pago_id):
        """Cancela un pago"""
        data = request.get_json()
        resultado = payment_service.cancelar_pago(
            pago_id=pago_id,
            admin_id=session.get('user_id'),
            motivo=data.get('motivo')
        )

        return jsonify(resultado)

    # ------------------ NUEVAS RUTAS PARA PAGOS MENSUALES ------------------

    @app.route('/admin_pagos_mensuales')
    @admin_required
    def admin_pagos_mensuales():
        """Página para gestionar pagos mensuales"""
        # Obtener usuarios con configuración de pago mensual
        usuarios_config = payment_service.obtener_usuarios_con_pago_mensual()

        # Obtener estadísticas
        stats = payment_service.obtener_estadisticas_pagos()

        # Obtener mes actual
        hoy = datetime.today()
        moment_actual = f"{hoy.year}-{hoy.month:02d}"

        return render_template('admin_pagos_mensuales.html',
                             usuarios_config=usuarios_config,
                             stats=stats,
                             moment_actual=moment_actual)

    @app.route('/admin_pagos_mensuales/configurar', methods=['GET', 'POST'])
    @admin_required
    def admin_configurar_pago_mensual():
        """Configurar pago mensual para un usuario"""

        if request.method == 'POST':
            try:
                usuario_id = request.form['usuario_id']
                cantidad = request.form['cantidad']
                metodo_pago = request.form['metodo_pago']
                forma_pago = request.form.get('forma_pago', '')
                dia_vencimiento = int(request.form.get('dia_vencimiento', 1))

                # Validaciones
                if not usuario_id or not cantidad or not metodo_pago:
                    flash('Usuario, cantidad y método de pago son obligatorios', 'danger')
                    return redirect(url_for('admin_configurar_pago_mensual'))

                # Verificar que el usuario existe
                usuario = Usuario.query.get(usuario_id)
                if not usuario:
                    flash('Usuario no encontrado', 'danger')
                    return redirect(url_for('admin_configurar_pago_mensual'))

                # Validar cantidad
                try:
                    cantidad_float = float(cantidad)
                    if cantidad_float <= 0:
                        flash('La cantidad debe ser mayor a 0', 'danger')
                        return redirect(url_for('admin_configurar_pago_mensual'))
                except ValueError:
                    flash('La cantidad debe ser un número válido', 'danger')
                    return redirect(url_for('admin_configurar_pago_mensual'))

                # Configurar pago mensual
                resultado = payment_service.configurar_pago_mensual(
                    usuario_id=int(usuario_id),
                    cantidad=cantidad_float,
                    metodo_pago=metodo_pago,
                    forma_pago=forma_pago,
                    dia_vencimiento=dia_vencimiento
                )

                if resultado['success']:
                    log_activity(f"Configuración de pago mensual: €{cantidad_float} para {usuario.nombre}", session['user_id'])
                    flash(f'Configuración de pago mensual guardada para {usuario.nombre}', 'success')
                    return redirect(url_for('admin_pagos_mensuales'))
                else:
                    flash(f'Error al configurar pago mensual: {resultado["error"]}', 'danger')

            except Exception as e:
                log_error(f"Error en admin_configurar_pago_mensual: {e}", session.get('user_id'))
                flash(f'Error interno del servidor: {str(e)}', 'danger')

        # GET: Mostrar formulario
        usuarios = Usuario.query.order_by(Usuario.nombre).all()

        return render_template('admin_configurar_pago_mensual.html', usuarios=usuarios)

    @app.route('/admin_pagos_mensuales/generar', methods=['POST'])
    @admin_required
    def admin_generar_pagos_mensuales():
        """Genera los pagos mensuales para todos los usuarios"""
        try:
            mes = request.form.get('mes')

            resultado = payment_service.generar_pagos_mensuales(mes)

            if resultado['success']:
                flash(f'Se generaron {resultado["pagos_creados"]} pagos mensuales para {resultado["mes"]}', 'success')
                if resultado['errores']:
                    flash(f'Errores: {", ".join(resultado["errores"])}', 'warning')
            else:
                flash(f'Error al generar pagos mensuales: {resultado["error"]}', 'danger')

        except Exception as e:
            log_error(f"Error en admin_generar_pagos_mensuales: {e}", session.get('user_id'))
            flash(f'Error interno del servidor: {str(e)}', 'danger')

        return redirect(url_for('admin_pagos_mensuales'))

    @app.route('/admin_pagos_mensuales/cancelar/<int:usuario_id>', methods=['POST'])
    @admin_required
    def admin_cancelar_pago_mensual(usuario_id):
        """Cancela la configuración de pago mensual de un usuario"""
        try:
            resultado = payment_service.cancelar_pago_mensual(usuario_id)

            if resultado['success']:
                usuario = Usuario.query.get(usuario_id)
                log_activity(f"Pago mensual cancelado para {usuario.nombre}", session['user_id'])
                return jsonify({
                    'success': True,
                    'mensaje': f'Configuración de pago mensual cancelada para {usuario.nombre}'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': resultado['error']
                })

        except Exception as e:
            log_error(f"Error en admin_cancelar_pago_mensual: {e}", session.get('user_id'))
            return jsonify({
                'success': False,
                'error': f'Error interno del servidor: {str(e)}'
            })

    # ------------------ ADMIN PROGRESOS ------------------

    @app.route('/admin/progresos')
    @admin_required
    @handle_db_error
    def admin_progresos():
        """Listado de usuarios con acciones de progreso (estilo tarjetas)."""
        try:
            usuarios = Usuario.query.filter(Usuario.rol != 'admin').order_by(Usuario.nombre).all()
            # Conteo de seguimientos por usuario
            conteos = dict(
                db.session.query(SeguimientoEjercicio.usuario_id, func.count(SeguimientoEjercicio.id))
                .group_by(SeguimientoEjercicio.usuario_id)
                .all()
            )
            return render_template('admin_progresos_usuarios.html', usuarios=usuarios, conteos=conteos, active_page='progresos')
        except Exception as e:
            logger.error(f"Error listando usuarios de progresos: {e}")
            flash('Error listando usuarios', 'danger')
            return render_template('admin_progresos_usuarios.html', usuarios=[], conteos={}, active_page='progresos')

    @app.route('/admin/progresos/<int:user_id>')
    @admin_required
    @handle_db_error
    def admin_progresos_usuario(user_id):
        """Vista de progresos por usuario con modos: diaria, semanal, mensual."""
        usuario = Usuario.query.get(user_id)
        if not usuario:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('admin_progresos'))

        vista = request.args.get('vista', 'diaria')
        fecha_str = request.args.get('fecha')
        base = datetime.today().date()
        if fecha_str:
            try:
                base = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Fecha inválida (YYYY-MM-DD)', 'danger')

        datos_vista = None

        if vista == 'diaria':
            segs = (
                SeguimientoEjercicio.query.filter_by(usuario_id=user_id, fecha_ejecucion=base)
                .order_by(SeguimientoEjercicio.id.desc())
                .all()
            )
            datos_vista = { 'tipo': 'diaria', 'fecha': base, 'seguimientos': segs }

        elif vista == 'semanal':
            lunes = base - timedelta(days=base.weekday())
            domingo = lunes + timedelta(days=6)
            segs = (
                SeguimientoEjercicio.query
                .filter(SeguimientoEjercicio.usuario_id == user_id)
                .filter(SeguimientoEjercicio.fecha_ejecucion >= lunes)
                .filter(SeguimientoEjercicio.fecha_ejecucion <= domingo)
                .order_by(SeguimientoEjercicio.fecha_ejecucion.desc())
                .all()
            )
            dias = {}
            for seg in segs:
                dias.setdefault(seg.fecha_ejecucion, []).append(seg)
            datos_vista = { 'tipo': 'semanal', 'inicio': lunes, 'fin': domingo, 'dias': dias }

        else:  # mensual
            inicio = base.replace(day=1)
            _, dias_mes = monthrange(base.year, base.month)
            fin = inicio + timedelta(days=dias_mes)
            segs = (
                SeguimientoEjercicio.query
                .filter(SeguimientoEjercicio.usuario_id == user_id)
                .filter(SeguimientoEjercicio.fecha_ejecucion >= inicio)
                .filter(SeguimientoEjercicio.fecha_ejecucion < fin)
                .order_by(SeguimientoEjercicio.fecha_ejecucion.asc())
                .all()
            )
            semanas = {}
            for seg in segs:
                lunes = seg.fecha_ejecucion - timedelta(days=seg.fecha_ejecucion.weekday())
                semanas.setdefault(lunes, []).append(seg)
            semanas_ordenadas = []
            for lunes, segs_sem in sorted(semanas.items()):
                domingo = lunes + timedelta(days=6)
                dias_sem = {}
                for seg in segs_sem:
                    dias_sem.setdefault(seg.fecha_ejecucion, []).append(seg)
                semanas_ordenadas.append({ 'inicio': lunes, 'fin': domingo, 'dias': dias_sem })
            datos_vista = { 'tipo': 'mensual', 'semanas': semanas_ordenadas }

        return render_template('admin_progresos_usuario.html', usuario=usuario, datos_vista=datos_vista, vista_actual=vista, fecha_actual=base, active_page='progresos')

    @app.route('/admin/progresos/<int:seg_id>/eliminar', methods=['POST'])
    @admin_required
    @handle_db_error
    def admin_eliminar_progreso(seg_id):
        try:
            seg = SeguimientoEjercicio.query.get(seg_id)
            if not seg:
                flash('Seguimiento no encontrado', 'danger')
                next_url = request.args.get('next') or request.form.get('next')
                return redirect(next_url or url_for('admin_progresos'))
            db.session.delete(seg)
            db.session.commit()
            flash('Seguimiento eliminado', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error eliminando progreso: {e}")
            flash('Error eliminando progreso', 'danger')
        next_url = request.args.get('next') or request.form.get('next')
        return redirect(next_url or url_for('admin_progresos'))

    @app.route('/admin/progresos/<int:seg_id>/actualizar', methods=['POST'])
    @admin_required
    @handle_db_error
    def admin_actualizar_progreso(seg_id):
        try:
            seg = SeguimientoEjercicio.query.get(seg_id)
            if not seg:
                flash('Seguimiento no encontrado', 'danger')
                next_url = request.args.get('next') or request.form.get('next')
                return redirect(next_url or url_for('admin_progresos'))
            seg.series_reps_reales = request.form.get('series', '')
            seg.rpe_real = request.form.get('rpe', '')
            seg.carga_real = request.form.get('carga', '')
            seg.notas = request.form.get('notas', '')
            seg.completado = request.form.get('completado') == 'on'
            seg.fecha_actualizacion = datetime.utcnow()
            db.session.commit()
            flash('Seguimiento actualizado', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando progreso: {e}")
            flash('Error actualizando progreso', 'danger')
        next_url = request.args.get('next') or request.form.get('next')
        return redirect(next_url or url_for('admin_progresos'))

    @app.route('/admin/progresos/<int:user_id>/exportar')
    @admin_required
    def exportar_progreso_pdf(user_id):
        """Exportar el historial de progreso de un usuario a PDF."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import cm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            import io
            from flask import make_response
        except ImportError:
            flash('reportlab no está instalado. Ejecuta: pip install reportlab', 'danger')
            return redirect(url_for('admin_progresos_usuario', user_id=user_id))

        usuario = Usuario.query.get(user_id)
        if not usuario:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('admin_progresos'))

        desde_str = request.args.get('desde')
        hasta_str = request.args.get('hasta')
        hoy = datetime.today().date()
        desde = datetime.strptime(desde_str, '%Y-%m-%d').date() if desde_str else hoy.replace(day=1)
        hasta = datetime.strptime(hasta_str, '%Y-%m-%d').date() if hasta_str else hoy

        seguimientos = (
            SeguimientoEjercicio.query
            .filter(
                SeguimientoEjercicio.usuario_id == user_id,
                SeguimientoEjercicio.fecha_ejecucion >= desde,
                SeguimientoEjercicio.fecha_ejecucion <= hasta,
            )
            .order_by(SeguimientoEjercicio.fecha_ejecucion.asc())
            .all()
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=1.5*cm, leftMargin=1.5*cm,
                                topMargin=2*cm, bottomMargin=1.5*cm)
        styles = getSampleStyleSheet()
        gold = colors.HexColor('#d4900a')
        dark = colors.HexColor('#1a2035')

        title_style = ParagraphStyle('Title', parent=styles['Normal'],
                                     fontSize=18, fontName='Helvetica-Bold',
                                     textColor=dark, spaceAfter=4)
        sub_style = ParagraphStyle('Sub', parent=styles['Normal'],
                                   fontSize=10, textColor=colors.HexColor('#6b7a99'),
                                   spaceAfter=16)
        small_style = ParagraphStyle('Small', parent=styles['Normal'],
                                     fontSize=8, textColor=colors.HexColor('#6b7a99'))

        elements = []
        elements.append(Paragraph('Informe de Progreso', title_style))
        elements.append(Paragraph(
            f'{usuario.nombre} {usuario.apellidos}  ·  '
            f'{desde.strftime("%d/%m/%Y")} – {hasta.strftime("%d/%m/%Y")}',
            sub_style
        ))
        elements.append(Spacer(1, 0.3*cm))

        total = len(seguimientos)
        completados = sum(1 for s in seguimientos if s.completado)
        tasa = f'{round(completados/total*100)}%' if total else '—'
        elements.append(Paragraph(
            f'Total registros: <b>{total}</b>  ·  Completados: <b>{completados}</b>  ·  Tasa: <b>{tasa}</b>',
            small_style
        ))
        elements.append(Spacer(1, 0.5*cm))

        headers = ['Fecha', 'Ejercicio', 'Planificado', 'Realizado', 'RPE', 'Carga', 'Estado']
        data = [headers]
        for seg in seguimientos:
            nombre_ej = '—'
            if seg.ejercicio_asignado and seg.ejercicio_asignado.ejercicio:
                nombre_ej = seg.ejercicio_asignado.ejercicio.nombre
            elif seg.ejercicio_asignado and seg.ejercicio_asignado.nombre_manual:
                nombre_ej = seg.ejercicio_asignado.nombre_manual
            data.append([
                seg.fecha_ejecucion.strftime('%d/%m/%Y') if seg.fecha_ejecucion else '—',
                nombre_ej[:35] + ('…' if len(nombre_ej) > 35 else ''),
                seg.series_reps_planificadas or '—',
                seg.series_reps_reales or '—',
                str(seg.rpe_real) if seg.rpe_real else '—',
                str(seg.carga_real) if seg.carga_real else '—',
                'OK' if seg.completado else 'Pte.',
            ])

        col_widths = [2.2*cm, 6*cm, 2.8*cm, 2.8*cm, 1.5*cm, 1.8*cm, 1.5*cm]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), dark),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f8fc')]),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e6f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        for i, seg in enumerate(seguimientos, start=1):
            if seg.completado:
                table.setStyle(TableStyle([
                    ('TEXTCOLOR', (-1, i), (-1, i), colors.HexColor('#1e7e34')),
                    ('FONTNAME', (-1, i), (-1, i), 'Helvetica-Bold'),
                ]))

        elements.append(table)
        elements.append(Spacer(1, 0.8*cm))
        elements.append(Paragraph(
            f'Generado el {datetime.today().strftime("%d/%m/%Y %H:%M")} — CJFitness',
            small_style
        ))

        doc.build(elements)
        buffer.seek(0)
        filename = f'progreso_{usuario.username}_{desde}_{hasta}.pdf'
        response = make_response(buffer.read())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        log_activity(f"PDF de progreso exportado para usuario {user_id}", session.get('user_id'))
        return response
