import logging
from flask import render_template, request, redirect, url_for, session, flash, jsonify

logger = logging.getLogger('fitness_app')


def init_app(app):
    from models import (db, BloqueTaxonomia, CategoriaTaxonomia, SubcategoriaTaxonomia,
                        CaracteristicaTipo, CaracteristicaValor, EjercicioCompleto)
    from utils import handle_db_error, admin_required

    # ── TAXONOMÍA — vistas HTML ───────────────────────────────────────────────

    @app.route('/admin/taxonomia')
    @admin_required
    @handle_db_error
    def admin_taxonomia():
        bloques = BloqueTaxonomia.query.order_by(BloqueTaxonomia.orden).all()
        return render_template('admin_taxonomia.html',
                               bloques=bloques,
                               username=session.get('username'),
                               active_page='taxonomia')

    @app.route('/admin/taxonomia/bloque', methods=['POST'])
    @admin_required
    def tax_nuevo_bloque():
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash('El nombre del bloque no puede estar vacío.', 'danger')
            return redirect(url_for('admin_taxonomia'))
        if BloqueTaxonomia.query.filter_by(nombre=nombre).first():
            flash(f'Ya existe un bloque llamado "{nombre}".', 'warning')
            return redirect(url_for('admin_taxonomia'))
        try:
            orden = BloqueTaxonomia.query.count()
            db.session.add(BloqueTaxonomia(nombre=nombre, orden=orden))
            db.session.commit()
            flash(f'Bloque "{nombre}" creado.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'tax_nuevo_bloque: {e}')
            flash('Error al crear el bloque.', 'danger')
        return redirect(url_for('admin_taxonomia'))

    @app.route('/admin/taxonomia/bloque/<int:bloque_id>/editar', methods=['POST'])
    @admin_required
    def tax_editar_bloque(bloque_id):
        bloque = db.get_or_404(BloqueTaxonomia, bloque_id)
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash('El nombre no puede estar vacío.', 'danger')
            return redirect(url_for('admin_taxonomia'))
        try:
            bloque.nombre = nombre
            db.session.commit()
            flash('Bloque actualizado.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'tax_editar_bloque: {e}')
            flash('Error al actualizar.', 'danger')
        return redirect(url_for('admin_taxonomia'))

    @app.route('/admin/taxonomia/categoria', methods=['POST'])
    @admin_required
    def tax_nueva_categoria():
        bloque_id = request.form.get('bloque_id', type=int)
        nombre    = request.form.get('nombre', '').strip()
        if not bloque_id or not nombre:
            flash('Datos incompletos.', 'danger')
            return redirect(url_for('admin_taxonomia'))
        try:
            orden = CategoriaTaxonomia.query.filter_by(bloque_id=bloque_id).count()
            db.session.add(CategoriaTaxonomia(bloque_id=bloque_id, nombre=nombre, orden=orden))
            db.session.commit()
            flash(f'Categoría "{nombre}" creada.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'tax_nueva_categoria: {e}')
            flash('Error al crear la categoría.', 'danger')
        return redirect(url_for('admin_taxonomia'))

    @app.route('/admin/taxonomia/categoria/<int:cat_id>/editar', methods=['POST'])
    @admin_required
    def tax_editar_categoria(cat_id):
        cat    = db.get_or_404(CategoriaTaxonomia, cat_id)
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash('El nombre no puede estar vacío.', 'danger')
            return redirect(url_for('admin_taxonomia'))
        try:
            cat.nombre = nombre
            db.session.commit()
            flash('Categoría actualizada.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'tax_editar_categoria: {e}')
            flash('Error al actualizar.', 'danger')
        return redirect(url_for('admin_taxonomia'))

    @app.route('/admin/taxonomia/subcategoria', methods=['POST'])
    @admin_required
    def tax_nueva_subcategoria():
        cat_id = request.form.get('categoria_id', type=int)
        nombre = request.form.get('nombre', '').strip()
        if not cat_id or not nombre:
            flash('Datos incompletos.', 'danger')
            return redirect(url_for('admin_taxonomia'))
        try:
            orden = SubcategoriaTaxonomia.query.filter_by(categoria_id=cat_id).count()
            db.session.add(SubcategoriaTaxonomia(categoria_id=cat_id, nombre=nombre, orden=orden))
            db.session.commit()
            flash(f'Subcategoría "{nombre}" creada.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'tax_nueva_subcategoria: {e}')
            flash('Error al crear la subcategoría.', 'danger')
        return redirect(url_for('admin_taxonomia'))

    @app.route('/admin/taxonomia/subcategoria/<int:sub_id>/editar', methods=['POST'])
    @admin_required
    def tax_editar_subcategoria(sub_id):
        sub    = db.get_or_404(SubcategoriaTaxonomia, sub_id)
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash('El nombre no puede estar vacío.', 'danger')
            return redirect(url_for('admin_taxonomia'))
        try:
            sub.nombre = nombre
            db.session.commit()
            flash('Subcategoría actualizada.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'tax_editar_subcategoria: {e}')
            flash('Error al actualizar.', 'danger')
        return redirect(url_for('admin_taxonomia'))

    @app.route('/admin/taxonomia/caracteristica/tipo', methods=['POST'])
    @admin_required
    def tax_nuevo_tipo():
        bloque_id = request.form.get('bloque_id', type=int)
        nombre    = request.form.get('nombre', '').strip()
        if not bloque_id or not nombre:
            flash('Datos incompletos.', 'danger')
            return redirect(url_for('admin_taxonomia'))
        try:
            db.session.add(CaracteristicaTipo(bloque_id=bloque_id, nombre=nombre))
            db.session.commit()
            flash(f'Tipo de característica "{nombre}" creado.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'tax_nuevo_tipo: {e}')
            flash('Error al crear el tipo.', 'danger')
        return redirect(url_for('admin_taxonomia'))

    @app.route('/admin/taxonomia/caracteristica/valor', methods=['POST'])
    @admin_required
    def tax_nuevo_valor():
        tipo_id = request.form.get('tipo_id', type=int)
        nombre  = request.form.get('nombre', '').strip()
        if not tipo_id or not nombre:
            flash('Datos incompletos.', 'danger')
            return redirect(url_for('admin_taxonomia'))
        try:
            orden = CaracteristicaValor.query.filter_by(tipo_id=tipo_id).count()
            db.session.add(CaracteristicaValor(tipo_id=tipo_id, nombre=nombre, orden=orden))
            db.session.commit()
            flash(f'Valor "{nombre}" añadido.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'tax_nuevo_valor: {e}')
            flash('Error al añadir el valor.', 'danger')
        return redirect(url_for('admin_taxonomia'))

    @app.route('/admin/taxonomia/caracteristica/valor/<int:val_id>/editar', methods=['POST'])
    @admin_required
    def tax_editar_valor(val_id):
        val    = db.get_or_404(CaracteristicaValor, val_id)
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash('El nombre no puede estar vacío.', 'danger')
            return redirect(url_for('admin_taxonomia'))
        try:
            val.nombre = nombre
            db.session.commit()
            flash('Valor actualizado.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'tax_editar_valor: {e}')
            flash('Error al actualizar.', 'danger')
        return redirect(url_for('admin_taxonomia'))

    # ── EJERCICIOS — vistas HTML ──────────────────────────────────────────────

    @app.route('/admin/ejercicios2')
    @admin_required
    @handle_db_error
    def admin_ejercicios2():
        bloque_id = request.args.get('bloque_id', type=int)
        cat_id    = request.args.get('categoria_id', type=int)
        q         = request.args.get('q', '').strip()

        query = EjercicioCompleto.query
        if bloque_id:
            query = query.filter_by(bloque_id=bloque_id)
        if cat_id:
            query = query.filter_by(categoria_id=cat_id)
        if q:
            query = query.filter(EjercicioCompleto.nombre.ilike(f'%{q}%'))

        ejercicios = query.order_by(EjercicioCompleto.nombre).all()
        bloques    = BloqueTaxonomia.query.filter_by(activo=True).order_by(BloqueTaxonomia.orden).all()
        categorias = (CategoriaTaxonomia.query.filter_by(bloque_id=bloque_id).order_by(CategoriaTaxonomia.orden).all()
                      if bloque_id else [])

        return render_template('admin_ejercicios2.html',
                               ejercicios=ejercicios,
                               bloques=bloques,
                               categorias=categorias,
                               bloque_id=bloque_id,
                               categoria_id=cat_id,
                               q=q,
                               username=session.get('username'),
                               active_page='ejercicios2')

    @app.route('/admin/ejercicios2/nuevo', methods=['GET'])
    @admin_required
    @handle_db_error
    def ejercicio_nuevo_form():
        bloques = BloqueTaxonomia.query.filter_by(activo=True).order_by(BloqueTaxonomia.orden).all()
        return render_template('admin_ejercicio_nuevo.html',
                               bloques=bloques,
                               ejercicio=None,
                               username=session.get('username'),
                               active_page='ejercicios2')

    @app.route('/admin/ejercicios2/nuevo', methods=['POST'])
    @admin_required
    @handle_db_error
    def ejercicio_nuevo_post():
        nombre        = request.form.get('nombre', '').strip()
        bloque_id     = request.form.get('bloque_id', type=int)
        categoria_id  = request.form.get('categoria_id', type=int) or None
        subcategoria_id = request.form.get('subcategoria_id', type=int) or None
        material      = request.form.get('material', '').strip() or None
        otras         = request.form.get('otras_caracteristicas', '').strip() or None

        if not nombre or not bloque_id:
            flash('El nombre y el bloque son obligatorios.', 'danger')
            return redirect(url_for('ejercicio_nuevo_form'))

        # Recoger características dinámicas
        import json
        caracteristicas = {}
        for key, value in request.form.items():
            if key.startswith('caracteristica_') and value.strip():
                tipo_nombre = key[len('caracteristica_'):]
                caracteristicas[tipo_nombre] = value.strip()

        ejercicio = EjercicioCompleto(
            nombre=nombre,
            bloque_id=bloque_id,
            categoria_id=categoria_id,
            subcategoria_id=subcategoria_id,
            caracteristicas_json=caracteristicas or None,
            material=material,
            otras_caracteristicas=otras,
        )
        db.session.add(ejercicio)
        db.session.commit()
        flash(f'Ejercicio "{nombre}" creado correctamente.', 'success')
        return redirect(url_for('admin_ejercicios2'))

    @app.route('/admin/ejercicios2/nuevo-masivo', methods=['POST'])
    @admin_required
    @handle_db_error
    def ejercicio_nuevo_masivo():
        bloque_id       = request.form.get('bloque_id', type=int)
        categoria_id    = request.form.get('categoria_id', type=int) or None
        subcategoria_id = request.form.get('subcategoria_id', type=int) or None
        otras           = request.form.get('otras_caracteristicas', '').strip() or None

        if not bloque_id:
            flash('El bloque es obligatorio.', 'danger')
            return redirect(url_for('ejercicio_nuevo_form'))

        # Características dinámicas (mismo patrón que ejercicio_nuevo_post)
        caracteristicas = {}
        for key, value in request.form.items():
            if key.startswith('caracteristica_') and value.strip():
                tipo_nombre = key[len('caracteristica_'):]
                caracteristicas[tipo_nombre] = value.strip()

        nombres    = request.form.getlist('nombres[]')
        materiales = request.form.getlist('materiales[]')

        creados = 0
        for i, nombre in enumerate(nombres):
            nombre = nombre.strip()
            if not nombre:
                continue
            material = (materiales[i].strip() if i < len(materiales) else '') or None
            ej = EjercicioCompleto(
                nombre=nombre,
                bloque_id=bloque_id,
                categoria_id=categoria_id,
                subcategoria_id=subcategoria_id,
                caracteristicas_json=caracteristicas or None,
                material=material,
                otras_caracteristicas=otras,
                activo=True
            )
            db.session.add(ej)
            creados += 1

        db.session.commit()
        flash(f'✅ {creados} ejercicio{"s" if creados != 1 else ""} creado{"s" if creados != 1 else ""} correctamente.', 'success')
        return redirect(url_for('admin_ejercicios2'))

    @app.route('/admin/ejercicios2/<int:ej_id>/editar', methods=['GET'])
    @admin_required
    @handle_db_error
    def ejercicio_editar_form(ej_id):
        ejercicio = db.get_or_404(EjercicioCompleto, ej_id)
        bloques   = BloqueTaxonomia.query.filter_by(activo=True).order_by(BloqueTaxonomia.orden).all()
        return render_template('admin_ejercicio_nuevo.html',
                               bloques=bloques,
                               ejercicio=ejercicio,
                               username=session.get('username'),
                               active_page='ejercicios2')

    @app.route('/admin/ejercicios2/<int:ej_id>/editar', methods=['POST'])
    @admin_required
    @handle_db_error
    def ejercicio_editar_post(ej_id):
        ejercicio = db.get_or_404(EjercicioCompleto, ej_id)
        nombre    = request.form.get('nombre', '').strip()
        bloque_id = request.form.get('bloque_id', type=int)

        if not nombre or not bloque_id:
            flash('El nombre y el bloque son obligatorios.', 'danger')
            return redirect(url_for('ejercicio_editar_form', ej_id=ej_id))

        caracteristicas = {}
        for key, value in request.form.items():
            if key.startswith('caracteristica_') and value.strip():
                tipo_nombre = key[len('caracteristica_'):]
                caracteristicas[tipo_nombre] = value.strip()

        ejercicio.nombre          = nombre
        ejercicio.bloque_id       = bloque_id
        ejercicio.categoria_id    = request.form.get('categoria_id', type=int) or None
        ejercicio.subcategoria_id = request.form.get('subcategoria_id', type=int) or None
        ejercicio.material        = request.form.get('material', '').strip() or None
        ejercicio.otras_caracteristicas = request.form.get('otras_caracteristicas', '').strip() or None
        ejercicio.caracteristicas_json  = caracteristicas or None
        db.session.commit()
        flash(f'Ejercicio "{nombre}" actualizado.', 'success')
        return redirect(url_for('admin_ejercicios2'))

    @app.route('/admin/ejercicios2/<int:ej_id>/desactivar', methods=['POST'])
    @admin_required
    def ejercicio_desactivar(ej_id):
        ejercicio = db.get_or_404(EjercicioCompleto, ej_id)
        try:
            ejercicio.activo = not ejercicio.activo
            db.session.commit()
            estado = 'activado' if ejercicio.activo else 'desactivado'
            flash(f'Ejercicio "{ejercicio.nombre}" {estado}.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'ejercicio_desactivar: {e}')
            flash('Error al cambiar el estado.', 'danger')
        return redirect(url_for('admin_ejercicios2'))

    # ── API JSON — cascada del formulario ────────────────────────────────────

    @app.route('/api/ejercicios/categorias')
    @admin_required
    def api_ej_categorias():
        bloque_id = request.args.get('bloque_id', type=int)
        if not bloque_id:
            return jsonify([])
        cats = (CategoriaTaxonomia.query
                .filter_by(bloque_id=bloque_id, activo=True)
                .order_by(CategoriaTaxonomia.orden).all())
        return jsonify([{'id': c.id, 'nombre': c.nombre} for c in cats])

    @app.route('/api/ejercicios/subcategorias')
    @admin_required
    def api_ej_subcategorias():
        cat_id = request.args.get('categoria_id', type=int)
        if not cat_id:
            return jsonify([])
        subs = (SubcategoriaTaxonomia.query
                .filter_by(categoria_id=cat_id, activo=True)
                .order_by(SubcategoriaTaxonomia.orden).all())
        return jsonify([{'id': s.id, 'nombre': s.nombre} for s in subs])

    @app.route('/api/ejercicios/caracteristicas')
    @admin_required
    def api_ej_caracteristicas():
        bloque_id = request.args.get('bloque_id', type=int)
        if not bloque_id:
            return jsonify([])
        tipos = (CaracteristicaTipo.query
                 .filter_by(bloque_id=bloque_id, activo=True).all())
        return jsonify([{
            'id':     t.id,
            'nombre': t.nombre,
            'valores': [{'id': v.id, 'nombre': v.nombre}
                        for v in t.valores if v.activo]
        } for t in tipos])

    @app.route('/api/ejercicios/categoria/nueva', methods=['POST'])
    @admin_required
    def api_ej_nueva_categoria():
        data      = request.get_json(silent=True) or {}
        bloque_id = data.get('bloque_id')
        nombre    = (data.get('nombre') or '').strip()
        if not bloque_id or not nombre:
            return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
        try:
            orden = CategoriaTaxonomia.query.filter_by(bloque_id=bloque_id).count()
            cat   = CategoriaTaxonomia(bloque_id=bloque_id, nombre=nombre, orden=orden)
            db.session.add(cat)
            db.session.commit()
            return jsonify({'success': True, 'id': cat.id, 'nombre': cat.nombre})
        except Exception as e:
            db.session.rollback()
            logger.error(f'api_ej_nueva_categoria: {e}')
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.route('/api/ejercicios/subcategoria/nueva', methods=['POST'])
    @admin_required
    def api_ej_nueva_subcategoria():
        data   = request.get_json(silent=True) or {}
        cat_id = data.get('categoria_id')
        nombre = (data.get('nombre') or '').strip()
        if not cat_id or not nombre:
            return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
        try:
            orden = SubcategoriaTaxonomia.query.filter_by(categoria_id=cat_id).count()
            sub   = SubcategoriaTaxonomia(categoria_id=cat_id, nombre=nombre, orden=orden)
            db.session.add(sub)
            db.session.commit()
            return jsonify({'success': True, 'id': sub.id, 'nombre': sub.nombre})
        except Exception as e:
            db.session.rollback()
            logger.error(f'api_ej_nueva_subcategoria: {e}')
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.route('/api/ejercicios/caracteristica/valor/nuevo', methods=['POST'])
    @admin_required
    def api_ej_nuevo_valor():
        data    = request.get_json(silent=True) or {}
        tipo_id = data.get('tipo_id')
        nombre  = (data.get('nombre') or '').strip()
        if not tipo_id or not nombre:
            return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
        try:
            orden = CaracteristicaValor.query.filter_by(tipo_id=tipo_id).count()
            val   = CaracteristicaValor(tipo_id=tipo_id, nombre=nombre, orden=orden)
            db.session.add(val)
            db.session.commit()
            return jsonify({'success': True, 'id': val.id, 'nombre': val.nombre})
        except Exception as e:
            db.session.rollback()
            logger.error(f'api_ej_nuevo_valor: {e}')
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
