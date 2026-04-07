import logging
from datetime import date, datetime

from flask import render_template, request, redirect, url_for, session, flash, jsonify


def init_app(app):
    from models import db, Usuario, PerfilNutricional, Alimento, RecomendacionDiaria, PreferenciaAlimento, ValoracionComida
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

    # ── Biblioteca de alimentos ───────────────────────────────────────────────

    @app.route('/nutricion/alimentos')
    @login_required
    @handle_db_error
    def nutricion_alimentos():
        usuario = Usuario.query.get(session['user_id'])
        return render_template('nutricion_alimentos.html', username=usuario.nombre)

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

    @app.route('/api/nutricion/alimentos')
    @login_required
    def api_nutricion_alimentos():
        from models import Alimento
        q         = request.args.get('q', '').strip()
        categoria = request.args.get('categoria', '').strip()
        try:
            query = Alimento.query
            if q:
                query = query.filter(Alimento.nombre.ilike(f'%{q}%'))
            if categoria:
                query = query.filter_by(categoria=categoria)
            alimentos = query.limit(20).all()
            # Si < 3 resultados y hay búsqueda, intentar OFF
            if len(alimentos) < 3 and q:
                nutrition_service.buscar_alimento_off(q)
                alimentos = query.limit(20).all()
            return jsonify([nutrition_service._alimento_to_dict(a) for a in alimentos])
        except Exception as exc:
            logger.error(f'api_nutricion_alimentos error: {exc}')
            return jsonify([])

    # ── Preferencias de alimentos ─────────────────────────────────────────────

    @app.route('/api/nutricion/preferencias', methods=['GET'])
    @login_required
    def api_nutricion_preferencias_get():
        try:
            prefs = PreferenciaAlimento.query.filter_by(
                usuario_id=session['user_id']
            ).order_by(PreferenciaAlimento.creado.desc()).all()
            return jsonify([{'nombre': p.nombre_alimento, 'tipo': p.tipo} for p in prefs])
        except Exception as exc:
            logger.error(f'api_nutricion_preferencias get error: {exc}')
            return jsonify([])

    @app.route('/api/nutricion/preferencia', methods=['POST'])
    @login_required
    def api_nutricion_preferencia_add():
        data   = request.get_json(silent=True) or {}
        nombre = (data.get('nombre') or '').strip()[:200]
        tipo   = data.get('tipo', 'no_me_gusta')
        if not nombre:
            return jsonify({'ok': False, 'error': 'nombre requerido'}), 400
        try:
            pref = PreferenciaAlimento.query.filter_by(
                usuario_id=session['user_id'], nombre_alimento=nombre
            ).first()
            if not pref:
                pref = PreferenciaAlimento(
                    usuario_id=session['user_id'],
                    nombre_alimento=nombre,
                    tipo=tipo,
                )
                db.session.add(pref)
                db.session.commit()
            return jsonify({'ok': True})
        except Exception as exc:
            db.session.rollback()
            logger.error(f'api_nutricion_preferencia add error: {exc}')
            return jsonify({'ok': False, 'error': str(exc)}), 500

    @app.route('/api/nutricion/preferencia', methods=['DELETE'])
    @login_required
    def api_nutricion_preferencia_del():
        data   = request.get_json(silent=True) or {}
        nombre = (data.get('nombre') or '').strip()
        if not nombre:
            return jsonify({'ok': False, 'error': 'nombre requerido'}), 400
        try:
            PreferenciaAlimento.query.filter_by(
                usuario_id=session['user_id'], nombre_alimento=nombre
            ).delete()
            db.session.commit()
            return jsonify({'ok': True})
        except Exception as exc:
            db.session.rollback()
            logger.error(f'api_nutricion_preferencia del error: {exc}')
            return jsonify({'ok': False, 'error': str(exc)}), 500

    # ── Valoración por comida individual ─────────────────────────────────────

    @app.route('/api/nutricion/valorar_comida', methods=['POST'])
    @login_required
    def api_nutricion_valorar_comida():
        data          = request.get_json(silent=True) or {}
        nombre_comida = (data.get('nombre_comida') or '').strip()[:200]
        try:
            valoracion = int(data.get('valoracion', 0))
        except (ValueError, TypeError):
            valoracion = 0
        if not nombre_comida or not (1 <= valoracion <= 5):
            return jsonify({'ok': False, 'error': 'datos inválidos'}), 400
        try:
            v = ValoracionComida(
                usuario_id    = session['user_id'],
                nombre_comida = nombre_comida,
                valoracion    = valoracion,
            )
            db.session.add(v)
            db.session.commit()
            return jsonify({'ok': True})
        except Exception as exc:
            db.session.rollback()
            logger.error(f'api_nutricion_valorar_comida error: {exc}')
            return jsonify({'ok': False, 'error': str(exc)}), 500

    # ── Estadísticas de valoraciones ─────────────────────────────────────────

    @app.route('/nutricion/estadisticas')
    @login_required
    @handle_db_error
    def nutricion_estadisticas():
        from sqlalchemy import func
        usuario = Usuario.query.get(session['user_id'])

        stats_comidas = (
            db.session.query(
                ValoracionComida.nombre_comida,
                func.avg(ValoracionComida.valoracion).label('media'),
                func.count(ValoracionComida.id).label('total'),
            )
            .filter_by(usuario_id=session['user_id'])
            .group_by(ValoracionComida.nombre_comida)
            .order_by(func.avg(ValoracionComida.valoracion).desc())
            .all()
        )

        top_mejores = stats_comidas[:3]
        top_peores  = list(reversed(stats_comidas))[:3]

        avg_menus = (
            db.session.query(func.avg(RecomendacionDiaria.valoracion_usuario))
            .filter(
                RecomendacionDiaria.usuario_id == session['user_id'],
                RecomendacionDiaria.valoracion_usuario.isnot(None),
            )
            .scalar()
        )
        avg_comidas = (
            db.session.query(func.avg(ValoracionComida.valoracion))
            .filter_by(usuario_id=session['user_id'])
            .scalar()
        )

        return render_template(
            'nutricion_estadisticas.html',
            username    = usuario.nombre,
            top_mejores = top_mejores,
            top_peores  = top_peores,
            avg_menus   = round(float(avg_menus), 1) if avg_menus else None,
            avg_comidas = round(float(avg_comidas), 1) if avg_comidas else None,
        )