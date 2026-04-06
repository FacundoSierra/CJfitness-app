import logging
from datetime import date, datetime

from flask import render_template, request, redirect, url_for, session, flash, jsonify


def init_app(app):
    from models import db, Usuario, PerfilNutricional, Alimento, RecomendacionDiaria
    from utils import handle_db_error, login_required
    from nutrition_service import nutrition_service

    logger = logging.getLogger('fitness_app')

    # ── Dashboard nutricional ────────────────────────────────────────────────

    @app.route('/nutricion')
    @login_required
    @handle_db_error
    def nutricion_dashboard():
        usuario = Usuario.query.get(session['user_id'])
        perfil  = PerfilNutricional.query.filter_by(usuario_id=session['user_id']).first()

        macros_objetivo = None
        ultimas_recomendaciones = []

        if perfil:
            calorias = perfil.calorias_objetivo or nutrition_service.calcular_calorias_objetivo(perfil, usuario)
            macros_objetivo = nutrition_service.calcular_macros_objetivo(calorias, perfil.objetivo)

            ultimas_recomendaciones = (
                RecomendacionDiaria.query
                .filter_by(usuario_id=session['user_id'])
                .order_by(RecomendacionDiaria.fecha.desc())
                .limit(3)
                .all()
            )

        return render_template(
            'nutricion_dashboard.html',
            username=usuario.nombre,
            perfil=perfil,
            macros_objetivo=macros_objetivo,
            ultimas_recomendaciones=ultimas_recomendaciones,
        )

    # ── Perfil nutricional ───────────────────────────────────────────────────

    @app.route('/nutricion/perfil', methods=['GET', 'POST'])
    @login_required
    @handle_db_error
    def nutricion_perfil():
        usuario = Usuario.query.get(session['user_id'])
        perfil  = PerfilNutricional.query.filter_by(usuario_id=session['user_id']).first()

        if request.method == 'POST':
            if not perfil:
                perfil = PerfilNutricional(usuario_id=session['user_id'])
                db.session.add(perfil)

            perfil.objetivo         = request.form.get('objetivo', 'mantener')
            perfil.nivel_actividad  = request.form.get('nivel_actividad', 'moderado')

            peso_raw    = request.form.get('peso_kg', '').strip()
            altura_raw  = request.form.get('altura_cm', '').strip()
            perfil.peso_kg    = float(peso_raw)   if peso_raw   else None
            perfil.altura_cm  = float(altura_raw) if altura_raw else None

            # Alergias: campo de texto separado por comas
            alergias_raw = request.form.get('alergias', '').strip()
            perfil.alergias = [a.strip().lower() for a in alergias_raw.split(',') if a.strip()]

            # Preferencias: checkboxes múltiples
            perfil.preferencias = request.form.getlist('preferencias')

            # Calcular y guardar calorías objetivo
            if perfil.peso_kg and perfil.altura_cm:
                perfil.calorias_objetivo = nutrition_service.calcular_calorias_objetivo(perfil, usuario)

            perfil.fecha_actualizacion = datetime.utcnow()
            db.session.commit()

            flash('Perfil nutricional guardado correctamente', 'success')
            return redirect(url_for('nutricion_dashboard'))

        return render_template(
            'nutricion_perfil.html',
            username=usuario.nombre,
            usuario=usuario,
            perfil=perfil,
        )

    # ── Menú del día ─────────────────────────────────────────────────────────

    @app.route('/nutricion/recomendar', methods=['GET', 'POST'])
    @login_required
    @handle_db_error
    def nutricion_recomendar():
        usuario = Usuario.query.get(session['user_id'])
        perfil  = PerfilNutricional.query.filter_by(usuario_id=session['user_id']).first()

        if not perfil:
            flash('Primero configura tu perfil nutricional', 'warning')
            return redirect(url_for('nutricion_perfil'))

        hoy = date.today()
        recomendacion = RecomendacionDiaria.query.filter_by(
            usuario_id=session['user_id'], fecha=hoy
        ).first()

        # GET: mostrar la existente si hay; POST: regenerar siempre
        if request.method == 'GET' and recomendacion:
            calorias_objetivo = perfil.calorias_objetivo or nutrition_service.calcular_calorias_objetivo(perfil, usuario)
            macros_objetivo   = nutrition_service.calcular_macros_objetivo(calorias_objetivo, perfil.objetivo)
            return render_template(
                'nutricion_menu.html',
                username=usuario.nombre,
                recomendacion=recomendacion,
                macros_objetivo=macros_objetivo,
                calorias_objetivo=calorias_objetivo,
            )

        # Buscar el menú del día anterior para rotar alimentos
        from datetime import timedelta
        ayer = hoy - timedelta(days=1)
        rec_anterior = RecomendacionDiaria.query.filter_by(
            usuario_id=session['user_id'], fecha=ayer
        ).first()

        resultado = nutrition_service.generar_menu(perfil, usuario, rec_anterior)

        if recomendacion:
            # Regenerar: actualizar el existente
            recomendacion.menu_json        = resultado['menu_json']
            recomendacion.calorias_totales = resultado['calorias_totales']
            recomendacion.macros_json      = resultado['macros_json']
            recomendacion.fecha_creacion   = datetime.utcnow()
            recomendacion.valoracion_usuario = None
            recomendacion.notas_usuario      = None
        else:
            recomendacion = RecomendacionDiaria(
                usuario_id      = session['user_id'],
                fecha           = hoy,
                menu_json       = resultado['menu_json'],
                calorias_totales= resultado['calorias_totales'],
                macros_json     = resultado['macros_json'],
            )
            db.session.add(recomendacion)

        db.session.commit()

        calorias_objetivo = perfil.calorias_objetivo or nutrition_service.calcular_calorias_objetivo(perfil, usuario)
        macros_objetivo   = nutrition_service.calcular_macros_objetivo(calorias_objetivo, perfil.objetivo)

        return render_template(
            'nutricion_menu.html',
            username=usuario.nombre,
            recomendacion=recomendacion,
            macros_objetivo=macros_objetivo,
            calorias_objetivo=calorias_objetivo,
        )

    # ── Valorar recomendación ─────────────────────────────────────────────────

    @app.route('/nutricion/valorar/<int:rec_id>', methods=['POST'])
    @login_required
    @handle_db_error
    def nutricion_valorar(rec_id):
        recomendacion = RecomendacionDiaria.query.filter_by(
            id=rec_id, usuario_id=session['user_id']
        ).first_or_404()

        valoracion = request.form.get('valoracion')
        notas      = request.form.get('notas_usuario', '').strip()

        if valoracion:
            try:
                v = int(valoracion)
                if 1 <= v <= 5:
                    recomendacion.valoracion_usuario = v
            except ValueError:
                pass

        recomendacion.notas_usuario = notas or None
        db.session.commit()

        flash('Valoración guardada, ¡gracias!', 'success')
        return redirect(url_for('nutricion_recomendar'))

    # ── Historial ─────────────────────────────────────────────────────────────

    @app.route('/nutricion/historial')
    @login_required
    @handle_db_error
    def nutricion_historial():
        usuario = Usuario.query.get(session['user_id'])
        pagina  = request.args.get('pagina', 1, type=int)

        total = RecomendacionDiaria.query.filter_by(usuario_id=session['user_id']).count()
        recomendaciones = (
            RecomendacionDiaria.query
            .filter_by(usuario_id=session['user_id'])
            .order_by(RecomendacionDiaria.fecha.desc())
            .offset((pagina - 1) * 10)
            .limit(10)
            .all()
        )

        total_paginas = (total + 9) // 10

        return render_template(
            'nutricion_historial.html',
            username=usuario.nombre,
            recomendaciones=recomendaciones,
            pagina=pagina,
            total_paginas=total_paginas,
            total=total,
            today=date.today(),
        )

    # ── API búsqueda de alimentos ─────────────────────────────────────────────

    @app.route('/api/nutricion/buscar')
    @login_required
    def api_nutricion_buscar():
        q = request.args.get('q', '').strip()
        if len(q) < 2:
            return jsonify([])
        try:
            resultados = nutrition_service.buscar_alimento(q)
            return jsonify(resultados)
        except Exception as exc:
            logger.error(f'api_nutricion_buscar error: {exc}')
            return jsonify([])