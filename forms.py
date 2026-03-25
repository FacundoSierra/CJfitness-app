from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, SelectField, TextAreaField, DateField, DecimalField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange, ValidationError
from models import Usuario

class LoginForm(FlaskForm):
    """Formulario de login con validación"""
    username = StringField('Usuario o Email', validators=[
        DataRequired(message='El campo es obligatorio'),
        Length(min=3, max=50, message='El usuario debe tener entre 3 y 50 caracteres')
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message='La contraseña es obligatoria'),
        Length(min=8, message='La contraseña debe tener al menos 8 caracteres')
    ])
    submit = SubmitField('Iniciar Sesión')

class RegisterForm(FlaskForm):
    """Formulario de registro con validación completa"""
    username = StringField('Nombre de Usuario', validators=[
        DataRequired(message='El nombre de usuario es obligatorio'),
        Length(min=3, max=50, message='El usuario debe tener entre 3 y 50 caracteres')
    ])
    email = EmailField('Email', validators=[
        DataRequired(message='El email es obligatorio'),
        Email(message='Formato de email inválido'),
        Length(max=120, message='El email no puede exceder 120 caracteres')
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message='La contraseña es obligatoria'),
        Length(min=8, message='La contraseña debe tener al menos 8 caracteres')
    ])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[
        DataRequired(message='Debes confirmar la contraseña'),
        EqualTo('password', message='Las contraseñas no coinciden')
    ])
    nombre = StringField('Nombre', validators=[
        DataRequired(message='El nombre es obligatorio'),
        Length(min=2, max=100, message='El nombre debe tener entre 2 y 100 caracteres')
    ])
    apellidos = StringField('Apellidos', validators=[
        DataRequired(message='Los apellidos son obligatorios'),
        Length(min=2, max=150, message='Los apellidos deben tener entre 2 y 150 caracteres')
    ])
    telefono = StringField('Teléfono', validators=[
        Optional(),
        Length(max=20, message='El teléfono no puede exceder 20 caracteres')
    ])
    fecha_nacimiento = DateField('Fecha de Nacimiento', validators=[Optional()])
    genero = SelectField('Género', choices=[('', 'Seleccionar...'), ('masculino','Masculino'), ('femenino','Femenino'), ('otro','Otro')], validators=[Optional()])
    direccion = StringField('Dirección', validators=[Optional(), Length(max=255)])
    ciudad = StringField('Ciudad', validators=[Optional(), Length(max=100)])
    codigo_postal = StringField('Código Postal', validators=[Optional(), Length(max=20)])
    submit = SubmitField('Registrarse')

    def validate_username(self, username):
        """Validar que el username no exista"""
        user = Usuario.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Este nombre de usuario ya está en uso. Elige otro.')

    def validate_email(self, email):
        """Validar que el email no exista"""
        user = Usuario.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Este email ya está registrado. Usa otro o inicia sesión.')

class EjercicioForm(FlaskForm):
    """Formulario para crear/editar ejercicios"""
    nombre = StringField('Nombre del Ejercicio', validators=[
        DataRequired(message='El nombre del ejercicio es obligatorio'),
        Length(min=3, max=300, message='El nombre debe tener entre 3 y 300 caracteres')
    ])
    categoria = StringField('Categoría', validators=[
        DataRequired(message='La categoría es obligatoria'),
        Length(max=100, message='La categoría no puede exceder 100 caracteres')
    ])
    subcategoria = StringField('Subcategoría', validators=[
        Optional(),
        Length(max=150, message='La subcategoría no puede exceder 150 caracteres')
    ])
    submit = SubmitField('Guardar Ejercicio')

class UsuarioEditForm(FlaskForm):
    """Formulario para editar información de usuario"""
    nombre = StringField('Nombre', validators=[
        DataRequired(message='El nombre es obligatorio'),
        Length(min=2, max=100, message='El nombre debe tener entre 2 y 100 caracteres')
    ])
    apellidos = StringField('Apellidos', validators=[
        DataRequired(message='Los apellidos son obligatorios'),
        Length(min=2, max=150, message='Los apellidos deben tener entre 2 y 150 caracteres')
    ])
    email = EmailField('Email', validators=[
        DataRequired(message='El email es obligatorio'),
        Email(message='Formato de email inválido'),
        Length(max=120, message='El email no puede exceder 120 caracteres')
    ])
    telefono = StringField('Teléfono', validators=[
        Optional(),
        Length(max=20, message='El teléfono no puede exceder 20 caracteres')
    ])
    fecha_nacimiento = DateField('Fecha de Nacimiento', validators=[Optional()])
    genero = SelectField('Género', choices=[('', 'Seleccionar...'), ('masculino','Masculino'), ('femenino','Femenino'), ('otro','Otro')], validators=[Optional()])
    direccion = StringField('Dirección', validators=[Optional(), Length(max=255)])
    ciudad = StringField('Ciudad', validators=[Optional(), Length(max=100)])
    codigo_postal = StringField('Código Postal', validators=[Optional(), Length(max=20)])
    submit = SubmitField('Actualizar Información')
