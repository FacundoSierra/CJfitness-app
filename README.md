# Fitness App V2

Aplicación web de fitness desarrollada en Flask para la gestión de entrenamientos, ejercicios y pagos.

## 🚀 Características

### Sistema de Usuarios
- Registro y login de usuarios
- Dashboard personalizado
- Gestión de perfiles

### Gestión de Ejercicios
- Biblioteca de ejercicios categorizada
- Búsqueda avanzada
- Filtros por categoría y subcategoría

### Sistema de Rutinas
- Creación y asignación de rutinas
- Calendario de entrenamientos
- Gestión de bloques y ejercicios

### Sistema de Pagos
- Registro manual de pagos
- Estados de pago (pendiente, completado, cancelado)
- Dashboard administrativo con estadísticas

### Panel de Administración
- Gestión de usuarios
- Asignación de rutinas
- Control de pagos
- Estadísticas generales

## 🛠️ Tecnologías

- **Backend**: Flask, Python
- **Base de Datos**: PostgreSQL (Render)
- **Frontend**: HTML, CSS, JavaScript, Bootstrap
- **Autenticación**: Flask-Login
- **ORM**: SQLAlchemy

## 📋 Requisitos

- Python 3.8+
- PostgreSQL
- Dependencias listadas en `requirements.txt`

## 🔧 Instalación

1. Clonar el repositorio
2. Instalar dependencias: `pip install -r requirements.txt`
3. Configurar variables de entorno
4. Ejecutar: `python app.py`

## 📁 Estructura del Proyecto

```
Fitness_app_V2/
├── app.py                 # Aplicación principal Flask
├── models.py             # Modelos de base de datos
├── forms.py              # Formularios de la aplicación
├── config.py             # Configuración
├── payment_service.py    # Servicio de pagos
├── utils.py              # Utilidades
├── requirements.txt      # Dependencias Python
├── templates/            # Plantillas HTML
├── static/               # Archivos estáticos (CSS, JS, imágenes)
└── .gitignore           # Archivos ignorados por Git
```

## 🔐 Variables de Entorno

Crear archivo `.env` con:
- `DATABASE_URL`: URL de la base de datos PostgreSQL
- `SECRET_KEY`: Clave secreta de Flask
- `FLASK_ENV`: Entorno de desarrollo/producción

## 📝 Licencia

Proyecto privado - Todos los derechos reservados
