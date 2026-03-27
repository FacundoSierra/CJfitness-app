from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import enum

db = SQLAlchemy()

# Estados de pago como strings simples
# PENDIENTE, PAGADO, CANCELADO, FALLIDO, REEMBOLSADO

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    nombre = db.Column(db.String(80), nullable=False)
    apellidos = db.Column(db.String(80), nullable=False)
    telefono = db.Column(db.String(20))
    # Campos adicionales de perfil
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    genero = db.Column(db.String(20), nullable=True)
    direccion = db.Column(db.String(255), nullable=True)
    ciudad = db.Column(db.String(100), nullable=True)
    codigo_postal = db.Column(db.String(20), nullable=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    rol = db.Column(db.String(20), default='usuario')
    
    # Relaciones
    rutinas = db.relationship('Rutina', backref='usuario', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Usuario {self.username}>'

class Ejercicio(db.Model):
    __tablename__ = 'ejercicios'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(100), nullable=False)
    subcategoria = db.Column(db.String(100), nullable=False)
    
    # Relaciones
    ejercicios_asignados = db.relationship('EjercicioAsignado', lazy=True)
    
    def __repr__(self):
        return f'<Ejercicio {self.nombre}>'

class Rutina(db.Model):
    __tablename__ = 'rutinas'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    # Columnas removidas: nombre, descripcion, activa (no existen en Render DB)

    bloques = db.relationship('Bloque', backref='rutina', lazy=True, cascade='all, delete-orphan')

class Bloque(db.Model):
    __tablename__ = 'bloques'
    id = db.Column(db.Integer, primary_key=True)
    rutina_id = db.Column(db.Integer, db.ForeignKey('rutinas.id'), nullable=False)
    nombre_bloque = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(100), nullable=False)
    # Columna removida: orden (no existe en Render DB)

    ejercicios = db.relationship('EjercicioAsignado', lazy=True, cascade='all, delete-orphan')

class EjercicioAsignado(db.Model):
    __tablename__ = 'ejercicios_asignados'
    id = db.Column(db.Integer, primary_key=True)
    bloque_id = db.Column(db.Integer, db.ForeignKey('bloques.id'), nullable=False)
    ejercicio_id = db.Column(db.Integer, db.ForeignKey('ejercicios.id'), nullable=True)
    nombre_manual = db.Column(db.String(128), nullable=True)
    series_reps = db.Column(db.String(32), nullable=True)   # legacy
    rpe = db.Column(db.String(12), nullable=True)           # legacy
    carga = db.Column(db.String(32), nullable=True)         # legacy
    series_json = db.Column(db.Text, nullable=True)         # nuevo: JSON con series variables
    categoria = db.Column(db.String(64), nullable=True)
    subcategoria = db.Column(db.String(64), nullable=True)
    # Columnas removidas: orden, descanso, tiempo (no existen en Render DB)

    ejercicio = relationship("Ejercicio")
    bloque = relationship("Bloque")

    @property
    def series_data_parsed(self):
        """Devuelve el dict parseado de series_json, o None si no hay."""
        import json
        if self.series_json:
            try:
                return json.loads(self.series_json)
            except Exception:
                pass
        return None

    @property
    def series_display(self):
        """Cadena legible para mostrar el volumen del ejercicio."""
        d = self.series_data_parsed
        if d:
            if d.get('variar'):
                parts = [
                    f"S{i+1}: {s.get('reps','?')}r @ {s.get('carga','?')} RPE{s.get('rpe','?')}"
                    for i, s in enumerate(d.get('series_data', []))
                ]
                return ' / '.join(parts)
            carga = d.get('carga', '')
            carga_str = f" @ {carga}" if carga else ''
            rpe = d.get('rpe', '')
            rpe_str = f" (RPE {rpe})" if rpe else ''
            return f"{d.get('series','?')}×{d.get('reps','?')}{carga_str}{rpe_str}"
        return self.series_reps or ''

class Plan(db.Model):
    __tablename__ = 'planes'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    precio = db.Column(db.Numeric(8,2), nullable=False)
    duracion_dias = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # plan_basico, plan_pro, plan_anual
    caracteristicas = db.Column(db.JSON)
    activo = db.Column(db.Boolean, default=True)
    orden = db.Column(db.Integer, default=0)

class Pago(db.Model):
    __tablename__ = 'pagos'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_pago = db.Column(db.Date, nullable=False)
    cantidad = db.Column(db.Numeric(10, 2), nullable=False)
    estado = db.Column(db.String(20), default='pendiente')
    observaciones = db.Column(db.Text)
    metodo_pago = db.Column(db.String(50), nullable=False)  # efectivo, transferencia, tarjeta, etc.
    forma_pago = db.Column(db.String(100), nullable=True)  # descripción de cómo se paga
    mes_pago = db.Column(db.String(7), nullable=False)  # formato YYYY-MM para identificar el mes
    fecha_vencimiento = db.Column(db.Date, nullable=True)  # fecha límite para pagar
    activo = db.Column(db.Boolean, default=True)  # para cancelar pagos futuros
    
    # Relaciones
    usuario = db.relationship("Usuario")

class ConfiguracionPagoMensual(db.Model):
    __tablename__ = 'configuracion_pago_mensual'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    cantidad_mensual = db.Column(db.Numeric(10, 2), nullable=False)
    metodo_pago = db.Column(db.String(50), nullable=False)  # efectivo, transferencia, tarjeta, etc.
    forma_pago = db.Column(db.String(100), nullable=True)  # descripción de cómo se paga
    dia_vencimiento = db.Column(db.Integer, default=1)  # día del mes en que vence (1-31)
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_ultima_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    usuario = db.relationship("Usuario")

# Tabla para seguimiento de progreso del usuario
class SeguimientoEjercicio(db.Model):
    __tablename__ = 'seguimiento_ejercicios'
    __table_args__ = (
        db.UniqueConstraint('usuario_id', 'ejercicio_asignado_id', 'fecha_ejecucion', name='uq_usuario_ejercicio_fecha'),
        db.Index('ix_seguimiento_usuario_fecha', 'usuario_id', 'fecha_ejecucion'),
        db.Index('ix_seguimiento_ejercicio_fecha', 'ejercicio_asignado_id', 'fecha_ejecucion'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    ejercicio_asignado_id = db.Column(db.Integer, db.ForeignKey('ejercicios_asignados.id'), nullable=False)
    fecha_ejecucion = db.Column(db.Date, nullable=False, default=lambda: datetime.utcnow().date())
    
    # Valores planificados (del admin)
    series_reps_planificadas = db.Column(db.String(100), nullable=True)
    rpe_planificado = db.Column(db.String(50), nullable=True)
    carga_planificada = db.Column(db.String(50), nullable=True)
    
    # Valores reales (del usuario)
    series_reps_reales = db.Column(db.String(100), nullable=True)
    rpe_real = db.Column(db.String(50), nullable=True)
    carga_real = db.Column(db.String(50), nullable=True)
    
    # Notas del usuario
    notas = db.Column(db.Text, nullable=True)
    
    # Estado del ejercicio
    completado = db.Column(db.Boolean, default=False)
    fecha_completado = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    usuario = db.relationship("Usuario")
    ejercicio_asignado = db.relationship("EjercicioAsignado")
    
    def __repr__(self):
        return f'<SeguimientoEjercicio {self.id} - Usuario {self.usuario_id}>'

class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    usuario = db.relationship("Usuario")
    
    def is_valid(self):
        """Verificar si el token es válido (no expirado y no usado)"""
        return not self.used and datetime.utcnow() < self.expires_at
    
    def __repr__(self):
        return f'<PasswordResetToken {self.id} - Usuario {self.user_id}>'

class FeedbackSesion(db.Model):
    """Feedback bidireccional entre usuario y entrenador por sesión/día."""
    __tablename__ = 'feedback_sesiones'

    id          = db.Column(db.Integer, primary_key=True)
    usuario_id  = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha       = db.Column(db.Date, nullable=False)

    # Usuario → Entrenador
    valoracion      = db.Column(db.Integer, nullable=True)   # 1-5
    sensacion       = db.Column(db.String(20), nullable=True) # muy bien|bien|normal|mal|muy mal
    notas_usuario   = db.Column(db.Text, nullable=True)
    fecha_usuario   = db.Column(db.DateTime, nullable=True)

    # Entrenador → Usuario
    respuesta_entrenador = db.Column(db.Text, nullable=True)
    fecha_entrenador     = db.Column(db.DateTime, nullable=True)

    creado = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship("Usuario")

    def __repr__(self):
        return f'<FeedbackSesion {self.usuario_id} {self.fecha}>'


# Tablas simplificadas para el sistema de pagos básico
# Estas se pueden agregar más adelante si se necesitan
