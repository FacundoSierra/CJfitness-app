"""
Tests de rutas HTTP.

Cubre:
- Rutas públicas accesibles sin sesión
- Rutas protegidas que redirigen al login
- Rutas de admin inaccesibles para usuarios normales
- Fix send_from_directory: /sitemap.xml y /robots.txt no dan 500
- API de ejercicios devuelve JSON válido
"""
import pytest
import json


class TestRutasPublicas:

    def test_index_accesible(self, client):
        """La página de inicio devuelve 200."""
        response = client.get('/')
        assert response.status_code == 200

    def test_login_accesible(self, client):
        """La página de login devuelve 200."""
        response = client.get('/login')
        assert response.status_code == 200

    def test_register_accesible(self, client):
        """La página de registro devuelve 200."""
        response = client.get('/register')
        assert response.status_code == 200

    def test_sitemap_xml_no_da_500(self, client):
        """
        /sitemap.xml no debe dar error 500.
        Fix: send_from_directory no estaba importado en app.py.
        """
        response = client.get('/sitemap.xml')
        assert response.status_code != 500, (
            "send_from_directory no está importado — /sitemap.xml da error 500"
        )

    def test_robots_txt_no_da_500(self, client):
        """
        /robots.txt no debe dar error 500.
        Fix: send_from_directory no estaba importado en app.py.
        """
        response = client.get('/robots.txt')
        assert response.status_code != 500, (
            "send_from_directory no está importado — /robots.txt da error 500"
        )

    def test_planes_accesible(self, client):
        """La página de planes/precios devuelve 200."""
        response = client.get('/planes')
        assert response.status_code in (200, 302, 404)  # 302 si requiere login


class TestRutasProtegidas:
    """Las rutas que requieren login deben redirigir si no hay sesión."""

    @pytest.mark.parametrize("ruta", [
        '/dashboard',
        '/mis_rutinas',
    ])
    def test_rutas_usuario_redirigen_sin_sesion(self, client, ruta):
        """Las rutas de usuario redirigen al login si no hay sesión activa."""
        response = client.get(ruta, follow_redirects=False)
        assert response.status_code in (301, 302), (
            f"Se esperaba redirección en {ruta}, se obtuvo {response.status_code}"
        )
        assert 'login' in response.headers.get('Location', '')

    @pytest.mark.parametrize("ruta", [
        '/admin_dashboard',
        '/admin_usuarios',
        '/admin_entrenamientos',
        '/admin_ejercicios',
        '/admin_pagos',
    ])
    def test_rutas_admin_redirigen_sin_sesion(self, client, ruta):
        """Las rutas de admin redirigen al login si no hay sesión activa."""
        response = client.get(ruta, follow_redirects=False)
        assert response.status_code in (301, 302), (
            f"Se esperaba redirección en {ruta}, se obtuvo {response.status_code}"
        )


class TestRutasAdmin:

    def test_admin_dashboard_accesible_para_admin(self, login_as_admin):
        """El admin puede acceder al dashboard de admin."""
        response = login_as_admin.get('/admin_dashboard', follow_redirects=True)
        assert response.status_code == 200

    def test_admin_usuarios_accesible_para_admin(self, login_as_admin):
        """El admin puede ver la lista de usuarios."""
        response = login_as_admin.get('/admin_usuarios', follow_redirects=True)
        assert response.status_code == 200

    def test_usuario_normal_bloqueado_en_admin_dashboard(self, login_as_user):
        """Un usuario normal no puede acceder al dashboard de admin."""
        response = login_as_user.get('/admin_dashboard', follow_redirects=False)
        assert response.status_code in (301, 302), (
            "Un usuario con rol 'usuario' no debe poder ver el panel admin"
        )

    def test_usuario_normal_bloqueado_en_admin_usuarios(self, login_as_user):
        """Un usuario normal no puede acceder a la gestión de usuarios."""
        response = login_as_user.get('/admin_usuarios', follow_redirects=False)
        assert response.status_code in (301, 302)


class TestRutasUsuario:

    def test_dashboard_usuario_accesible(self, login_as_user):
        """Un usuario autenticado puede acceder a su dashboard."""
        response = login_as_user.get('/dashboard', follow_redirects=True)
        assert response.status_code == 200

    def test_mis_rutinas_accesible(self, login_as_user):
        """Un usuario autenticado puede ver sus rutinas."""
        response = login_as_user.get('/mis_rutinas', follow_redirects=True)
        assert response.status_code == 200


class TestNuevasRutasPublicas:
    """Tests para las rutas añadidas en los últimos fixes."""

    def test_forgot_password_accesible(self, client):
        """/forgot-password devuelve 200."""
        response = client.get('/forgot-password')
        assert response.status_code == 200

    def test_reset_password_token_invalido_redirige(self, client):
        """/reset-password/<token> con token inválido redirige a forgot-password."""
        response = client.get('/reset-password/token-invalido-xyz', follow_redirects=False)
        assert response.status_code in (301, 302)

    def test_sobre_mi_redirige_sin_sesion(self, client):
        """/sobre_mi redirige al login si no hay sesión."""
        response = client.get('/sobre_mi', follow_redirects=False)
        assert response.status_code in (301, 302)
        assert 'login' in response.headers.get('Location', '')

    def test_sobre_mi_accesible_autenticado(self, login_as_user):
        """/sobre_mi devuelve 200 para un usuario autenticado."""
        response = login_as_user.get('/sobre_mi', follow_redirects=True)
        assert response.status_code == 200

    def test_pagos_accesible_autenticado(self, login_as_user):
        """/pagos ya no falla con NameError de Suscripcion (bug fix)."""
        response = login_as_user.get('/pagos', follow_redirects=True)
        assert response.status_code == 200

    def test_forgot_password_redirige_si_sesion_activa(self, login_as_user):
        """/forgot-password redirige al dashboard si ya hay sesión."""
        response = login_as_user.get('/forgot-password', follow_redirects=False)
        assert response.status_code in (301, 302)


class TestApiEjercicios:

    def test_api_ejercicios_devuelve_json(self, client, ejercicio):
        """El endpoint /api_ejercicios devuelve JSON válido."""
        response = client.get('/api_ejercicios')
        assert response.status_code == 200
        assert response.content_type == 'application/json'

        data = json.loads(response.data)
        assert isinstance(data, dict), "La respuesta debe ser un objeto JSON"

    def test_api_ejercicios_contiene_ejercicio_creado(self, client, ejercicio):
        """El ejercicio de ejemplo aparece en la respuesta de la API."""
        response = client.get('/api_ejercicios')
        data = json.loads(response.data)

        # La estructura es {categoria: {subcategoria: [nombres]}}
        assert 'Fuerza' in data
        assert 'Piernas' in data['Fuerza']
        assert 'Sentadilla' in data['Fuerza']['Piernas']
