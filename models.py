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
    __table_args__ = (
        db.Index('ix_rutina_usuario_fecha', 'usuario_id', 'fecha'),
    )
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    fecha = db.Column(db.Date, nullable=False, default=datetime.utcnow, index=True)
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
    bloque_id = db.Column(db.Integer, db.ForeignKey('bloques.id'), nullable=False, index=True)
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
                parts = []
                for i, s in enumerate(d.get('series_data', [])):
                    reps  = s.get('reps') or '?'
                    carga = str(s.get('carga') or '').strip()
                    rpe   = str(s.get('rpe') or '').strip()
                    parte = f"S{i+1}: {reps}r"
                    if carga: parte += f" {carga} kg"
                    if rpe:   parte += f" RPE{rpe}"
                    parts.append(parte)
                return ' / '.join(parts)
            carga = str(d.get('carga') or '').strip()
            rpe   = str(d.get('rpe') or '').strip()
            carga_str = f" {carga} kg" if carga else ''
            rpe_str   = f" RPE{rpe}" if rpe else ''
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
    series_reps_planificadas = db.Column(db.Text, nullable=True)
    rpe_planificado = db.Column(db.String(50), nullable=True)
    carga_planificada = db.Column(db.String(50), nullable=True)

    # Valores reales (del usuario)
    series_reps_reales = db.Column(db.Text, nullable=True)
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


# ── MÓDULO NUTRICIONAL ──────────────────────────────────────────────────────

class ComidaCompleta(db.Model):
    """Comidas predefinidas para generar menús diarios recomendados."""
    __tablename__ = 'comidas_completas'

    id               = db.Column(db.Integer, primary_key=True)
    nombre           = db.Column(db.String(200), nullable=False)
    franja           = db.Column(db.String(20),  nullable=False)   # desayuno|almuerzo|cena|snack
    calorias         = db.Column(db.Integer,      nullable=False)
    proteinas_g      = db.Column(db.Float,        nullable=False)
    carbohidratos_g  = db.Column(db.Float,        nullable=False)
    grasas_g         = db.Column(db.Float,        nullable=False)
    vegetariano      = db.Column(db.Boolean, default=False)
    sin_gluten       = db.Column(db.Boolean, default=False)
    sin_lacteos      = db.Column(db.Boolean, default=False)
    descripcion      = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<ComidaCompleta {self.nombre} [{self.franja}]>'


class PerfilNutricional(db.Model):
    """Datos del usuario necesarios para el motor de recomendación nutricional."""
    __tablename__ = 'perfiles_nutricionales'

    id            = db.Column(db.Integer, primary_key=True)
    usuario_id    = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, unique=True)
    objetivo      = db.Column(db.String(30), nullable=False, default='mantener')
    # opciones: perder_peso | ganar_masa | mantener | mejorar_rendimiento
    nivel_actividad = db.Column(db.String(20), nullable=False, default='moderado')
    # opciones: sedentario | ligero | moderado | activo | muy_activo
    peso_kg       = db.Column(db.Float, nullable=True)
    altura_cm     = db.Column(db.Float, nullable=True)
    alergias      = db.Column(db.JSON, nullable=True)       # lista de strings
    preferencias  = db.Column(db.JSON, nullable=True)       # lista de strings
    calorias_objetivo = db.Column(db.Integer, nullable=True)  # calculado con Mifflin-St Jeor
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    usuario = db.relationship('Usuario', backref=db.backref('perfil_nutricional', uselist=False))

    def __repr__(self):
        return f'<PerfilNutricional usuario={self.usuario_id} objetivo={self.objetivo}>'


class Alimento(db.Model):
    """Base de datos nutricional local (USDA + caché de Open Food Facts)."""
    __tablename__ = 'alimentos'

    id                  = db.Column(db.Integer, primary_key=True)
    nombre              = db.Column(db.String(300), nullable=False)
    calorias_100g       = db.Column(db.Float, nullable=False)
    proteinas_100g      = db.Column(db.Float, nullable=False)
    carbohidratos_100g  = db.Column(db.Float, nullable=False)
    grasas_100g         = db.Column(db.Float, nullable=False)
    categoria           = db.Column(db.String(30), nullable=False, default='otro')
    # opciones: proteina | cereal | verdura | fruta | lacteo | grasa | otro
    fuente              = db.Column(db.String(20), nullable=False, default='usda')
    # opciones: usda | openfoodfacts
    fuente_id           = db.Column(db.String(100), nullable=True, unique=True)
    # ID externo para evitar duplicados (fdcId o barcode)

    def __repr__(self):
        return f'<Alimento {self.nombre} [{self.categoria}]>'


class RecomendacionDiaria(db.Model):
    """Historial de menús diarios recomendados al usuario."""
    __tablename__ = 'recomendaciones_diarias'

    id              = db.Column(db.Integer, primary_key=True)
    usuario_id      = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha           = db.Column(db.Date, nullable=False)
    menu_json       = db.Column(db.JSON, nullable=False)    # estructura completa del menú
    calorias_totales = db.Column(db.Integer, nullable=True)
    macros_json     = db.Column(db.JSON, nullable=True)     # {'proteinas': x, 'carbohidratos': x, 'grasas': x}
    valoracion_usuario = db.Column(db.Integer, nullable=True)  # 1-5
    notas_usuario   = db.Column(db.Text, nullable=True)
    fecha_creacion  = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', backref=db.backref('recomendaciones', lazy='dynamic'))

    def __repr__(self):
        return f'<RecomendacionDiaria usuario={self.usuario_id} fecha={self.fecha}>'


class PreferenciaAlimento(db.Model):
    """Ingredientes/alimentos que el usuario no quiere en sus menús."""
    __tablename__ = 'preferencias_alimentos'
    __table_args__ = (
        db.UniqueConstraint('usuario_id', 'nombre_alimento', name='uq_pref_usuario_alimento'),
    )
    id              = db.Column(db.Integer, primary_key=True)
    usuario_id      = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nombre_alimento = db.Column(db.String(200), nullable=False)
    tipo            = db.Column(db.String(20), default='no_me_gusta')
    creado          = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('Usuario')

    def __repr__(self):
        return f'<PreferenciaAlimento {self.usuario_id} "{self.nombre_alimento}">'


class ValoracionComida(db.Model):
    """Valoración individual (1-5) del usuario por cada comida del menú."""
    __tablename__ = 'valoraciones_comidas'
    id            = db.Column(db.Integer, primary_key=True)
    usuario_id    = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nombre_comida = db.Column(db.String(200), nullable=False)
    valoracion    = db.Column(db.Integer, nullable=False)   # 1-5
    creado        = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('Usuario')

    def __repr__(self):
        return f'<ValoracionComida {self.usuario_id} "{self.nombre_comida}" {self.valoracion}★>'


# ── MÓDULO TAXONOMÍA DE EJERCICIOS ───────────────────────────────────────────
# Sistema jerárquico: BloqueTaxonomia → CategoriaTaxonomia → SubcategoriaTaxonomia
# con características específicas configurables por bloque.
# Coexiste con el modelo Ejercicio (simple) y Bloque (de rutinas) sin colisionar.

class BloqueTaxonomia(db.Model):
    """Nivel raíz de la jerarquía: Fuerza, Core, Potencia, Preparación, DSE."""
    __tablename__ = 'bloques_taxonomia'
    id      = db.Column(db.Integer, primary_key=True)
    nombre  = db.Column(db.String(100), unique=True, nullable=False)
    activo  = db.Column(db.Boolean, default=True)
    orden   = db.Column(db.Integer, default=0)
    categorias      = db.relationship('CategoriaTaxonomia', backref='bloque',
                                       lazy=True, cascade='all, delete-orphan',
                                       order_by='CategoriaTaxonomia.orden')
    caracteristicas = db.relationship('CaracteristicaTipo', backref='bloque',
                                       lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<BloqueTaxonomia "{self.nombre}">'


class CategoriaTaxonomia(db.Model):
    """Segundo nivel: PRINCIPALES, AUXILIARES, Patron_Respiratorio, etc."""
    __tablename__ = 'categorias_taxonomia'
    id        = db.Column(db.Integer, primary_key=True)
    bloque_id = db.Column(db.Integer, db.ForeignKey('bloques_taxonomia.id'), nullable=False)
    nombre    = db.Column(db.String(100), nullable=False)
    activo    = db.Column(db.Boolean, default=True)
    orden     = db.Column(db.Integer, default=0)
    subcategorias = db.relationship('SubcategoriaTaxonomia', backref='categoria',
                                     lazy=True, cascade='all, delete-orphan',
                                     order_by='SubcategoriaTaxonomia.orden')

    def __repr__(self):
        return f'<CategoriaTaxonomia "{self.nombre}">'


class SubcategoriaTaxonomia(db.Model):
    """Tercer nivel: 3FE, Bisagra de cadera, PRV, Anti-extensión, etc."""
    __tablename__ = 'subcategorias_taxonomia'
    id           = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias_taxonomia.id'), nullable=False)
    nombre       = db.Column(db.String(100), nullable=False)
    activo       = db.Column(db.Boolean, default=True)
    orden        = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<SubcategoriaTaxonomia "{self.nombre}">'


class CaracteristicaTipo(db.Model):
    """Tipo de característica específica del bloque: Base, Agarre, Posturas…"""
    __tablename__ = 'caracteristicas_tipo'
    id        = db.Column(db.Integer, primary_key=True)
    bloque_id = db.Column(db.Integer, db.ForeignKey('bloques_taxonomia.id'), nullable=False)
    nombre    = db.Column(db.String(100), nullable=False)
    activo    = db.Column(db.Boolean, default=True)
    valores   = db.relationship('CaracteristicaValor', backref='tipo',
                                 lazy=True, cascade='all, delete-orphan',
                                 order_by='CaracteristicaValor.orden')

    def __repr__(self):
        return f'<CaracteristicaTipo "{self.nombre}">'


class CaracteristicaValor(db.Model):
    """Valor concreto de una característica: C1, C2, pronado, supino…"""
    __tablename__ = 'caracteristicas_valores'
    id      = db.Column(db.Integer, primary_key=True)
    tipo_id = db.Column(db.Integer, db.ForeignKey('caracteristicas_tipo.id'), nullable=False)
    nombre  = db.Column(db.String(100), nullable=False)
    activo  = db.Column(db.Boolean, default=True)
    orden   = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<CaracteristicaValor "{self.nombre}">'


class EjercicioCompleto(db.Model):
    """Ejercicio con taxonomía completa. Coexiste con el modelo Ejercicio original."""
    __tablename__ = 'ejercicios_completos'
    id              = db.Column(db.Integer, primary_key=True)
    nombre          = db.Column(db.String(200), nullable=False)
    bloque_id       = db.Column(db.Integer, db.ForeignKey('bloques_taxonomia.id'), nullable=False)
    categoria_id    = db.Column(db.Integer, db.ForeignKey('categorias_taxonomia.id'), nullable=True)
    subcategoria_id = db.Column(db.Integer, db.ForeignKey('subcategorias_taxonomia.id'), nullable=True)
    # {"Base": "dos piernas", "Agarre": "pronado", "Posturas": "C1"}
    caracteristicas_json  = db.Column(db.JSON, nullable=True)
    material              = db.Column(db.String(200), nullable=True)
    otras_caracteristicas = db.Column(db.Text, nullable=True)
    activo         = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    bloque       = db.relationship('BloqueTaxonomia')
    categoria    = db.relationship('CategoriaTaxonomia')
    subcategoria = db.relationship('SubcategoriaTaxonomia')

    def __repr__(self):
        return f'<EjercicioCompleto "{self.nombre}">'

class EventoAdmin(db.Model):
    __tablename__ = 'eventos_admin'
    id           = db.Column(db.Integer, primary_key=True)
    titulo       = db.Column(db.String(200), nullable=False)
    descripcion  = db.Column(db.Text, nullable=True)
    fecha_inicio = db.Column(db.DateTime, nullable=False)
    fecha_fin    = db.Column(db.DateTime, nullable=True)
    todo_el_dia  = db.Column(db.Boolean, default=False)
    color        = db.Column(db.String(20), default='#3788d8')
    creado_en    = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<EventoAdmin "{self.titulo}">'
