"""
Configuración compartida de pytest.
Crea una app en modo testing con SQLite en memoria para cada test.
"""
import os
import pytest

# Forzar entorno de testing ANTES de importar la app
os.environ['FLASK_ENV'] = 'testing'

from app import app as flask_app
from models import db as _db
from models import Usuario, Ejercicio, Rutina, Bloque, EjercicioAsignado
from werkzeug.security import generate_password_hash


@pytest.fixture(scope='session')
def app():
    """App compartida para toda la sesión de tests."""
    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'test-secret-key',
    })

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture(scope='function')
def db(app):
    """Transacción limpia por cada test — hace rollback al terminar."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()

        # Bind la sesión a la conexión con transacción abierta
        _db.session.bind = connection

        yield _db

        _db.session.remove()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope='function')
def client(app):
    """Cliente HTTP de Flask para tests."""
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """CLI runner de Flask."""
    return app.test_cli_runner()


# ---------- Factories de datos ----------

@pytest.fixture
def usuario_normal(db):
    """Crea un usuario con rol 'usuario' para tests."""
    user = Usuario(
        username='testuser',
        email='test@example.com',
        password=generate_password_hash('password123'),
        nombre='Test',
        apellidos='User',
        rol='usuario',
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def usuario_admin(db):
    """Crea un usuario con rol 'admin' para tests."""
    admin = Usuario(
        username='adminuser',
        email='admin@example.com',
        password=generate_password_hash('adminpass123'),
        nombre='Admin',
        apellidos='User',
        rol='admin',
    )
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def ejercicio(db):
    """Crea un ejercicio de ejemplo."""
    ej = Ejercicio(
        nombre='Sentadilla',
        categoria='Fuerza',
        subcategoria='Piernas',
    )
    db.session.add(ej)
    db.session.commit()
    return ej


@pytest.fixture
def login_as_admin(client, usuario_admin):
    """Inicia sesión como admin y devuelve el cliente autenticado."""
    client.post('/login', data={
        'username': 'adminuser',
        'password': 'adminpass123',
    }, follow_redirects=True)
    return client


@pytest.fixture
def login_as_user(client, usuario_normal):
    """Inicia sesión como usuario normal y devuelve el cliente autenticado."""
    client.post('/login', data={
        'username': 'testuser',
        'password': 'password123',
    }, follow_redirects=True)
    return client
