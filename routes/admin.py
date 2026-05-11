import logging
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
from calendar import monthrange
from collections import defaultdict
from sqlalchemy import func


def init_app(app):
    from models import db, Usuario, Ejercicio, Rutina, Bloque, EjercicioAsignado, Plan, Pago, ConfiguracionPagoMensual, SeguimientoEjercicio, FeedbackSesion, EjercicioCompleto, EventoAdmin
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
        usuario = db.get_or_404(Usuario, user_id)

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
        usuario = db.get_or_404(Usuario, user_id)

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
        total_filas = (inicio_semana + ultimo_dia + 6) // 7

        # Pre-cargar todas las rutinas del mes en UNA sola query
        ultimo_dia_mes = primer_dia_mes.replace(day=ultimo_dia).date()
        rutinas_mes = Rutina.query.filter_by(usuario_id=user_id)\
            .filter(Rutina.fecha >= primer_dia_mes.date())\
            .filter(Rutina.fecha <= ultimo_dia_mes).all()
        rutinas_dict = {r.fecha: r for r in rutinas_mes}

        # Generar todas las fechas del calendario
        dias_calendario = []
        dia_actual = primer_dia_mes - timedelta(days=inicio_semana)

        for _ in range(total_filas):
            semana = []
            for _ in range(7):
                fecha = dia_actual.date()
                semana.append({
                    "fecha": fecha,
                    "es_del_mes": fecha.month == mes,
                    "rutina": rutinas_dict.get(fecha)
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

                ejercicios    = request.form.getlist(f"ejercicio_{bloque_id}[]")
                series_jsons  = request.form.getlist(f"series_json_{bloque_id}[]")
                bloques_ej    = request.form.getlist(f"bloque_ej_{bloque_id}[]")
                categorias_ej = request.form.getlist(f"categoria_ej_{bloque_id}[]")

                logger.debug(f"Bloque {bloque_id}: {len(ejercicios)} ejercicios, {len(series_jsons)} series_json")

                for i in range(len(ejercicios)):
                    nombre_ej    = ejercicios[i]
                    bloque_ej    = bloques_ej[i]    if i < len(bloques_ej)    else None
                    categoria_ej = categorias_ej[i] if i < len(categorias_ej) else None
                    sj           = series_jsons[i]  if i < len(series_jsons)  else None

                    asignado = EjercicioAsignado(
                        bloque_id=bloque.id,
                        ejercicio_id=None,
                        nombre_manual=nombre_ej,
                        series_json=sj,
                        categoria=bloque_ej,
                        subcategoria=categoria_ej
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

            # Obtener o crear rutina (conservar el mismo ID)
            rutina = Rutina.query.filter_by(usuario_id=user_id, fecha=fecha).first()
            if not rutina:
                rutina = Rutina(usuario_id=user_id, fecha=fecha)
                db.session.add(rutina)
                db.session.flush()
            logger.info(f"Rutina ID={rutina.id}")

            # Detectar bloques enviados por el formulario (índices posicionales)
            bloque_ids = []
            for key in request.form:
                if key.startswith("ejercicio_") and key.endswith("[]"):
                    bid = key.split("_")[1].replace("[]", "")
                    if bid not in bloque_ids:
                        bloque_ids.append(bid)

            # Bloques existentes ordenados por ID (posición estable)
            bloques_existentes = sorted(rutina.bloques, key=lambda b: b.id)

            for pos, bloque_id in enumerate(bloque_ids):
                categoria_bloque = request.form.get(f"categoria_bloque_{bloque_id}") or "General"

                # UPDATE bloque existente en esa posición, o INSERT si es nuevo
                if pos < len(bloques_existentes):
                    bloque = bloques_existentes[pos]
                    bloque.nombre_bloque = f'Bloque {bloque_id}'
                    bloque.categoria = categoria_bloque
                else:
                    bloque = Bloque(rutina_id=rutina.id,
                                    nombre_bloque=f'Bloque {bloque_id}',
                                    categoria=categoria_bloque)
                    db.session.add(bloque)
                    db.session.flush()

                ejercicios    = request.form.getlist(f"ejercicio_{bloque_id}[]")
                series_jsons  = request.form.getlist(f"series_json_{bloque_id}[]")
                bloques_ej    = request.form.getlist(f"bloque_ej_{bloque_id}[]")
                categorias_ej = request.form.getlist(f"categoria_ej_{bloque_id}[]")

                # Ejercicios existentes en este bloque ordenados por ID
                ejs_existentes = sorted(bloque.ejercicios, key=lambda e: e.id)

                for i, nombre_ej in enumerate(ejercicios):
                    bloque_ej    = bloques_ej[i]    if i < len(bloques_ej)    else None
                    categoria_ej = categorias_ej[i] if i < len(categorias_ej) else None
                    sj           = series_jsons[i]  if i < len(series_jsons)  else None

                    if i < len(ejs_existentes):
                        # UPDATE ejercicio existente
                        ej = ejs_existentes[i]
                        ej.nombre_manual = nombre_ej
                        ej.series_json   = sj
                        ej.categoria     = bloque_ej
                        ej.subcategoria  = categoria_ej
                        ej.ejercicio_id  = None
                    else:
                        # INSERT nuevo ejercicio
                        ej = EjercicioAsignado(
                            bloque_id=bloque.id,
                            ejercicio_id=None,
                            nombre_manual=nombre_ej,
                            series_json=sj,
                            categoria=bloque_ej,
                            subcategoria=categoria_ej
                        )
                        db.session.add(ej)

                # Eliminar ejercicios sobrantes (el formulario tiene menos que la BD)
                for ej_extra in ejs_existentes[len(ejercicios):]:
                    SeguimientoEjercicio.query.filter_by(
                        ejercicio_asignado_id=ej_extra.id
                    ).delete(synchronize_session=False)
                    db.session.delete(ej_extra)

            # Eliminar bloques sobrantes (el formulario tiene menos bloques que la BD)
            for bloque_extra in bloques_existentes[len(bloque_ids):]:
                for ej_extra in bloque_extra.ejercicios:
                    SeguimientoEjercicio.query.filter_by(
                        ejercicio_asignado_id=ej_extra.id
                    ).delete(synchronize_session=False)
                db.session.delete(bloque_extra)

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
            for bloque in rutina.bloques:
                for ej in bloque.ejercicios:
                    SeguimientoEjercicio.query.filter_by(
                        ejercicio_asignado_id=ej.id
                    ).delete(synchronize_session=False)
                    db.session.delete(ej)
                db.session.delete(bloque)
            db.session.delete(rutina)
            db.session.commit()

            flash(f'✅ Rutina eliminada para {fecha.strftime("%d/%m/%Y")}', 'success')
        else:
            flash('❌ No se encontró la rutina para eliminar', 'danger')

        return redirect(url_for('ver_rutinas_usuario', user_id=user_id))

    # ------------------ ADMIN ESTADISTICAS ------------------

    @app.route('/admin_estadisticas')
    @admin_required
    @handle_db_error
    def admin_estadisticas():
        from datetime import date, timedelta

        hoy   = date.today()
        hace30 = hoy - timedelta(days=29)
        hace7  = hoy - timedelta(days=6)

        # ── KPIs globales ──────────────────────────────────────────────────
        total_sesiones   = SeguimientoEjercicio.query.count()
        total_completados = SeguimientoEjercicio.query.filter_by(completado=True).count()
        tasa_global = round(total_completados / total_sesiones * 100) if total_sesiones else 0

        usuarios_activos_mes = db.session.query(
            func.count(func.distinct(SeguimientoEjercicio.usuario_id))
        ).filter(SeguimientoEjercicio.fecha_ejecucion >= hoy.replace(day=1)).scalar() or 0

        # ── Actividad por día (últimos 30 días) ────────────────────────────
        filas_dia = db.session.query(
            SeguimientoEjercicio.fecha_ejecucion,
            func.count(SeguimientoEjercicio.id).label('total'),
            func.sum(db.cast(SeguimientoEjercicio.completado, db.Integer)).label('completados')
        ).filter(
            SeguimientoEjercicio.fecha_ejecucion >= hace30
        ).group_by(SeguimientoEjercicio.fecha_ejecucion).all()

        # Rellenar días sin actividad con 0
        mapa_dia = {f.fecha_ejecucion: (f.total, f.completados or 0) for f in filas_dia}
        dias_labels, dias_total, dias_completados = [], [], []
        for i in range(30):
            d = hace30 + timedelta(days=i)
            dias_labels.append(d.strftime('%d/%m'))
            t, c = mapa_dia.get(d, (0, 0))
            dias_total.append(t)
            dias_completados.append(c)

        # ── Top 8 ejercicios más realizados ───────────────────────────────
        top_ejercicios = db.session.query(
            func.coalesce(Ejercicio.nombre, EjercicioAsignado.nombre_manual).label('nombre'),
            func.count(SeguimientoEjercicio.id).label('total')
        ).join(EjercicioAsignado, SeguimientoEjercicio.ejercicio_asignado_id == EjercicioAsignado.id
        ).outerjoin(Ejercicio, EjercicioAsignado.ejercicio_id == Ejercicio.id
        ).group_by(func.coalesce(Ejercicio.nombre, EjercicioAsignado.nombre_manual)
        ).order_by(func.count(SeguimientoEjercicio.id).desc()
        ).limit(8).all()

        # ── Distribución por categoría ─────────────────────────────────────
        por_categoria = db.session.query(
            EjercicioAsignado.categoria,
            func.count(SeguimientoEjercicio.id).label('total')
        ).join(SeguimientoEjercicio, EjercicioAsignado.id == SeguimientoEjercicio.ejercicio_asignado_id
        ).filter(EjercicioAsignado.categoria.isnot(None)
        ).group_by(EjercicioAsignado.categoria
        ).order_by(func.count(SeguimientoEjercicio.id).desc()
        ).all()

        # ── Ranking de usuarios ────────────────────────────────────────────
        usuarios_stats = db.session.query(
            Usuario,
            func.count(SeguimientoEjercicio.id).label('total'),
            func.sum(db.cast(SeguimientoEjercicio.completado, db.Integer)).label('completados')
        ).join(SeguimientoEjercicio, Usuario.id == SeguimientoEjercicio.usuario_id
        ).filter(Usuario.rol != 'admin'
        ).group_by(Usuario.id
        ).order_by(func.count(SeguimientoEjercicio.id).desc()
        ).all()

        # Calcular el ejercicio más popular para KPI
        ejercicio_top = top_ejercicios[0].nombre if top_ejercicios else '—'

        return render_template('admin_estadisticas.html',
                               username=session.get('username'),
                               active_page='estadisticas',
                               # KPIs
                               total_sesiones=total_sesiones,
                               tasa_global=tasa_global,
                               usuarios_activos_mes=usuarios_activos_mes,
                               ejercicio_top=ejercicio_top,
                               # Gráficas (JSON para Chart.js)
                               dias_labels=dias_labels,
                               dias_total=dias_total,
                               dias_completados=dias_completados,
                               top_ejercicios=top_ejercicios,
                               por_categoria=por_categoria,
                               # Tabla ranking
                               usuarios_stats=usuarios_stats)

    # --------------------- ADMIN BORRAR/EDITAR USUARIO ---------------------------------------------

    @app.route('/admin/usuarios/borrar/<int:user_id>', methods=['POST'])
    @admin_required
    @handle_db_error
    def borrar_usuario(user_id):
        user = db.get_or_404(Usuario, user_id)
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
        user = db.get_or_404(Usuario, user_id)
        if request.method == 'POST':
            nombre = request.form.get('nombre', '').strip()
            apellidos = request.form.get('apellidos', '').strip()
            email = request.form.get('email', '').strip()
            if not nombre or not apellidos or not email:
                flash("Nombre, apellidos y email son obligatorios.", "danger")
                return redirect(url_for('editar_usuario', user_id=user_id))
            user.nombre = nombre
            user.apellidos = apellidos
            user.email = email
            user.telefono = request.form.get('telefono', '').strip()
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
            usuario_id = request.form.get('usuario_id', '').strip()
            cantidad = request.form.get('cantidad', '').strip()
            metodo_pago = request.form.get('metodo_pago', '').strip()
            forma_pago = request.form.get('forma_pago', '')
            observaciones = request.form.get('observaciones', '')

            # Validaciones
            if not usuario_id or not cantidad or not metodo_pago:
                flash('Usuario, cantidad y método de pago son obligatorios', 'danger')
                return redirect(url_for('admin_pagos'))

            # Verificar que el usuario existe
            usuario = db.session.get(Usuario, usuario_id)
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
            pago = db.get_or_404(Pago, pago_id)

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
            pago = db.get_or_404(Pago, pago_id)

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
        ejercicio = db.get_or_404(Ejercicio, e_id)
        db.session.delete(ejercicio)
        db.session.commit()
        flash('Ejercicio eliminado', 'success')
        return redirect(url_for('admin_ejercicios'))

    @app.route('/admin_ejercicios/editar/<int:e_id>', methods=['POST'])
    @admin_required
    @handle_db_error
    def admin_ejercicios_editar(e_id):
        ejercicio = db.get_or_404(Ejercicio, e_id)
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
                usuario = db.session.get(Usuario, usuario_id)
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
                usuario = db.session.get(Usuario, usuario_id)
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
                usuario = db.session.get(Usuario, usuario_id)
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
        """Listado de usuarios con stats de progreso."""
        try:
            usuarios = Usuario.query.filter(Usuario.rol != 'admin').order_by(Usuario.nombre).all()
            # Total registros por usuario
            conteos = dict(
                db.session.query(SeguimientoEjercicio.usuario_id, func.count(SeguimientoEjercicio.id))
                .group_by(SeguimientoEjercicio.usuario_id)
                .all()
            )
            # Registros completados por usuario
            completados = dict(
                db.session.query(SeguimientoEjercicio.usuario_id, func.count(SeguimientoEjercicio.id))
                .filter(SeguimientoEjercicio.completado == True)
                .group_by(SeguimientoEjercicio.usuario_id)
                .all()
            )
            return render_template('admin_progresos_usuarios.html',
                                   usuarios=usuarios, conteos=conteos, completados=completados,
                                   active_page='progresos')
        except Exception as e:
            logger.error(f"Error listando usuarios de progresos: {e}")
            flash('Error listando usuarios', 'danger')
            return render_template('admin_progresos_usuarios.html',
                                   usuarios=[], conteos={}, completados={},
                                   active_page='progresos')

    @app.route('/admin/progresos/<int:user_id>')
    @admin_required
    @handle_db_error
    def admin_progresos_usuario(user_id):
        """Vista de progresos por usuario con modos: diaria, semanal, mensual."""
        usuario = db.session.get(Usuario, user_id)
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

        return render_template('admin_progresos_usuario.html', usuario=usuario, datos_vista=datos_vista, vista_actual=vista, fecha_actual=base, timedelta=timedelta, active_page='progresos')

    @app.route('/admin/progresos/<int:seg_id>/eliminar', methods=['POST'])
    @admin_required
    @handle_db_error
    def admin_eliminar_progreso(seg_id):
        try:
            seg = db.session.get(SeguimientoEjercicio, seg_id)
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
            seg = db.session.get(SeguimientoEjercicio, seg_id)
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

        usuario = db.session.get(Usuario, user_id)
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

    # ── FEEDBACK DE SESIÓN (ADMIN) ────────────────────────────────────────────

    @app.route('/admin/feedback/<int:feedback_id>/responder', methods=['POST'])
    @admin_required
    def admin_responder_feedback(feedback_id):
        """El entrenador responde al feedback de un usuario."""
        fb = db.get_or_404(FeedbackSesion, feedback_id)
        data = request.get_json() or {}
        respuesta = (data.get('respuesta') or '').strip()
        if not respuesta:
            return jsonify({'success': False, 'message': 'La respuesta no puede estar vacía'}), 400
        fb.respuesta_entrenador = respuesta
        fb.fecha_entrenador = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/admin/usuarios/<int:user_id>/feedbacks')
    @admin_required
    def admin_feedbacks_usuario(user_id):
        """Lista de feedbacks de un usuario para el panel admin."""
        usuario = db.get_or_404(Usuario, user_id)
        feedbacks = (
            FeedbackSesion.query
            .filter_by(usuario_id=user_id)
            .order_by(FeedbackSesion.fecha.desc())
            .limit(60)
            .all()
        )
        return render_template(
            'admin_feedbacks_usuario.html',
            usuario=usuario,
            feedbacks=feedbacks
        )

    # ── COPIAR SEMANA ─────────────────────────────────────────────────────────

    @app.route('/admin_entrenamientos/<int:user_id>/copiar_semana', methods=['POST'])
    @admin_required
    def copiar_semana_usuario(user_id):
        """Copia todas las rutinas de una semana a otra (deep copy)."""
        try:
            source_str = request.form.get('source_week')
            target_str = request.form.get('target_week')
            if not source_str or not target_str:
                flash('Debes seleccionar semana origen y destino', 'danger')
                return redirect(url_for('calendario_entrenamientos_usuario', user_id=user_id))

            # Normalizar a lunes de cada semana
            source_day = datetime.strptime(source_str, '%Y-%m-%d').date()
            target_day = datetime.strptime(target_str, '%Y-%m-%d').date()
            source_lunes = source_day - timedelta(days=source_day.weekday())
            target_lunes = target_day - timedelta(days=target_day.weekday())

            if source_lunes == target_lunes:
                flash('La semana origen y destino son la misma', 'warning')
                return redirect(url_for('calendario_entrenamientos_usuario', user_id=user_id,
                                        mes=source_lunes.strftime('%Y-%m')))

            # Buscar rutinas en la semana origen
            rutinas_origen = (
                Rutina.query
                .filter_by(usuario_id=user_id)
                .filter(Rutina.fecha >= source_lunes)
                .filter(Rutina.fecha <= source_lunes + timedelta(days=6))
                .all()
            )

            if not rutinas_origen:
                flash('La semana origen no tiene rutinas asignadas', 'warning')
                return redirect(url_for('calendario_entrenamientos_usuario', user_id=user_id,
                                        mes=source_lunes.strftime('%Y-%m')))

            copiados = 0
            for rutina_src in rutinas_origen:
                offset = rutina_src.fecha.weekday()
                fecha_dest = target_lunes + timedelta(days=offset)

                # Borrar rutina existente en destino (cascade)
                rutina_dest = Rutina.query.filter_by(usuario_id=user_id, fecha=fecha_dest).first()
                if rutina_dest:
                    db.session.delete(rutina_dest)
                    db.session.flush()

                # Crear nueva rutina
                nueva_rutina = Rutina(usuario_id=user_id, fecha=fecha_dest)
                db.session.add(nueva_rutina)
                db.session.flush()

                for bloque_src in rutina_src.bloques:
                    nuevo_bloque = Bloque(
                        rutina_id=nueva_rutina.id,
                        nombre_bloque=bloque_src.nombre_bloque,
                        categoria=bloque_src.categoria
                    )
                    db.session.add(nuevo_bloque)
                    db.session.flush()

                    for ej_src in bloque_src.ejercicios:
                        nuevo_ej = EjercicioAsignado(
                            bloque_id=nuevo_bloque.id,
                            ejercicio_id=ej_src.ejercicio_id,
                            nombre_manual=ej_src.nombre_manual,
                            series_reps=ej_src.series_reps,
                            rpe=ej_src.rpe,
                            carga=ej_src.carga,
                            series_json=ej_src.series_json,
                            categoria=ej_src.categoria,
                            subcategoria=ej_src.subcategoria
                        )
                        db.session.add(nuevo_ej)

                copiados += 1

            db.session.commit()
            flash(f'{copiados} día{"s" if copiados != 1 else ""} copiado{"s" if copiados != 1 else ""} correctamente', 'success')
            return redirect(url_for('calendario_entrenamientos_usuario', user_id=user_id,
                                    mes=target_lunes.strftime('%Y-%m')))

        except Exception as e:
            db.session.rollback()
            log_error(e, session.get('user_id'))
            flash(f'Error al copiar la semana: {str(e)}', 'danger')
            return redirect(url_for('calendario_entrenamientos_usuario', user_id=user_id))

    # ─────────────────────────────────────────────────────────────────────────
    # CALENDARIO ADMIN
    # ─────────────────────────────────────────────────────────────────────────

    @app.route('/admin/calendario')
    @admin_required
    def admin_calendario():
        return render_template('admin_calendario.html')

    @app.route('/admin/api/eventos')
    @admin_required
    def api_eventos_admin():
        start_str = request.args.get('start', '')
        end_str   = request.args.get('end', '')
        try:
            start = datetime.fromisoformat(start_str[:10])
            end   = datetime.fromisoformat(end_str[:10])
        except Exception:
            return jsonify([])

        eventos = EventoAdmin.query.filter(
            EventoAdmin.fecha_inicio >= start,
            EventoAdmin.fecha_inicio <  end
        ).all()

        result = []
        for e in eventos:
            item = {
                'id':    f'e-{e.id}',
                'title': e.titulo,
                'color': e.color,
                'extendedProps': {
                    'tipo':        'evento',
                    'descripcion': e.descripcion or '',
                    'db_id':       e.id,
                }
            }
            if e.todo_el_dia:
                item['start']  = e.fecha_inicio.strftime('%Y-%m-%d')
                item['allDay'] = True
                if e.fecha_fin:
                    item['end'] = e.fecha_fin.strftime('%Y-%m-%d')
            else:
                item['start'] = e.fecha_inicio.isoformat()
                if e.fecha_fin:
                    item['end'] = e.fecha_fin.isoformat()
            result.append(item)
        return jsonify(result)

    @app.route('/admin/api/rutinas-calendario')
    @admin_required
    def api_rutinas_calendario():
        start_str = request.args.get('start', '')
        end_str   = request.args.get('end', '')
        try:
            start = datetime.fromisoformat(start_str[:10]).date()
            end   = datetime.fromisoformat(end_str[:10]).date()
        except Exception:
            return jsonify([])

        rutinas = (Rutina.query
                   .join(Usuario, Rutina.usuario_id == Usuario.id)
                   .filter(Rutina.fecha >= start, Rutina.fecha < end)
                   .add_columns(Usuario.nombre, Usuario.apellidos)
                   .all())

        result = []
        for rutina, nombre, apellidos in rutinas:
            result.append({
                'id':      f'r-{rutina.id}',
                'title':   f'{nombre} {apellidos}',
                'start':   rutina.fecha.isoformat(),
                'allDay':  True,
                'color':   '#28a745',
                'editable': False,
                'extendedProps': {
                    'tipo':       'rutina',
                    'rutina_id':  rutina.id,
                    'usuario_id': rutina.usuario_id,
                }
            })
        return jsonify(result)

    @app.route('/admin/api/eventos', methods=['POST'])
    @admin_required
    def api_crear_evento_admin():
        data = request.get_json() or {}
        try:
            fecha_inicio = datetime.fromisoformat(data['fecha_inicio'])
            fecha_fin    = datetime.fromisoformat(data['fecha_fin']) if data.get('fecha_fin') else None
            evento = EventoAdmin(
                titulo       = data.get('titulo', 'Sin título').strip(),
                descripcion  = data.get('descripcion', '').strip() or None,
                fecha_inicio = fecha_inicio,
                fecha_fin    = fecha_fin,
                todo_el_dia  = bool(data.get('todo_el_dia', False)),
                color        = data.get('color', '#3788d8'),
            )
            db.session.add(evento)
            db.session.commit()
            return jsonify({'ok': True, 'id': evento.id}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/admin/api/eventos/<int:evento_id>', methods=['PUT'])
    @admin_required
    def api_editar_evento_admin(evento_id):
        evento = db.get_or_404(EventoAdmin, evento_id)
        data   = request.get_json() or {}
        try:
            if 'titulo'      in data: evento.titulo      = data['titulo'].strip()
            if 'descripcion' in data: evento.descripcion = data['descripcion'].strip() or None
            if 'color'       in data: evento.color       = data['color']
            if 'todo_el_dia' in data: evento.todo_el_dia = bool(data['todo_el_dia'])
            if 'fecha_inicio' in data:
                evento.fecha_inicio = datetime.fromisoformat(data['fecha_inicio'])
            if 'fecha_fin' in data:
                evento.fecha_fin = datetime.fromisoformat(data['fecha_fin']) if data['fecha_fin'] else None
            db.session.commit()
            return jsonify({'ok': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/admin/api/eventos/<int:evento_id>', methods=['DELETE'])
    @admin_required
    def api_borrar_evento_admin(evento_id):
        evento = db.get_or_404(EventoAdmin, evento_id)
        try:
            db.session.delete(evento)
            db.session.commit()
            return '', 204
        except Exception as e:
            db.session.rollback()
            return jsonify({'ok': False, 'error': str(e)}), 400
