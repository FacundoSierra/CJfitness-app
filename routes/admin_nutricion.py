import logging
from flask import render_template, session
from datetime import date


def init_app(app):
    from models import db, Usuario, PerfilNutricional, RecomendacionDiaria
    from utils import handle_db_error, admin_required

    logger = logging.getLogger('fitness_app')

    @app.route('/admin_nutricion')
    @admin_required
    @handle_db_error
    def admin_nutricion():
        usuarios = Usuario.query.filter(Usuario.rol != 'admin').order_by(Usuario.nombre).all()
        hoy = date.today()

        # Pre-cargar perfiles y recomendaciones en 2 queries (en vez de 2×N)
        ids = [u.id for u in usuarios]
        perfiles = {
            p.usuario_id: p
            for p in PerfilNutricional.query.filter(PerfilNutricional.usuario_id.in_(ids)).all()
        }
        recs = {}
        for r in (
            RecomendacionDiaria.query
            .filter(RecomendacionDiaria.usuario_id.in_(ids))
            .order_by(RecomendacionDiaria.fecha.desc())
            .all()
        ):
            recs.setdefault(r.usuario_id, r)  # conserva solo la más reciente por usuario

        datos = []
        for u in usuarios:
            rec = recs.get(u.id)
            datos.append({
                'usuario': u,
                'perfil':  perfiles.get(u.id),
                'rec':     rec,
                'es_hoy':  rec.fecha == hoy if rec else False,
            })

        return render_template('admin_nutricion.html',
                               datos=datos,
                               hoy=hoy,
                               username=session.get('username'),
                               active_page='nutricion')
