from flask import Flask, render_template, send_from_directory
import os

# Crear aplicación Flask
app = Flask(__name__)

# Configuración
from config import config
config_name = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[config_name])

# Validar SECRET_KEY en producción
if config_name == 'production' and not os.environ.get('SECRET_KEY'):
    raise RuntimeError(
        "SECRET_KEY must be set as an environment variable in production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

# Inicializar base de datos
from models import db
db.init_app(app)

# Importar modelos después de inicializar db
from models import Usuario, Ejercicio, Rutina, Bloque, EjercicioAsignado, Plan, Pago, ConfiguracionPagoMensual, SeguimientoEjercicio, PasswordResetToken, FeedbackSesion

# Importar payment service
from payment_service import payment_service

# Configurar logging
from utils import setup_logging, log_activity, log_error, handle_db_error, admin_required, login_required
logger = setup_logging(app)

# ------------------ RUTAS ESTÁTICAS ------------------

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(app.static_folder, 'sitemap.xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route('/')
def index():
    return render_template('index.html')

# ------------------ AUTO-MIGRACIÓN DE BD ------------------
# Crea tablas nuevas y añade columnas si no existen (nunca borra datos)
with app.app_context():
    db.create_all()  # crea tablas nuevas (feedback_sesiones, etc.) sin tocar las existentes
    try:
        from sqlalchemy import text
        with db.engine.connect() as _conn:
            _conn.execute(text(
                "ALTER TABLE ejercicios_asignados ADD COLUMN series_json TEXT"
            ))
            _conn.commit()
    except Exception:
        pass  # La columna ya existe

# ------------------ REGISTRAR MÓDULOS DE RUTAS ------------------

from routes import auth, admin, usuario, api
auth.init_app(app)
admin.init_app(app)
usuario.init_app(app)
api.init_app(app)

# ------------------ MAIN ------------------

if __name__ == '__main__':
    app.run(debug=True)