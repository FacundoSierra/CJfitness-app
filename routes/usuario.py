import logging
from flask import render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from calendar import monthrange


def init_app(app):
    from models import db, Usuario, Ejercicio, Rutina, Bloque, EjercicioAsignado, Pago, ConfiguracionPagoMensual
    from utils import log_activity, log_error, handle_db_error, login_required

    logger = logging.getLogger('fitness_app')

    @app.route('/dashboard')
    @login_required
    @handle_db_error
    def dashboard():
        user = Usuario.query.get(session['user_id'])
        if user:
            return render_template('usuario_dashboard.html', username=user.nombre)
        return redirect(url_for('login'))

    @app.route('/usuario_rutinas')
    @app.route('/mis_rutinas')
    @login_required
    @handle_db_error
    def mis_rutinas():
        usuario_id = session['user_id']
        usuario = Usuario.query.get(usuario_id)

        # Obtener parámetros de vista
        vista = request.args.get('vista', 'semanal')  # semanal, mensual, diaria
        fecha_param = request.args.get('fecha')
        hoy = datetime.today().date()

        if fecha_param:
            try:
                base = datetime.strptime(fecha_param, "%Y-%m-%d").date()
            except ValueError:
                base = hoy
        else:
            base = hoy

        datos_vista = None

        if vista == 'diaria':
            # Vista diaria - mostrar rutina de un día específico
            rutina = Rutina.query.filter_by(usuario_id=usuario_id, fecha=base).first()
            logger.info(f"[mis_rutinas] diaria base={base} usuario={usuario_id} rutina={'sí' if rutina else 'no'}")
            datos_vista = {
                'tipo': 'diaria',
                'fecha': base,
                'rutina': rutina
            }

        elif vista == 'semanal':
            # Vista semanal - mostrar rutinas de la semana (consulta por rango y agrupación)
            inicio_semana = base - timedelta(days=base.weekday())
            fin_semana = inicio_semana + timedelta(days=6)

            rutinas_semana = (
                Rutina.query
                .filter(Rutina.usuario_id == usuario_id)
                .filter(Rutina.fecha >= inicio_semana)
                .filter(Rutina.fecha <= fin_semana)
                .order_by(Rutina.fecha.asc())
                .all()
            )
            logger.info(f"[mis_rutinas] semanal usuario={usuario_id} rango={inicio_semana}..{fin_semana} count={len(rutinas_semana)} fechas={[r.fecha for r in rutinas_semana]}")

            dias = {}
            for r in rutinas_semana:
                bloques = []
                for bloque in r.bloques:
                    ejercicios = []
                    for e in bloque.ejercicios:
                        ejercicios.append({
                            'id': e.id,
                            'ejercicio': e.ejercicio,
                            'nombre_manual': e.nombre_manual,
                            'series_reps': e.series_reps,
                            'rpe': e.rpe,
                            'carga': e.carga,
                            'categoria': e.categoria,
                            'subcategoria': e.subcategoria
                        })
                    bloques.append({
                        'nombre_bloque': bloque.nombre_bloque,
                        'categoria': bloque.categoria,
                        'ejercicios': ejercicios
                    })
                dias[r.fecha] = bloques

            # Placeholder: asegurar los 7 días en orden lunes→domingo
            for i in range(7):
                dia = inicio_semana + timedelta(days=i)
                if dia not in dias:
                    dias[dia] = []

            datos_vista = {
                'tipo': 'semanal',
                'inicio': inicio_semana,
                'fin': fin_semana,
                'dias': dias
            }

        else:  # vista == 'mensual'
            # Vista mensual - mostrar rutinas del mes por semanas (robusta para diciembre)
            año, mes = base.year, base.month
            inicio_mes = datetime(año, mes, 1).date()
            _, dias_mes = monthrange(año, mes)
            fin_mes = inicio_mes + timedelta(days=dias_mes - 1)

            # Recolectar todas las rutinas del mes
            todas = (
                Rutina.query
                .filter(Rutina.usuario_id == usuario_id)
                .filter(Rutina.fecha >= inicio_mes)
                .filter(Rutina.fecha <= fin_mes)
                .order_by(Rutina.fecha.asc())
                .all()
            )

            semanas_map = {}
            for r in todas:
                lunes = r.fecha - timedelta(days=r.fecha.weekday())
                bloques = []
                for bloque in r.bloques:
                    ejercicios = []
                    for e in bloque.ejercicios:
                        ejercicios.append({
                            'id': e.id,
                            'ejercicio': e.ejercicio,
                            'nombre_manual': e.nombre_manual,
                            'series_reps': e.series_reps,
                            'rpe': e.rpe,
                            'carga': e.carga,
                            'categoria': e.categoria,
                            'subcategoria': e.subcategoria
                        })
                    bloques.append({
                        'nombre_bloque': bloque.nombre_bloque,
                        'categoria': bloque.categoria,
                        'ejercicios': ejercicios
                    })
                semanas_map.setdefault(lunes, []).append({ 'fecha': r.fecha, 'bloques': bloques })

            semanas = []
            for lunes, rutinas_semana in sorted(semanas_map.items()):
                domingo = lunes + timedelta(days=6)
                semanas.append({ 'inicio': lunes, 'fin': domingo, 'rutinas': rutinas_semana })

            datos_vista = { 'tipo': 'mensual', 'semanas': semanas }

        return render_template(
            'usuario_rutinas.html',
            usuario=usuario,
            datos_vista=datos_vista,
            vista_actual=vista,
            fecha_actual=base
        )

    @app.route('/exercises')
    @login_required
    @handle_db_error
    def exercises():
        # Obtener todos los ejercicios agrupados por categoría
        ejercicios = Ejercicio.query.order_by(Ejercicio.categoria, Ejercicio.subcategoria, Ejercicio.nombre).all()

        # Agrupar ejercicios por categoría y subcategoría
        ejercicios_agrupados = {}
        for ejercicio in ejercicios:
            categoria = ejercicio.categoria or "Sin categoría"
            subcategoria = ejercicio.subcategoria or "Sin subcategoría"

            if categoria not in ejercicios_agrupados:
                ejercicios_agrupados[categoria] = {}

            if subcategoria not in ejercicios_agrupados[categoria]:
                ejercicios_agrupados[categoria][subcategoria] = []

            ejercicios_agrupados[categoria][subcategoria].append(ejercicio)

        return render_template('usuario_explicacion_ejercicios.html', ejercicios=ejercicios_agrupados)

    @app.route('/sobre_mi')
    @login_required
    @handle_db_error
    def sobre_mi():
        user = Usuario.query.get(session['user_id'])
        return render_template('usuario_sobre_mi.html', user=user)

    @app.route('/my_info')
    @login_required
    @handle_db_error
    def my_info():
        user = Usuario.query.get(session['user_id'])
        if user:
            return render_template('usuario_my_info.html', user=user)
        return redirect(url_for('dashboard'))

    @app.route('/update_info', methods=['POST'])
    @login_required
    @handle_db_error
    def update_info():
        user = Usuario.query.get(session['user_id'])
        if user:
            user.nombre = request.form.get('nombre', user.nombre)
            user.apellidos = request.form.get('apellidos', user.apellidos)
            user.telefono = request.form.get('telefono', user.telefono)
            user.email = request.form.get('email', user.email)
            user.username = request.form.get('username', user.username)
            # Nuevos campos
            fn = request.form.get('fecha_nacimiento')
            if fn:
                try:
                    user.fecha_nacimiento = datetime.strptime(fn, '%Y-%m-%d').date()
                except Exception:
                    pass
            user.genero = request.form.get('genero') or user.genero
            user.direccion = request.form.get('direccion') or user.direccion
            user.ciudad = request.form.get('ciudad') or user.ciudad
            user.codigo_postal = request.form.get('codigo_postal') or user.codigo_postal
            db.session.commit()
            flash('Información actualizada correctamente', 'success')
            return redirect(url_for('my_info'))
        return redirect(url_for('login'))

    @app.route('/change_password', methods=['GET', 'POST'])
    @login_required
    @handle_db_error
    def change_password():
        if request.method == 'POST':
            user = Usuario.query.get(session['user_id'])
            if user:
                current_password = request.form['current_password']
                new_password = request.form['new_password']
                confirm_password = request.form['confirm_password']

                # Verificar contraseña actual
                if not check_password_hash(user.password, current_password):
                    flash('La contraseña actual es incorrecta', 'danger')
                    return render_template('usuario_change_password.html', user=user)

                # Validar nueva contraseña
                if len(new_password) < 8:
                    flash('La nueva contraseña debe tener al menos 8 caracteres', 'danger')
                    return render_template('usuario_change_password.html', user=user)

                if new_password != confirm_password:
                    flash('Las contraseñas nuevas no coinciden', 'danger')
                    return render_template('usuario_change_password.html', user=user)

                if current_password == new_password:
                    flash('La nueva contraseña debe ser diferente a la actual', 'danger')
                    return render_template('usuario_change_password.html', user=user)

                # Cambiar contraseña
                user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
                db.session.commit()
                flash('Contraseña cambiada exitosamente', 'success')
                return redirect(url_for('my_info'))

            return redirect(url_for('login'))

        user = Usuario.query.get(session['user_id'])
        return render_template('usuario_change_password.html', user=user)

    @app.route('/soporte_usuario')
    @login_required
    @handle_db_error
    def soporte_usuario():
        user = Usuario.query.get(session['user_id'])
        return render_template('usuario_soporte.html', user=user)

    @app.route('/sobre_app')
    @login_required
    def sobre_app():
        moment_actual = datetime.now().strftime('%d/%m/%Y')
        return render_template('usuario_sobre_app.html', moment_actual=moment_actual)

    @app.route('/planes')
    @login_required
    def planes():
        """Página de planes de suscripción"""
        try:
            from payment_service import payment_service
            planes = payment_service.obtener_planes_disponibles()
            return render_template('planes.html', planes=planes)
        except Exception as e:
            log_error(e, session.get('user_id'))
            flash("Error cargando planes", "danger")
            return redirect(url_for('dashboard'))

    @app.route('/pagos')
    @login_required
    def pagos_usuario():
        """Página de historial de pagos del usuario"""
        try:
            usuario = Usuario.query.get(session['user_id'])
            pagos = Pago.query.filter_by(usuario_id=session['user_id']).order_by(Pago.fecha_pago.desc()).all()
            config_pago = ConfiguracionPagoMensual.query.filter_by(
                usuario_id=session['user_id'], activo=True
            ).first()

            return render_template('usuario_pagos.html',
                                 usuario=usuario,
                                 pagos=pagos,
                                 config_pago=config_pago)
        except Exception as e:
            log_error(e, session.get('user_id'))
            flash("Error cargando pagos", "danger")
            return redirect(url_for('dashboard'))
