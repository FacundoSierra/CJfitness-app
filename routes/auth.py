from flask import render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets


def init_app(app):
    from models import db, Usuario, PasswordResetToken
    from utils import log_activity, log_error, handle_db_error, login_required
    from forms import LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm

    @app.route('/register', methods=['GET', 'POST'])
    @handle_db_error
    def register():
        form = RegisterForm()

        if form.validate_on_submit():
            try:
                nuevo_usuario = Usuario(
                    username=form.username.data,
                    email=form.email.data,
                    password=generate_password_hash(form.password.data, method='pbkdf2:sha256'),
                    nombre=form.nombre.data,
                    apellidos=form.apellidos.data,
                    telefono=form.telefono.data,
                    fecha_nacimiento=form.fecha_nacimiento.data,
                    genero=form.genero.data,
                    direccion=form.direccion.data,
                    ciudad=form.ciudad.data,
                    codigo_postal=form.codigo_postal.data,
                    rol='usuario'
                )
                db.session.add(nuevo_usuario)
                db.session.commit()

                # Log de actividad
                log_activity("Usuario registrado", nuevo_usuario.id, f"Username: {form.username.data}")

                flash("¡Registro exitoso! Ahora puedes iniciar sesión.", "success")
                return redirect(url_for('login'))

            except Exception as e:
                db.session.rollback()
                log_error(e, "Error en registro de usuario")
                flash("Error en el registro. Intenta de nuevo.", "danger")

        return render_template('register.html', form=form)

    @app.route('/login', methods=['GET', 'POST'])
    @handle_db_error
    def login():
        form = LoginForm()

        if form.validate_on_submit():
            try:
                identifier = form.username.data
                password = form.password.data

                user = Usuario.query.filter(
                    (Usuario.username == identifier) | (Usuario.email == identifier)
                ).first()

                if user and check_password_hash(user.password, password):
                    session['user_id'] = user.id
                    session['role'] = user.rol
                    session['username'] = user.nombre

                    # Log de actividad
                    log_activity("Usuario logueado", user.id, f"Username: {user.username}")

                    flash("Bienvenido/a de nuevo.", "success")

                    if user.rol == 'admin':
                        return redirect(url_for('admin_dashboard'))
                    else:
                        return redirect(url_for('dashboard'))
                else:
                    flash("Usuario o contraseña incorrectos. Intenta de nuevo.", "danger")

            except Exception as e:
                log_error(e, "Error en login")
                flash("Error en el inicio de sesión. Intenta de nuevo.", "danger")

        return render_template('login.html', form=form)

    @app.route('/logout')
    def logout():
        if 'user_id' in session:
            log_activity("Usuario cerró sesión", session['user_id'])
        session.clear()
        flash("Has cerrado sesión correctamente.", "info")
        return redirect(url_for('index'))

    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        form = ForgotPasswordForm()
        if form.validate_on_submit():
            try:
                user = Usuario.query.filter_by(email=form.email.data.strip().lower()).first()
                if user:
                    # Invalidar tokens anteriores
                    PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({'used': True})
                    db.session.commit()
                    # Crear nuevo token
                    token = secrets.token_urlsafe(32)
                    expires = datetime.utcnow() + timedelta(hours=2)
                    reset_token = PasswordResetToken(
                        user_id=user.id,
                        token=token,
                        expires_at=expires,
                        used=False
                    )
                    db.session.add(reset_token)
                    db.session.commit()
                    log_activity(f"Token de reset generado para usuario {user.id}", user.id)
                # Siempre mostrar el mismo mensaje (no revelar si el email existe)
                flash("Si el email está registrado, recibirás un enlace para restablecer tu contraseña.", "success")
                return redirect(url_for('login'))
            except Exception as e:
                log_error(e, "forgot_password")
                flash("Error al procesar la solicitud. Intenta de nuevo.", "danger")
        return render_template('forgot_password.html', form=form)

    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        try:
            reset = PasswordResetToken.query.filter_by(token=token, used=False).first()
            if not reset or not reset.is_valid():
                flash("El enlace de recuperación es inválido o ha expirado. Solicita uno nuevo.", "danger")
                return redirect(url_for('forgot_password'))
            form = ResetPasswordForm()
            if form.validate_on_submit():
                user = Usuario.query.get(reset.user_id)
                if user:
                    user.password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
                    reset.used = True
                    db.session.commit()
                    log_activity(f"Contraseña restablecida para usuario {user.id}", user.id)
                    flash("Tu contraseña ha sido actualizada. Ya puedes iniciar sesión.", "success")
                    return redirect(url_for('login'))
            return render_template('reset_password.html', form=form, token=token)
        except Exception as e:
            log_error(e, "reset_password")
            flash("Error al restablecer la contraseña. Intenta de nuevo.", "danger")
            return redirect(url_for('forgot_password'))
