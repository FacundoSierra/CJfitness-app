import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def _build_db_uri():
    """
    Normaliza DATABASE_URL para que funcione con SQLAlchemy.
    - Convierte postgres:// → postgresql:// (legacy Heroku/Render format)
    - Añade ?sslmode=require si es Supabase (pooler o conexión directa)
    """
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        return url
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url

class Config:
    # Configuración básica
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')

    # Base de datos
    SQLALCHEMY_DATABASE_URI = _build_db_uri()

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        # SSL requerido para Supabase — no afecta a SQLite ni a PostgreSQL local sin SSL
        'connect_args': {'sslmode': 'require'} if os.environ.get('DB_SSL', 'false').lower() == 'true' else {},
    }
    
    # Configuración de sesión
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = int(os.environ.get('PERMANENT_SESSION_LIFETIME', 3600))
    
    # Configuración de logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/fitness_app.log')
    
    # Configuración de la aplicación
    APP_NAME = os.environ.get('APP_NAME', 'Fitness App')
    APP_VERSION = os.environ.get('APP_VERSION', '2.0.0')
    APP_DEBUG = os.environ.get('APP_DEBUG', 'True').lower() == 'true'

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    SESSION_COOKIE_SECURE = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuración por defecto
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
