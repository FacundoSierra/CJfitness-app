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

        datos = []
        for u in usuarios:
            perfil = PerfilNutricional.query.filter_by(usuario_id=u.id).first()
            rec = (
                RecomendacionDiaria.query
                .filter_by(usuario_id=u.id)
                .order_by(RecomendacionDiaria.fecha.desc())
                .first()
            )
            datos.append({
                'usuario': u,
                'perfil':  perfil,
                'rec':     rec,
                'es_hoy':  rec.fecha == hoy if rec else False,
            })

        return render_template('admin_nutricion.html',
                               datos=datos,
                               hoy=hoy,
                               username=session.get('username'),
                               active_page='nutricion')
