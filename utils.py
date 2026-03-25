import logging
import os
from datetime import datetime
from functools import wraps
from flask import request, session, flash, redirect, url_for, current_app
from sqlalchemy.exc import SQLAlchemyError

def setup_logging(app):
    """Configurar el sistema de logging de la aplicación"""
    
    # Crear directorio de logs si no existe
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configurar logging
    log_file = os.path.join(log_dir, 'fitness_app.log')
    
    # Formato del log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handler para archivo
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    
    # Configurar logger principal
    logger = logging.getLogger('fitness_app')
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Configurar loggers de Flask y SQLAlchemy
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    
    return logger

def log_activity(activity, user_id=None, details=None):
    """Registrar actividad del usuario"""
    logger = logging.getLogger('fitness_app')
    
    user_info = f"Usuario ID: {user_id}" if user_id else "Usuario no autenticado"
    details_info = f" - Detalles: {details}" if details else ""
    
    log_message = f"ACTIVIDAD: {activity} - {user_info}{details_info}"
    logger.info(log_message)

def log_error(error, context=None):
    """Registrar errores de la aplicación"""
    logger = logging.getLogger('fitness_app')
    
    context_info = f" - Contexto: {context}" if context else ""
    log_message = f"ERROR: {str(error)}{context_info}"
    logger.error(log_message, exc_info=True)

def handle_db_error(func):
    """Decorador para manejar errores de base de datos"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as e:
            log_error(e, f"Función: {func.__name__}")
            flash("Error en la base de datos. Intenta de nuevo.", "danger")
            return redirect(url_for('index'))
        except Exception as e:
            log_error(e, f"Función: {func.__name__}")
            flash("Ha ocurrido un error inesperado.", "danger")
            return redirect(url_for('index'))
    return wrapper

def admin_required(f):
    """Decorador para requerir rol de administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Debes iniciar sesión para acceder a esta página.", "warning")
            return redirect(url_for('login'))
        
        if session.get('role') != 'admin':
            flash("No tienes permisos para acceder a esta página.", "danger")
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """Decorador para requerir autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Debes iniciar sesión para acceder a esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
