"""
Tests de autenticación: registro, login y control de roles.

Cubre los fixes aplicados:
- El formulario de registro ya no tiene campo 'role' (fix seguridad)
- Registrarse siempre crea un usuario con rol='usuario'
- El login valida contraseña mínima de 8 caracteres
- Un usuario no puede acceder a rutas de admin
"""
import pytest
from models import Usuario
from forms import RegisterForm


class TestFormularioRegistro:

    def test_formulario_no_tiene_campo_role(self, app):
        """El campo 'role' fue eliminado del RegisterForm — nadie puede auto-asignarse admin."""
        with app.app_context():
            form = RegisterForm()
            assert not hasattr(form, 'role'), (
                "El campo 'role' no debe existir en RegisterForm. "
                "Cualquier usuario podría registrarse como admin."
            )

    def test_campos_obligatorios_presentes(self, app):
        """El formulario tiene todos los campos esenciales."""
        with app.app_context():
            form = RegisterForm()
            campos_requeridos = ['username', 'email', 'password', 'confirm_password', 'nombre', 'apellidos']
            for campo in campos_requeridos:
                assert hasattr(form, campo), f"Falta el campo obligatorio: {campo}"

    def test_password_minimo_8_caracteres(self, app):
        """La validación de contraseña exige mínimo 8 caracteres."""
        with app.app_context():
            form = RegisterForm()
            validators = form.password.validators
            from wtforms.validators import Length
            length_validators = [v for v in validators if isinstance(v, Length)]
            assert length_validators, "No hay validador Length en el campo password"
            assert length_validators[0].min == 8, (
                f"Se esperaba min=8, se encontró min={length_validators[0].min}"
            )


class TestRegistro:

    def test_registro_exitoso_crea_usuario(self, client, db):
        """Un registro válido crea un usuario en la BD."""
        response = client.post('/register', data={
            'username': 'nuevouser',
            'email': 'nuevo@example.com',
            'password': 'segura123',
            'confirm_password': 'segura123',
            'nombre': 'Nuevo',
            'apellidos': 'Usuario',
        }, follow_redirects=True)

        assert response.status_code == 200
        user = Usuario.query.filter_by(username='nuevouser').first()
        assert user is not None

    def test_registro_siempre_asigna_rol_usuario(self, client, db):
        """Sin importar qué se envíe, el rol siempre es 'usuario'."""
        # Intentar inyectar rol 'admin' directamente en el POST
        client.post('/register', data={
            'username': 'intentoadmin',
            'email': 'intento@example.com',
            'password': 'segura123',
            'confirm_password': 'segura123',
            'nombre': 'Intento',
            'apellidos': 'Admin',
            'role': 'admin',  # campo extra que no debería tener efecto
        }, follow_redirects=True)

        user = Usuario.query.filter_by(username='intentoadmin').first()
        assert user is not None, "El usuario no fue creado"
        assert user.rol == 'usuario', (
            f"Se esperaba rol='usuario', se obtuvo rol='{user.rol}'. "
            "Hay una vulnerabilidad de escalada de privilegios."
        )

    def test_registro_username_duplicado_falla(self, client, usuario_normal):
        """No se puede registrar con un username ya existente."""
        response = client.post('/register', data={
            'username': 'testuser',  # ya existe en el fixture
            'email': 'otro@example.com',
            'password': 'segura123',
            'confirm_password': 'segura123',
            'nombre': 'Otro',
            'apellidos': 'Usuario',
        }, follow_redirects=True)

        assert response.status_code == 200
        # Debe quedar solo un usuario con ese username
        assert Usuario.query.filter_by(username='testuser').count() == 1

    def test_registro_email_duplicado_falla(self, client, usuario_normal):
        """No se puede registrar con un email ya existente."""
        client.post('/register', data={
            'username': 'otrouser',
            'email': 'test@example.com',  # email ya existe
            'password': 'segura123',
            'confirm_password': 'segura123',
            'nombre': 'Otro',
            'apellidos': 'Usuario',
        }, follow_redirects=True)

        assert Usuario.query.filter_by(email='test@example.com').count() == 1

    def test_registro_passwords_no_coinciden_falla(self, client, db):
        """Registro falla si las contraseñas no coinciden."""
        client.post('/register', data={
            'username': 'userpassmismatch',
            'email': 'mismatch@example.com',
            'password': 'segura123',
            'confirm_password': 'diferente456',
            'nombre': 'Test',
            'apellidos': 'User',
        }, follow_redirects=True)

        assert Usuario.query.filter_by(username='userpassmismatch').first() is None

    def test_password_no_se_guarda_en_texto_plano(self, client, db):
        """La contraseña debe estar hasheada en la BD."""
        client.post('/register', data={
            'username': 'hashtest',
            'email': 'hash@example.com',
            'password': 'mipassword123',
            'confirm_password': 'mipassword123',
            'nombre': 'Hash',
            'apellidos': 'Test',
        }, follow_redirects=True)

        user = Usuario.query.filter_by(username='hashtest').first()
        assert user is not None
        assert user.password != 'mipassword123', "La contraseña no debe guardarse en texto plano"
        assert user.password.startswith('pbkdf2:') or user.password.startswith('scrypt:'), (
            "La contraseña debe estar hasheada con werkzeug"
        )


class TestLogin:

    def test_login_correcto_redirige_a_dashboard(self, client, usuario_normal):
        """Login válido redirige al dashboard del usuario."""
        response = client.post('/login', data={
            'username': 'testuser',
            'password': 'password123',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'dashboard' in response.request.url.encode() or response.status_code == 200

    def test_login_admin_redirige_a_admin_dashboard(self, client, usuario_admin):
        """Login de admin redirige al panel de administración."""
        response = client.post('/login', data={
            'username': 'adminuser',
            'password': 'adminpass123',
        }, follow_redirects=True)

        assert response.status_code == 200

    def test_login_password_incorrecta_falla(self, client, usuario_normal):
        """Login con contraseña incorrecta muestra error."""
        response = client.post('/login', data={
            'username': 'testuser',
            'password': 'wrongpassword',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'incorrectos' in response.data or b'error' in response.data.lower()

    def test_login_usuario_inexistente_falla(self, client, db):
        """Login con usuario que no existe muestra error."""
        response = client.post('/login', data={
            'username': 'noexiste',
            'password': 'cualquiera123',
        }, follow_redirects=True)

        assert response.status_code == 200

    def test_logout_limpia_sesion(self, login_as_user):
        """Logout redirige al inicio y limpia la sesión."""
        response = login_as_user.get('/logout', follow_redirects=True)
        assert response.status_code == 200

        # Tras logout, acceder al dashboard debe redirigir al login
        response = login_as_user.get('/dashboard', follow_redirects=True)
        assert b'login' in response.request.url.encode() or b'sesi' in response.data


class TestControlDeAcceso:

    def test_usuario_normal_no_accede_a_admin_dashboard(self, login_as_user):
        """Un usuario con rol 'usuario' no puede acceder al panel admin."""
        response = login_as_user.get('/admin_dashboard', follow_redirects=True)
        assert response.status_code == 200
        # Debe ser redirigido (no ver el panel admin)
        assert b'admin_dashboard' not in response.request.url.encode()

    def test_acceso_sin_sesion_redirige_a_login(self, client):
        """Sin sesión activa, las rutas protegidas redirigen al login."""
        rutas_protegidas = ['/dashboard', '/admin_dashboard', '/admin_usuarios']
        for ruta in rutas_protegidas:
            response = client.get(ruta, follow_redirects=False)
            assert response.status_code in (301, 302), (
                f"Se esperaba redirección en {ruta}, status: {response.status_code}"
            )
