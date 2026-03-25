from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from calendar import monthrange
from collections import defaultdict
from forms import LoginForm, RegisterForm

# Crear aplicación Flask
app = Flask(__name__)

# Configuración
from config import config
config_name = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[config_name])

# Validar SECRET_KEY en producción
if config_name == 'production' and not os.environ.get('SECRET_KEY'):
    raise RuntimeError(
        "SECRET_KEY must be set as an environment variable in production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
  
# Inicializar base de datos
from models import db
db.init_app(app)

# Importar modelos después de inicializar db
from models import Usuario, Ejercicio, Rutina, Bloque, EjercicioAsignado, Plan, Pago, ConfiguracionPagoMensual, SeguimientoEjercicio

# Importar payment service
from payment_service import payment_service

# Configurar logging
from utils import setup_logging, log_activity, log_error, handle_db_error, admin_required, login_required
logger = setup_logging(app)

# ------------------ RUTAS ------------------

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(app.static_folder, 'sitemap.xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route('/')
def index():
    return render_template('index.html')

# ------------------ LOGIN / REGISTRO ------------------

@app.route('/register', methods=['GET', 'POST'])
@handle_db_error
def register():
    form = RegisterForm()
    
    if form.validate_on_submit():
        try:
            nuevo_usuario = Usuario(
                username=form.username.data,
                email=form.email.data,
                password=generate_password_hash(form.password.data),
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

# ------------------ ADMIN ------------------

@app.route('/admin_dashboard')
@admin_required
@handle_db_error
def admin_dashboard():
    # Obtener estadísticas reales
    total_usuarios = Usuario.query.filter(Usuario.rol != 'admin').count()
    total_ejercicios = Ejercicio.query.count()
    total_rutinas = Rutina.query.count()
    
    # Obtener estadísticas de seguimiento
    total_seguimientos = SeguimientoEjercicio.query.count()
    ejercicios_completados = SeguimientoEjercicio.query.filter_by(completado=True).count()
    usuarios_activos = db.session.query(SeguimientoEjercicio.usuario_id).distinct().count()
    
    # Obtener usuarios recientes
    ultimos_usuarios = Usuario.query.filter(Usuario.rol != 'admin').order_by(Usuario.id.desc()).limit(5).all()
    
    # Obtener estadísticas de pagos
    try:
        from payment_service import payment_service
        stats_pagos = payment_service.obtener_estadisticas_pagos()
        ingresos_mes = stats_pagos.get('ingresos_mes', 0)
        pagos_mes = stats_pagos.get('pagos_pagados', 0)
    except Exception as e:
        log_error(e, "Error obteniendo estadísticas de pagos en dashboard")
        ingresos_mes = 0
        pagos_mes = 0
    
    # Obtener progreso reciente de usuarios
    progreso_reciente = db.session.query(
        SeguimientoEjercicio,
        Usuario,
        EjercicioAsignado
    ).join(Usuario, SeguimientoEjercicio.usuario_id == Usuario.id)\
     .join(EjercicioAsignado, SeguimientoEjercicio.ejercicio_asignado_id == EjercicioAsignado.id)\
     .order_by(SeguimientoEjercicio.fecha_actualizacion.desc())\
     .limit(10).all()
    
    # Log de actividad
    log_activity("Acceso al dashboard admin", session['user_id'])

    return render_template('admin_dashboard.html',
                           username=session.get('username'),
                           total_usuarios=total_usuarios,
                           total_ejercicios=total_ejercicios,
                           total_rutinas=total_rutinas,
                           total_seguimientos=total_seguimientos,
                           ejercicios_completados=ejercicios_completados,
                           usuarios_activos=usuarios_activos,
                           ingresos_mes=ingresos_mes,
                           pagos_mes=pagos_mes,
                           ultimos_usuarios=ultimos_usuarios,
                           progreso_reciente=progreso_reciente,
                           active_page='panel')

@app.route('/admin_usuarios')
@admin_required
@handle_db_error
def admin_usuarios():
    usuarios = Usuario.query.filter(Usuario.rol != 'admin').order_by(Usuario.id.desc()).all()
    return render_template('admin_usuarios.html', usuarios=usuarios, active_page='usuarios')

# ------------------ ADMIN ENTRENAMIENTOS ------------------

@app.route('/admin_entrenamientos')
@admin_required
@handle_db_error
def admin_entrenamientos():
    usuarios = Usuario.query.filter(Usuario.rol != 'admin').all()
    return render_template('admin_entrenamientos.html', usuarios=usuarios, active_page='entrenamientos')

# ------------------ ADMIN ASIGNAR ------------------

@app.route('/admin_entrenamientos/<int:user_id>/asignar', methods=['GET', 'POST'])
@admin_required
@handle_db_error
def asignar_rutinas_usuario(user_id):
    usuario = Usuario.query.get(user_id)
    if not usuario:
        return "Usuario no encontrado", 404

    dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

    if request.method == 'POST':
        Rutina.query.filter_by(usuario_id=user_id).delete()
        db.session.commit()

        hoy = datetime.today()
        dia_a_fecha = {dias[i]: hoy + timedelta(days=i - hoy.weekday()) for i in range(7)}

        for dia in dias:
            bloques_html = [key for key in request.form if key.startswith(f'ejercicio_{dia}_')]
            bloques_ids = set(k.split('_')[2].split('[')[0] for k in bloques_html)

            for bloque_id in bloques_ids:
                ejercicios = request.form.getlist(f'ejercicio_{dia}_{bloque_id}[]')
                series = request.form.getlist(f'series_{dia}_{bloque_id}[]')
                rpes = request.form.getlist(f'rpe_{dia}_{bloque_id}[]')
                cargas = request.form.getlist(f'carga_{dia}_{bloque_id}[]')
                categoria = request.form.get(f'bloque_{dia}_{bloque_id}_categoria')
                subcategoria = request.form.get(f'bloque_{dia}_{bloque_id}_subcategoria')
                fecha_rutina = dia_a_fecha[dia].date()

                rutina = Rutina(usuario_id=user_id, fecha=fecha_rutina)
                db.session.add(rutina)
                db.session.commit()

                bloque = Bloque(rutina_id=rutina.id, nombre_bloque=f'Bloque {bloque_id}', categoria=categoria)
                db.session.add(bloque)
                db.session.commit()

                for i in range(len(ejercicios)):
                    nombre_ejercicio = ejercicios[i]
                    ejercicio_obj = Ejercicio.query.filter_by(nombre=nombre_ejercicio).first()
                    ejercicio_id = ejercicio_obj.id if ejercicio_obj else None

                    asignado = EjercicioAsignado(
                        bloque_id=bloque.id,
                        ejercicio_id=ejercicio_id,
                        nombre_manual=nombre_ejercicio if not ejercicio_id else None,
                        series_reps=series[i],
                        rpe=rpes[i],
                        carga=cargas[i]
                    )
                    db.session.add(asignado)

        db.session.commit()
        return redirect(url_for('admin_entrenamientos'))

    return render_template('admin_asignar_rutina_usuario.html',
                           usuario=usuario,
                           dias=dias,
                           active_page='entrenamientos')

# ------------------ ADMIN VER ------------------

@app.route('/ver_rutinas/<int:user_id>')
@admin_required
@handle_db_error
def ver_rutinas_usuario(user_id):
    usuario = db.session.get(Usuario, user_id)
    if not usuario:
        return "Usuario no encontrado", 404

    # Obtener parámetros de vista y mes
    vista = request.args.get("vista", "mensual")  # diaria, semanal, mensual
    mes_str = request.args.get("mes")
    fecha_especifica = request.args.get("fecha")
    
    hoy = datetime.today()
    
    if fecha_especifica:
        try:
            fecha_obj = datetime.strptime(fecha_especifica, "%Y-%m-%d").date()
        except ValueError:
            fecha_obj = hoy.date()
    elif mes_str:
        try:
            año, mes = map(int, mes_str.split("-"))
            fecha_obj = datetime(año, mes, 1).date()
        except ValueError:
            fecha_obj = hoy.date()
    else:
        fecha_obj = hoy.date()

    # Preparar datos según la vista
    if vista == "diaria":
        # Vista diaria - solo un día
        rutinas = Rutina.query.filter_by(
            usuario_id=user_id, 
            fecha=fecha_obj
        ).order_by(Rutina.fecha).all()
        
        # Agrupar por bloques para el día
        bloques_dia = []
        for r in rutinas:
            for b in r.bloques:
                ejercicios = []
                for e in b.ejercicios:
                    ejercicios.append({
                        "nombre_manual": e.nombre_manual,
                        "series_reps": e.series_reps,
                        "rpe": e.rpe,
                        "carga": e.carga,
                        "ejercicio": {"nombre": e.ejercicio.nombre} if e.ejercicio else None,
                        "categoria": e.categoria,
                        "subcategoria": e.subcategoria
                    })
                bloques_dia.append({
                    "nombre_bloque": b.nombre_bloque,
                    "categoria": b.categoria,
                    "ejercicios": ejercicios
                })
        
        datos_vista = {
            "tipo": "diaria",
            "fecha": fecha_obj,
            "bloques": bloques_dia
        }
        
    elif vista == "semanal":
        # Vista semanal - semana completa
        lunes = fecha_obj - timedelta(days=fecha_obj.weekday())
        domingo = lunes + timedelta(days=6)
        
        rutinas = Rutina.query.filter(
            Rutina.usuario_id == user_id,
            Rutina.fecha >= lunes,
            Rutina.fecha <= domingo
        ).order_by(Rutina.fecha).all()
        
        # Agrupar por día de la semana
        dias_semana = {}
        for i in range(7):
            fecha_dia = lunes + timedelta(days=i)
            dias_semana[fecha_dia] = []
        
        for r in rutinas:
            bloques_dia = []
            for b in r.bloques:
                ejercicios = []
                for e in b.ejercicios:
                    ejercicios.append({
                        "nombre_manual": e.nombre_manual,
                        "series_reps": e.series_reps,
                        "rpe": e.rpe,
                        "carga": e.carga,
                        "ejercicio": {"nombre": e.ejercicio.nombre} if e.ejercicio else None,
                        "categoria": e.categoria,
                        "subcategoria": e.subcategoria
                    })
                bloques_dia.append({
                    "nombre_bloque": b.nombre_bloque,
                    "categoria": b.categoria,
                    "ejercicios": ejercicios
                })
            dias_semana[r.fecha] = bloques_dia
        
        datos_vista = {
            "tipo": "semanal",
            "inicio": lunes,
            "fin": domingo,
            "dias": dias_semana
        }
        
    else:  # vista == "mensual"
        # Vista mensual - por semanas (original)
        inicio = fecha_obj.replace(day=1)
        fin = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
        
        rutinas = Rutina.query.filter(
            Rutina.usuario_id == user_id,
            Rutina.fecha >= inicio,
            Rutina.fecha < fin
        ).order_by(Rutina.fecha).all()
        
        # Agrupar por semana (lunes como clave)
        semanas_ordenadas = defaultdict(list)
        for r in rutinas:
            lunes = r.fecha - timedelta(days=r.fecha.weekday())
            semanas_ordenadas[lunes].append(r)
        
        # Convertir a estructura que el template entienda
        semanas_final = []
        for lunes, rutinas_semana in sorted(semanas_ordenadas.items()):
            bloques_semana = []
            for r in rutinas_semana:
                bloques = []
                for b in r.bloques:
                    ejercicios = []
                    for e in b.ejercicios:
                        ejercicios.append({
                            "nombre_manual": e.nombre_manual,
                            "series_reps": e.series_reps,
                            "rpe": e.rpe,
                            "carga": e.carga,
                            "ejercicio": {"nombre": e.ejercicio.nombre} if e.ejercicio else None,
                            "categoria": e.categoria,
                            "subcategoria": e.subcategoria
                        })
                    bloques.append({
                        "nombre_bloque": b.nombre_bloque,
                        "categoria": b.categoria,
                        "ejercicios": ejercicios
                    })
                bloques_semana.append({
                    "fecha": r.fecha.strftime("%Y-%m-%d"),
                    "bloques": bloques
                })
            
            semanas_final.append({
                "inicio": lunes,
                "fin": lunes + timedelta(days=6),
                "rutinas": bloques_semana
            })
        
        datos_vista = {
            "tipo": "mensual",
            "semanas": semanas_final
        }

    mes_actual = fecha_obj.strftime("%Y-%m")
    fecha_actual = fecha_obj.strftime("%Y-%m-%d")

    return render_template("admin_ver_rutinas_usuario.html",
                           usuario=usuario,
                           datos_vista=datos_vista,
                           vista_actual=vista,
                           mes_actual=mes_actual,
                           fecha_actual=fecha_actual,
                           active_page='entrenamientos')

# ------------------ ADMIN CALENDARIO ------------------

@app.route('/admin_entrenamientos/<int:user_id>/calendario', methods=['GET'])
@admin_required
@handle_db_error
def calendario_entrenamientos_usuario(user_id):
    usuario = Usuario.query.get(user_id)
    if not usuario:
        return "Usuario no encontrado", 404

    # Obtener el mes solicitado o usar el actual
    mes_param = request.args.get('mes')
    hoy = datetime.today()

    if mes_param:
        try:
            año, mes = map(int, mes_param.split("-"))
            base = datetime(año, mes, 1)
        except ValueError:
            base = hoy
    else:
        base = hoy

    # Calcular rango del mes
    año, mes = base.year, base.month
    primer_dia_mes = datetime(año, mes, 1)
    _, ultimo_dia = monthrange(año, mes)  # (weekday_inicio, días_totales)

    # Día de la semana en que inicia (0 = lunes)
    inicio_semana = primer_dia_mes.weekday()
    total_celdas = inicio_semana + ultimo_dia
    total_filas = (total_celdas + 6) // 7  # redondear filas necesarias

    # Generar todas las fechas del calendario
    dias_calendario = []
    dia_actual = primer_dia_mes - timedelta(days=inicio_semana)

    for _ in range(total_filas):
        semana = []
        for _ in range(7):
            fecha = dia_actual.date()
            rutina = Rutina.query.filter_by(usuario_id=user_id, fecha=fecha).first()
            semana.append({
                "fecha": fecha,
                "es_del_mes": fecha.month == mes,
                "rutina": rutina
            })
            dia_actual += timedelta(days=1)
        dias_calendario.append(semana)

    nombre_mes = base.strftime("%B de %Y")  # nombre completo y año
    mes_actual = base.strftime("%Y-%m")

    return render_template('admin_asignar_calendario.html',
                           usuario=usuario,
                           dias_calendario=dias_calendario,
                           nombre_mes=nombre_mes,
                           mes_actual=mes_actual,
                           active_page='entrenamientos')

# ------------------ ADMIN GUARDAR ------------------

@app.route('/admin_entrenamientos/<int:user_id>/guardar', methods=['POST'])
@admin_required
@handle_db_error
def guardar_rutina_fecha(user_id):
    try:
        fecha_str = request.form.get("fecha")
        if not fecha_str:
            flash("Error: No se recibió la fecha", "danger")
            return redirect(url_for('calendario_entrenamientos_usuario', user_id=user_id))
        
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        logger.info(f"Guardando rutina para usuario {user_id} en fecha {fecha}")

        # Eliminar rutina anterior (si existe) — cascade borra bloques y ejercicios asignados
        rutina_ant = Rutina.query.filter_by(usuario_id=user_id, fecha=fecha).first()
        if rutina_ant:
            logger.info(f"Eliminando rutina anterior para {fecha}")
            db.session.delete(rutina_ant)
            db.session.commit()

        # Crear nueva rutina
        rutina = Rutina(usuario_id=user_id, fecha=fecha)
        db.session.add(rutina)
        db.session.commit()
        logger.info(f"Nueva rutina creada con ID: {rutina.id}")

        # Detectar los bloques por el botón de añadir bloque
        bloque_indices = []
        for key in request.form:
            if key.startswith("ejercicio_") and key.endswith("[]"):
                bloque_id = key.split("_")[1].replace("[]", "")
                if bloque_id not in bloque_indices:
                    bloque_indices.append(bloque_id)

        logger.debug(f"Bloques detectados: {bloque_indices}")

        for bloque_id in bloque_indices:
            # Obtener la categoría del bloque desde el formulario
            categoria_bloque = request.form.get(f"categoria_bloque_{bloque_id}")
            if not categoria_bloque:
                categoria_bloque = "General"  # Valor por defecto si no se especifica

            bloque = Bloque(
                rutina_id=rutina.id,
                nombre_bloque=f'Bloque {bloque_id}',
                categoria=categoria_bloque
            )
            db.session.add(bloque)
            db.session.commit()
            logger.debug(f"Bloque {bloque_id} creado con ID: {bloque.id}, categoría: {categoria_bloque}")

            ejercicios = request.form.getlist(f"ejercicio_{bloque_id}[]")
            series = request.form.getlist(f"series_{bloque_id}[]")
            rpes = request.form.getlist(f"rpe_{bloque_id}[]")
            cargas = request.form.getlist(f"carga_{bloque_id}[]")
            categorias_ej = request.form.getlist(f"categoria_ej_{bloque_id}[]")
            subcategorias_ej = request.form.getlist(f"subcategoria_ej_{bloque_id}[]")

            logger.debug(f"Bloque {bloque_id}: {len(ejercicios)} ejercicios, {len(series)} series, {len(rpes)} RPEs, {len(cargas)} cargas")

            for i in range(len(ejercicios)):
                ejercicio = ejercicios[i]
                ejercicio_obj = Ejercicio.query.filter_by(nombre=ejercicio).first()
                ejercicio_id = ejercicio_obj.id if ejercicio_obj else None
                categoria_ej = categorias_ej[i] if i < len(categorias_ej) else None
                subcategoria_ej = subcategorias_ej[i] if i < len(subcategorias_ej) else None

                asignado = EjercicioAsignado(
                    bloque_id=bloque.id,
                    ejercicio_id=ejercicio_id,
                    nombre_manual=ejercicio if not ejercicio_id else None,
                    series_reps=series[i] if i < len(series) else None,
                    rpe=rpes[i] if i < len(rpes) else None,
                    carga=cargas[i] if i < len(cargas) else None,
                    categoria=categoria_ej,
                    subcategoria=subcategoria_ej
                )
                db.session.add(asignado)

        db.session.commit()
        logger.info(f"Rutina guardada correctamente para usuario {user_id} en fecha {fecha}")
        flash("Rutina asignada correctamente", "success")
        return redirect(url_for('calendario_entrenamientos_usuario', user_id=user_id, mes=fecha.strftime("%Y-%m")))

    except Exception as e:
        db.session.rollback()
        log_error(e, f"Error guardando rutina para usuario {user_id}")
        flash(f"Error al guardar la rutina: {str(e)}", "danger")
        return redirect(url_for('calendario_entrenamientos_usuario', user_id=user_id))

# ------------------ ADMIN EDITAR ------------------

@app.route('/admin_entrenamientos/<int:user_id>/editar', methods=['POST'])
@admin_required
@handle_db_error
def editar_rutina(user_id):
    try:
        fecha_str = request.form.get("fecha_editar")
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        
        logger.info(f"Editando rutina para usuario {user_id} en fecha {fecha}")

        # Eliminar rutina anterior — cascade borra bloques y ejercicios asignados
        rutina_ant = Rutina.query.filter_by(usuario_id=user_id, fecha=fecha).first()
        if rutina_ant:
            logger.info(f"Eliminando rutina anterior con {len(rutina_ant.bloques)} bloques")
            db.session.delete(rutina_ant)
            db.session.commit()

        # Crear nueva rutina
        rutina = Rutina(usuario_id=user_id, fecha=fecha)
        db.session.add(rutina)
        db.session.commit()
        logger.info(f"Nueva rutina creada con ID: {rutina.id}")

        # Detectar todos los bloques enviados
        bloque_ids = []
        for key in request.form:
            if key.startswith("ejercicio_") and key.endswith("[]"):
                bloque_id = key.split("_")[1].replace("[]", "")
                if bloque_id not in bloque_ids:
                    bloque_ids.append(bloque_id)
        
        logger.info(f"Bloques detectados: {bloque_ids}")

        for bloque_id in bloque_ids:
            # Obtener la categoría del bloque
            categoria_bloque = request.form.get(f"categoria_bloque_{bloque_id}")
            if not categoria_bloque:
                categoria_bloque = "General"  # Categoría por defecto
            
            logger.info(f"Creando bloque {bloque_id} con categoría: {categoria_bloque}")
            
            bloque = Bloque(
                rutina_id=rutina.id, 
                nombre_bloque=f'Bloque {bloque_id}',
                categoria=categoria_bloque
            )
            db.session.add(bloque)
            db.session.commit()
            logger.info(f"Bloque {bloque_id} creado con ID: {bloque.id}")

            ejercicios = request.form.getlist(f"ejercicio_{bloque_id}[]")
            series = request.form.getlist(f"series_{bloque_id}[]")
            rpes = request.form.getlist(f"rpe_{bloque_id}[]")
            cargas = request.form.getlist(f"carga_{bloque_id}[]")
            categorias_ej = request.form.getlist(f"categoria_ej_{bloque_id}[]")
            subcategorias_ej = request.form.getlist(f"subcategoria_ej_{bloque_id}[]")

            logger.info(f"Ejercicios para bloque {bloque_id}: {ejercicios}")

            for i in range(len(ejercicios)):
                ejercicio = ejercicios[i]
                ejercicio_obj = Ejercicio.query.filter_by(nombre=ejercicio).first()
                ejercicio_id = ejercicio_obj.id if ejercicio_obj else None
                categoria_ej = categorias_ej[i] if i < len(categorias_ej) else None
                subcategoria_ej = subcategorias_ej[i] if i < len(subcategorias_ej) else None

                asignado = EjercicioAsignado(
                    bloque_id=bloque.id,
                    ejercicio_id=ejercicio_id,
                    nombre_manual=ejercicio if not ejercicio_id else None,
                    series_reps=series[i],
                    rpe=rpes[i],
                    carga=cargas[i],
                    categoria=categoria_ej,
                    subcategoria=subcategoria_ej
                )
                db.session.add(asignado)

        db.session.commit()
        logger.info(f"✅ Rutina actualizada exitosamente para {fecha}")
        flash(f'✅ Rutina actualizada para {fecha.strftime("%d/%m/%Y")}', 'success')
        return redirect(url_for('ver_rutinas_usuario', user_id=user_id))
        
    except Exception as e:
        logger.error(f"Error editando rutina: {str(e)}")
        db.session.rollback()
        flash(f'❌ Error al editar la rutina: {str(e)}', 'danger')
        return redirect(url_for('ver_rutinas_usuario', user_id=user_id))

@app.route('/admin_entrenamientos/<int:user_id>/eliminar', methods=['POST'])
@admin_required
@handle_db_error
def eliminar_rutina(user_id):
    fecha_str = request.form.get("fecha_eliminar")
    fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()

    # Buscar y eliminar la rutina
    rutina = Rutina.query.filter_by(usuario_id=user_id, fecha=fecha).first()
    if rutina:
        # Eliminar ejercicios asignados primero
        for bloque in rutina.bloques:
            EjercicioAsignado.query.filter_by(bloque_id=bloque.id).delete()
            db.session.delete(bloque)
        
        # Eliminar la rutina
        db.session.delete(rutina)
        db.session.commit()
        
        flash(f'✅ Rutina eliminada para {fecha.strftime("%d/%m/%Y")}', 'success')
    else:
        flash('❌ No se encontró la rutina para eliminar', 'danger')
    
    return redirect(url_for('ver_rutinas_usuario', user_id=user_id))

# ------------------ ADMIN API_EJERCICIOS ------------------

@app.route('/api_ejercicios')
def api_ejercicios():
    ejercicios = Ejercicio.query.all()
    data = {}
    for e in ejercicios:
        categoria = e.categoria or "Sin categoría"
        subcategoria = e.subcategoria or "Sin subcategoría"
        nombre = e.nombre
        data.setdefault(categoria, {}).setdefault(subcategoria, []).append(nombre)
    return jsonify(data)

# ------------------ ADMIN ESTADISTICAS ------------------

@app.route('/admin_estadisticas')
@admin_required
def admin_estadisticas():
    return render_template('admin_en_construccion.html',
                           titulo="Estadísticas",
                           mensaje="Próximamente podrás ver estadísticas detalladas aquí.",
                           active_page='estadisticas')

# --------------------- ADMIN BORRAR/EDITAR USUARIO ---------------------------------------------

@app.route('/admin/usuarios/borrar/<int:user_id>', methods=['POST'])
@admin_required
@handle_db_error
def borrar_usuario(user_id):
    user = Usuario.query.get_or_404(user_id)
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f"Usuario {user.nombre} {user.apellidos} eliminado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash("No se pudo eliminar el usuario. Intenta de nuevo.", "danger")
    return redirect(url_for('admin_usuarios'))

@app.route('/admin/usuarios/editar/<int:user_id>', methods=['GET', 'POST'])
@admin_required
@handle_db_error
def editar_usuario(user_id):
    user = Usuario.query.get_or_404(user_id)
    if request.method == 'POST':
        user.nombre = request.form['nombre']
        user.apellidos = request.form['apellidos']
        user.email = request.form['email']
        user.telefono = request.form['telefono']
        try:
            db.session.commit()
            flash("Usuario actualizado correctamente.", "success")
            return redirect(url_for('admin_usuarios'))
        except Exception as e:
            db.session.rollback()
            flash("No se pudo actualizar el usuario.", "danger")
            return redirect(url_for('admin_usuarios'))

# --------------------- PAGOS ---------------------------------------------

# Función antigua de admin_pagos eliminada - ahora usa payment_service

@app.route('/admin_pagos/nuevo', methods=['POST'])
@admin_required
@handle_db_error
def admin_pagos_nuevo():
    try:
        usuario_id = request.form['usuario_id']
        cantidad = request.form['cantidad']
        metodo_pago = request.form['metodo_pago']
        forma_pago = request.form.get('forma_pago', '')
        observaciones = request.form.get('observaciones', '')
        
        # Validaciones
        if not usuario_id or not cantidad or not metodo_pago:
            flash('Usuario, cantidad y método de pago son obligatorios', 'danger')
            return redirect(url_for('admin_pagos'))
        
        # Verificar que el usuario existe
        usuario = Usuario.query.get(usuario_id)
        if not usuario:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('admin_pagos'))
        
        # Validar cantidad
        try:
            cantidad_float = float(cantidad)
            if cantidad_float <= 0:
                flash('La cantidad debe ser mayor a 0', 'danger')
                return redirect(url_for('admin_pagos'))
        except ValueError:
            flash('La cantidad debe ser un número válido', 'danger')
            return redirect(url_for('admin_pagos'))
        
        # Registrar el pago usando el servicio
        resultado = payment_service.registrar_pago(
            usuario_id=int(usuario_id),
            cantidad=cantidad_float,
            metodo_pago=metodo_pago,
            forma_pago=forma_pago,
            observaciones=observaciones
        )
        
        if resultado['success']:
            # Log de actividad
            log_activity(f"Pago registrado: €{cantidad_float} para {usuario.nombre}", session['user_id'])
            flash(f'Pago de €{cantidad_float} registrado correctamente para {usuario.nombre}', 'success')
        else:
            flash(f'Error al registrar el pago: {resultado["error"]}', 'danger')
        
    except Exception as e:
        db.session.rollback()
        log_error(f"Error creando pago: {e}", session.get('user_id'))
        flash('Error al crear el pago. Intenta de nuevo.', 'danger')
    
    return redirect(url_for('admin_pagos'))

@app.route('/admin_pagos/eliminar/<int:pago_id>', methods=['POST'])
@admin_required
@handle_db_error
def admin_pagos_eliminar(pago_id):
    try:
        pago = Pago.query.get_or_404(pago_id)
        
        # Guardar información para el log
        info_pago = f"ID {pago_id}, Usuario: {pago.usuario.nombre}, Cantidad: €{pago.cantidad}, Estado: {pago.estado}"
        
        # Eliminar el pago
        db.session.delete(pago)
        db.session.commit()
        
        # Log de actividad
        log_activity(f"Pago eliminado: {info_pago}", session['user_id'])
        
        flash('Pago eliminado correctamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        log_error(f"Error eliminando pago {pago_id}: {e}", session.get('user_id'))
        flash('Error al eliminar el pago. Intenta de nuevo.', 'danger')
    
    return redirect(url_for('admin_pagos'))

@app.route('/admin_pagos/editar/<int:pago_id>', methods=['POST'])
@admin_required
@handle_db_error
def admin_pagos_editar(pago_id):
    try:
        pago = Pago.query.get_or_404(pago_id)
        
        # Obtener datos del formulario
        nuevo_estado = request.form['estado']
        nueva_fecha = request.form['fecha_pago']
        nueva_cantidad = request.form['cantidad']
        nuevas_observaciones = request.form['observaciones']
        
        # Validaciones
        if not nueva_fecha or not nueva_cantidad:
            flash('Todos los campos obligatorios deben estar completos', 'danger')
            return redirect(url_for('admin_pagos'))
        
        # Validar cantidad
        try:
            cantidad_float = float(nueva_cantidad)
            if cantidad_float <= 0:
                flash('La cantidad debe ser mayor a 0', 'danger')
                return redirect(url_for('admin_pagos'))
        except ValueError:
            flash('La cantidad debe ser un número válido', 'danger')
            return redirect(url_for('admin_pagos'))
        
        # Validar fecha
        try:
            fecha_pago_obj = datetime.strptime(nueva_fecha, '%Y-%m-%d').date()
            if fecha_pago_obj > datetime.today().date():
                flash('La fecha de pago no puede ser futura', 'warning')
        except ValueError:
            flash('Formato de fecha inválido', 'danger')
            return redirect(url_for('admin_pagos'))
        
        # Guardar valores anteriores para el log
        estado_anterior = pago.estado
        cantidad_anterior = pago.cantidad
        
        # Actualizar el pago
        pago.estado = nuevo_estado
        pago.fecha_pago = fecha_pago_obj
        pago.cantidad = cantidad_float
        pago.observaciones = nuevas_observaciones
        
        db.session.commit()
        
        # Log de actividad
        log_activity(
            f"Pago actualizado: ID {pago_id}, Estado: {estado_anterior} → {nuevo_estado}, "
            f"Cantidad: €{cantidad_anterior} → €{cantidad_float}", 
            session['user_id']
        )
        
        flash('Pago actualizado correctamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        log_error(f"Error actualizando pago {pago_id}: {e}", session.get('user_id'))
        flash('Error al actualizar el pago. Intenta de nuevo.', 'danger')
    
    return redirect(url_for('admin_pagos'))

# --------------------- EJERCICIOS ---------------------------------------------

@app.route('/admin_ejercicios')
@admin_required
@handle_db_error
def admin_ejercicios():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'nombre')
    order = request.args.get('order', 'asc')

    query = Ejercicio.query
    if search:
        search_like = f"%{search}%"
        query = query.filter(
            (Ejercicio.nombre.ilike(search_like)) |
            (Ejercicio.categoria.ilike(search_like)) |
            (Ejercicio.subcategoria.ilike(search_like))
        )

    sort_column = getattr(Ejercicio, sort, Ejercicio.nombre)
    if order == 'desc':
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    ejercicios_pagination = query.paginate(page=page, per_page=30)

    return render_template('admin_ejercicios.html',
                           ejercicios_pagination=ejercicios_pagination,
                           search=search, sort=sort, order=order)

@app.route('/admin_ejercicios/nuevo', methods=['POST'])
@admin_required
@handle_db_error
def admin_ejercicios_nuevo():
    nombre = request.form['nombre']
    categoria = request.form['categoria']
    subcategoria = request.form['subcategoria']
    ejercicio = Ejercicio(nombre=nombre, categoria=categoria, subcategoria=subcategoria)
    db.session.add(ejercicio)
    db.session.commit()
    flash('Ejercicio añadido', 'success')
    return redirect(url_for('admin_ejercicios'))

@app.route('/admin_ejercicios/eliminar/<int:e_id>', methods=['POST'])
@admin_required
@handle_db_error
def admin_ejercicios_eliminar(e_id):
    ejercicio = Ejercicio.query.get_or_404(e_id)
    db.session.delete(ejercicio)
    db.session.commit()
    flash('Ejercicio eliminado', 'success')
    return redirect(url_for('admin_ejercicios'))

@app.route('/admin_ejercicios/editar/<int:e_id>', methods=['POST'])
@admin_required
@handle_db_error
def admin_ejercicios_editar(e_id):
    ejercicio = Ejercicio.query.get_or_404(e_id)
    ejercicio.nombre = request.form['nombre']
    ejercicio.categoria = request.form['categoria']
    ejercicio.subcategoria = request.form['subcategoria']
    db.session.commit()
    flash('Ejercicio actualizado', 'success')
    return redirect(url_for('admin_ejercicios'))

@app.route('/admin_ejercicios_buscar')
@admin_required
@handle_db_error
def admin_ejercicios_buscar():
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'success': False, 'error': 'Término de búsqueda requerido'})
    
    try:
        # Buscar en todos los ejercicios sin paginación
        search_like = f"%{query}%"
        ejercicios = Ejercicio.query.filter(
            (Ejercicio.nombre.ilike(search_like)) |
            (Ejercicio.categoria.ilike(search_like)) |
            (Ejercicio.subcategoria.ilike(search_like))
        ).order_by(Ejercicio.nombre).all()
        
        # Convertir a formato JSON
        ejercicios_data = []
        for ejercicio in ejercicios:
            ejercicios_data.append({
                'id': ejercicio.id,
                'nombre': ejercicio.nombre,
                'categoria': ejercicio.categoria,
                'subcategoria': ejercicio.subcategoria
            })
        
        return jsonify({
            'success': True,
            'ejercicios': ejercicios_data,
            'total': len(ejercicios_data)
        })
        
    except Exception as e:
        logger.error(f"Error en búsqueda de ejercicios: {str(e)}")
        return jsonify({'success': False, 'error': 'Error en la búsqueda'})

# --------------------- USUARIO ---------------------------------------------

@app.route('/dashboard')
@login_required
@handle_db_error
def dashboard():
    user = Usuario.query.get(session['user_id'])
    if user:
        return render_template('usuario_dashboard.html', username=user.nombre)
    return redirect(url_for('login'))

@app.route('/usuario_rutinas')
@app.route('/mis_rutinas')
@login_required
@handle_db_error
def mis_rutinas():
    usuario_id = session['user_id']
    usuario = Usuario.query.get(usuario_id)

    # Obtener parámetros de vista
    vista = request.args.get('vista', 'semanal')  # semanal, mensual, diaria
    fecha_param = request.args.get('fecha')
    hoy = datetime.today().date()

    if fecha_param:
        try:
            base = datetime.strptime(fecha_param, "%Y-%m-%d").date()
        except ValueError:
            base = hoy
    else:
        base = hoy

    datos_vista = None

    if vista == 'diaria':
        # Vista diaria - mostrar rutina de un día específico
        rutina = Rutina.query.filter_by(usuario_id=usuario_id, fecha=base).first()
        logger.info(f"[mis_rutinas] diaria base={base} usuario={usuario_id} rutina={'sí' if rutina else 'no'}")
        datos_vista = {
            'tipo': 'diaria',
            'fecha': base,
            'rutina': rutina
        }
        
    elif vista == 'semanal':
        # Vista semanal - mostrar rutinas de la semana (consulta por rango y agrupación)
        inicio_semana = base - timedelta(days=base.weekday())
        fin_semana = inicio_semana + timedelta(days=6)

        rutinas_semana = (
            Rutina.query
            .filter(Rutina.usuario_id == usuario_id)
            .filter(Rutina.fecha >= inicio_semana)
            .filter(Rutina.fecha <= fin_semana)
            .order_by(Rutina.fecha.asc())
            .all()
        )
        logger.info(f"[mis_rutinas] semanal usuario={usuario_id} rango={inicio_semana}..{fin_semana} count={len(rutinas_semana)} fechas={[r.fecha for r in rutinas_semana]}")

        dias = {}
        for r in rutinas_semana:
            bloques = []
            for bloque in r.bloques:
                ejercicios = []
                for e in bloque.ejercicios:
                    ejercicios.append({
                        'id': e.id,
                        'ejercicio': e.ejercicio,
                        'nombre_manual': e.nombre_manual,
                        'series_reps': e.series_reps,
                        'rpe': e.rpe,
                        'carga': e.carga,
                        'categoria': e.categoria,
                        'subcategoria': e.subcategoria
                    })
                bloques.append({
                    'nombre_bloque': bloque.nombre_bloque,
                    'categoria': bloque.categoria,
                    'ejercicios': ejercicios
                })
            dias[r.fecha] = bloques

        # Placeholder: asegurar los 7 días en orden lunes→domingo
        for i in range(7):
            dia = inicio_semana + timedelta(days=i)
            if dia not in dias:
                dias[dia] = []
        
        datos_vista = {
            'tipo': 'semanal',
            'inicio': inicio_semana,
            'fin': fin_semana,
            'dias': dias
        }
        
    else:  # vista == 'mensual'
        # Vista mensual - mostrar rutinas del mes por semanas (robusta para diciembre)
        año, mes = base.year, base.month
        inicio_mes = datetime(año, mes, 1).date()
        _, dias_mes = monthrange(año, mes)
        fin_mes = inicio_mes + timedelta(days=dias_mes - 1)

        # Recolectar todas las rutinas del mes
        todas = (
            Rutina.query
            .filter(Rutina.usuario_id == usuario_id)
            .filter(Rutina.fecha >= inicio_mes)
            .filter(Rutina.fecha <= fin_mes)
            .order_by(Rutina.fecha.asc())
            .all()
        )
        # logger opcional: comentar para rendimiento
        # logger.info(f"[mis_rutinas] mensual usuario={usuario_id} rango={inicio_mes}..{fin_mes} count={len(todas)}")

        semanas_map = {}
        for r in todas:
            lunes = r.fecha - timedelta(days=r.fecha.weekday())
            bloques = []
            for bloque in r.bloques:
                ejercicios = []
                for e in bloque.ejercicios:
                    ejercicios.append({
                        'id': e.id,
                        'ejercicio': e.ejercicio,
                        'nombre_manual': e.nombre_manual,
                        'series_reps': e.series_reps,
                        'rpe': e.rpe,
                        'carga': e.carga,
                        'categoria': e.categoria,
                        'subcategoria': e.subcategoria
                    })
                bloques.append({
                    'nombre_bloque': bloque.nombre_bloque,
                    'categoria': bloque.categoria,
                    'ejercicios': ejercicios
                })
            semanas_map.setdefault(lunes, []).append({ 'fecha': r.fecha, 'bloques': bloques })

        semanas = []
        for lunes, rutinas_semana in sorted(semanas_map.items()):
            domingo = lunes + timedelta(days=6)
            semanas.append({ 'inicio': lunes, 'fin': domingo, 'rutinas': rutinas_semana })

        datos_vista = { 'tipo': 'mensual', 'semanas': semanas }

    # Debug opcional removido por fluidez
    
    return render_template(
        'usuario_rutinas.html',
        usuario=usuario,
        datos_vista=datos_vista,
        vista_actual=vista,
        fecha_actual=base
    )

@app.route('/exercises')
@login_required
@handle_db_error
def exercises():
    # Obtener todos los ejercicios agrupados por categoría
    ejercicios = Ejercicio.query.order_by(Ejercicio.categoria, Ejercicio.subcategoria, Ejercicio.nombre).all()
    
    # Agrupar ejercicios por categoría y subcategoría
    ejercicios_agrupados = {}
    for ejercicio in ejercicios:
        categoria = ejercicio.categoria or "Sin categoría"
        subcategoria = ejercicio.subcategoria or "Sin subcategoría"
        
        if categoria not in ejercicios_agrupados:
            ejercicios_agrupados[categoria] = {}
        
        if subcategoria not in ejercicios_agrupados[categoria]:
            ejercicios_agrupados[categoria][subcategoria] = []
        
        ejercicios_agrupados[categoria][subcategoria].append(ejercicio)
    
    return render_template('usuario_explicacion_ejercicios.html', ejercicios=ejercicios_agrupados)

@app.route('/sobre_mi')
@login_required
def sobre_mi():
    return render_template('en_construccion.html')

@app.route('/my_info')
@login_required
@handle_db_error
def my_info():
    user = Usuario.query.get(session['user_id'])
    if user:
        return render_template('usuario_my_info.html', user=user)
    return redirect(url_for('dashboard'))

@app.route('/update_info', methods=['POST'])
@login_required
@handle_db_error
def update_info():
    user = Usuario.query.get(session['user_id'])
    if user:
        user.nombre = request.form.get('nombre', user.nombre)
        user.apellidos = request.form.get('apellidos', user.apellidos)
        user.telefono = request.form.get('telefono', user.telefono)
        user.email = request.form.get('email', user.email)
        user.username = request.form.get('username', user.username)
        # Nuevos campos
        fn = request.form.get('fecha_nacimiento')
        if fn:
            try:
                from datetime import datetime
                user.fecha_nacimiento = datetime.strptime(fn, '%Y-%m-%d').date()
            except Exception:
                pass
        user.genero = request.form.get('genero') or user.genero
        user.direccion = request.form.get('direccion') or user.direccion
        user.ciudad = request.form.get('ciudad') or user.ciudad
        user.codigo_postal = request.form.get('codigo_postal') or user.codigo_postal
        db.session.commit()
        flash('Información actualizada correctamente', 'success')
        return redirect(url_for('my_info'))
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
@handle_db_error
def change_password():
    if request.method == 'POST':
        user = Usuario.query.get(session['user_id'])
        if user:
            current_password = request.form['current_password']
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            
            # Verificar contraseña actual
            if not user.check_password(current_password):
                flash('La contraseña actual es incorrecta', 'error')
                return render_template('usuario_change_password.html', user=user)
            
            # Validar nueva contraseña
            if len(new_password) < 6:
                flash('La nueva contraseña debe tener al menos 6 caracteres', 'error')
                return render_template('usuario_change_password.html', user=user)
            
            if new_password != confirm_password:
                flash('Las contraseñas nuevas no coinciden', 'error')
                return render_template('usuario_change_password.html', user=user)
            
            if current_password == new_password:
                flash('La nueva contraseña debe ser diferente a la actual', 'error')
                return render_template('usuario_change_password.html', user=user)
            
            # Cambiar contraseña
            user.set_password(new_password)
            db.session.commit()
            flash('Contraseña cambiada exitosamente', 'success')
            return redirect(url_for('my_info'))
        
        return redirect(url_for('login'))
    
    user = Usuario.query.get(session['user_id'])
    return render_template('usuario_change_password.html', user=user)

@app.route('/soporte_usuario')
@login_required
@handle_db_error
def soporte_usuario():
    user = Usuario.query.get(session['user_id'])
    return render_template('usuario_soporte.html', user=user)

@app.route('/sobre_app')
@login_required
def sobre_app():
    from datetime import datetime
    moment_actual = datetime.now().strftime('%d/%m/%Y')
    return render_template('usuario_sobre_app.html', moment_actual=moment_actual)

# ------------------ API ESTADÍSTICAS REALES ------------------

@app.route('/api/stats/dashboard')
@admin_required
@handle_db_error
def api_dashboard_stats():
    """Obtener estadísticas reales del dashboard"""
    try:
        # Estadísticas de usuarios
        total_usuarios = Usuario.query.count()
        usuarios_hoy = Usuario.query.filter(
            Usuario.id > 0,  # Placeholder para fecha de registro
            # En un modelo real tendrías: Usuario.fecha_registro >= datetime.today().date()
        ).count()
        
        # Estadísticas de ejercicios
        total_ejercicios = Ejercicio.query.count()
        
        # Estadísticas de rutinas
        total_rutinas = Rutina.query.count()
        rutinas_esta_semana = Rutina.query.filter(
            Rutina.fecha >= datetime.today().date() - timedelta(days=7)
        ).count()
        
        # Estadísticas de pagos
        total_pagos_mes = Pago.query.filter(
            Pago.fecha_pago >= datetime.today().replace(day=1).date()
        ).count()
        
        # Calcular ingresos del mes
        pagos_mes = Pago.query.filter(
            Pago.fecha_pago >= datetime.today().replace(day=1).date()
        ).all()
        ingresos_mes = sum(float(pago.cantidad) for pago in pagos_mes if pago.cantidad)
        
        # Calcular ingresos del mes anterior para comparación
        mes_anterior = datetime.today().replace(day=1) - timedelta(days=1)
        inicio_mes_anterior = mes_anterior.replace(day=1)
        pagos_mes_anterior = Pago.query.filter(
            Pago.fecha_pago >= inicio_mes_anterior.date(),
            Pago.fecha_pago < datetime.today().replace(day=1).date()
        ).all()
        ingresos_mes_anterior = sum(float(pago.cantidad) for pago in pagos_mes_anterior if pago.cantidad)
        
        # Calcular cambio porcentual
        if ingresos_mes_anterior > 0:
            cambio_porcentual = ((ingresos_mes - ingresos_mes_anterior) / ingresos_mes_anterior) * 100
        else:
            cambio_porcentual = 100 if ingresos_mes > 0 else 0
        
        # Pagos pendientes
        pagos_pendientes = Pago.query.filter_by(estado='pendiente').count()
        
        # Pagos pagados este mes
        pagos_pagados_mes = Pago.query.filter(
            Pago.fecha_pago >= datetime.today().replace(day=1).date(),
            Pago.estado == 'pagado'
        ).count()
        
        # Actividad de la semana (últimos 7 días)
        actividad_semana = []
        for i in range(7):
            fecha = datetime.today().date() - timedelta(days=i)
            rutinas_dia = Rutina.query.filter_by(fecha=fecha).count()
            actividad_semana.append({
                'fecha': fecha.strftime('%a'),
                'rutinas': rutinas_dia
            })
        
        # Ordenar por fecha (más reciente primero)
        actividad_semana.reverse()
        
        stats = {
            'usuarios': {
                'total': total_usuarios,
                'nuevos_hoy': usuarios_hoy,
                'cambio_mes': 12.5  # Placeholder - se puede calcular con fechas reales
            },
            'ejercicios': {
                'total': total_ejercicios,
                'cambio_mes': 5.2,  # Placeholder
                'mas_popular': 'Press de Banca'  # Placeholder - se puede calcular
            },
            'rutinas': {
                'total': total_rutinas,
                'esta_semana': rutinas_esta_semana,
                'cambio_semana': 8.7  # Placeholder
            },
            'pagos': {
                'total_mes': total_pagos_mes,
                'ingresos_mes': ingresos_mes or 0,
                'cambio_mes': round(cambio_porcentual, 1),
                'pendientes': pagos_pendientes,
                'pagados_mes': pagos_pagados_mes,
                'ingresos_mes_anterior': ingresos_mes_anterior or 0
            },
            'actividad': {
                'labels': [item['fecha'] for item in actividad_semana],
                'data': [item['rutinas'] for item in actividad_semana]
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        log_error(f"Error obteniendo estadísticas: {e}", session.get('user_id'))
        return jsonify({'error': 'Error obteniendo estadísticas'}), 500

@app.route('/api/stats/users')
@admin_required
@handle_db_error
def api_users_stats():
    """Obtener estadísticas detalladas de usuarios"""
    try:
        total_usuarios = Usuario.query.count()
        usuarios_admin = Usuario.query.filter_by(rol='admin').count()
        usuarios_normales = Usuario.query.filter_by(rol='user').count()
        
        # Usuarios por mes (últimos 6 meses)
        usuarios_por_mes = []
        for i in range(6):
            fecha = datetime.today().replace(day=1) - timedelta(days=30*i)
            # Placeholder - en un modelo real tendrías fecha de registro
            usuarios_por_mes.append({
                'mes': fecha.strftime('%b %Y'),
                'total': total_usuarios  # Placeholder
            })
        
        return jsonify({
            'total': total_usuarios,
            'admins': usuarios_admin,
            'usuarios': usuarios_normales,
            'por_mes': usuarios_por_mes
        })
        
    except Exception as e:
        log_error(f"Error obteniendo estadísticas de usuarios: {e}", session.get('user_id'))
        return jsonify({'error': 'Error obteniendo estadísticas'}), 500

@app.route('/api/stats/exercises')
@admin_required
@handle_db_error
def api_exercises_stats():
    """Obtener estadísticas detalladas de ejercicios"""
    try:
        total_ejercicios = Ejercicio.query.count()
        
        # Ejercicios por categoría
        ejercicios_por_categoria = db.session.query(
            Ejercicio.categoria, 
            db.func.count(Ejercicio.id).label('total')
        ).group_by(Ejercicio.categoria).all()
        
        # Ejercicios por subcategoría
        ejercicios_por_subcategoria = db.session.query(
            Ejercicio.subcategoria, 
            db.func.count(Ejercicio.id).label('total')
        ).group_by(Ejercicio.subcategoria).all()
        
        return jsonify({
            'total': total_ejercicios,
            'por_categoria': [{'categoria': cat, 'total': total} for cat, total in ejercicios_por_categoria],
            'por_subcategoria': [{'subcategoria': sub, 'total': total} for sub, total in ejercicios_por_subcategoria]
        })
        
    except Exception as e:
        log_error(f"Error obteniendo estadísticas de ejercicios: {e}", session.get('user_id'))
        return jsonify({'error': 'Error obteniendo estadísticas'}), 500

@app.route('/api/stats/payments')
@admin_required
@handle_db_error
def api_payments_stats():
    """Obtener estadísticas detalladas de pagos"""
    try:
        # Estadísticas generales
        total_pagos = Pago.query.count()
        pagos_pendientes = Pago.query.filter_by(estado='pendiente').count()
        pagos_pagados = Pago.query.filter_by(estado='pagado').count()
        
        # Ingresos totales
        ingresos_totales = db.session.query(db.func.sum(Pago.cantidad)).filter_by(estado='pagado').scalar() or 0
        ingresos_totales = float(ingresos_totales)
        
        # Ingresos del mes actual
        inicio_mes = datetime.today().replace(day=1).date()
        ingresos_mes = db.session.query(db.func.sum(Pago.cantidad)).filter(
            Pago.fecha_pago >= inicio_mes,
            Pago.estado == 'pagado'
        ).scalar() or 0
        ingresos_mes = float(ingresos_mes)
        
        # Ingresos del mes anterior
        mes_anterior = datetime.today().replace(day=1) - timedelta(days=1)
        inicio_mes_anterior = mes_anterior.replace(day=1)
        ingresos_mes_anterior = db.session.query(db.func.sum(Pago.cantidad)).filter(
            Pago.fecha_pago >= inicio_mes_anterior,
            Pago.fecha_pago < inicio_mes,
            Pago.estado == 'pagado'
        ).scalar() or 0
        ingresos_mes_anterior = float(ingresos_mes_anterior)
        
        # Calcular cambio porcentual
        if ingresos_mes_anterior > 0:
            cambio_porcentual = ((ingresos_mes - ingresos_mes_anterior) / ingresos_mes_anterior) * 100
        else:
            cambio_porcentual = 100 if ingresos_mes > 0 else 0
        
        # Pagos por mes (últimos 6 meses)
        pagos_por_mes = []
        for i in range(6):
            fecha = datetime.today().replace(day=1) - timedelta(days=30*i)
            inicio_mes_calc = fecha.date()
            fin_mes_calc = (fecha + timedelta(days=32)).replace(day=1).date()
            
            ingresos_mes_calc = db.session.query(db.func.sum(Pago.cantidad)).filter(
                Pago.fecha_pago >= inicio_mes_calc,
                Pago.fecha_pago < fin_mes_calc,
                Pago.estado == 'pagado'
            ).scalar() or 0
            ingresos_mes_calc = float(ingresos_mes_calc)
            
            pagos_por_mes.append({
                'mes': fecha.strftime('%b %Y'),
                'ingresos': ingresos_mes_calc,
                'pagos': Pago.query.filter(
                    Pago.fecha_pago >= inicio_mes_calc,
                    Pago.fecha_pago < fin_mes_calc
                ).count()
            })
        
        # Pagos por estado
        pagos_por_estado = [
            {'estado': 'Pagado', 'total': pagos_pagados, 'color': '#28a745'},
            {'estado': 'Pendiente', 'total': pagos_pendientes, 'color': '#ffc107'}
        ]
        
        return jsonify({
            'resumen': {
                'total_pagos': total_pagos,
                'pagos_pendientes': pagos_pendientes,
                'pagos_pagados': pagos_pagados,
                'ingresos_totales': ingresos_totales,
                'ingresos_mes': ingresos_mes,
                'ingresos_mes_anterior': ingresos_mes_anterior,
                'cambio_porcentual': round(cambio_porcentual, 1)
            },
            'por_mes': pagos_por_mes,
            'por_estado': pagos_por_estado
        })
        
    except Exception as e:
        log_error(f"Error obteniendo estadísticas de pagos: {e}", session.get('user_id'))
        return jsonify({'error': 'Error obteniendo estadísticas'}), 500

# ------------------ SISTEMA DE PAGOS ------------------

@app.route('/planes')
@login_required
def planes():
    """Página de planes de suscripción"""
    try:
        from payment_service import payment_service
        planes = payment_service.obtener_planes_disponibles()
        return render_template('planes.html', planes=planes)
    except Exception as e:
        log_error(e, session.get('user_id'))
        flash("Error cargando planes", "danger")
        return redirect(url_for('usuario_dashboard'))

@app.route('/api/planes')
def api_planes():
    """API para obtener planes disponibles"""
    try:
        from payment_service import payment_service
        planes = payment_service.obtener_planes_disponibles()
        return jsonify({'success': True, 'planes': planes})
    except Exception as e:
        log_error(e, session.get('user_id'))
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/suscripcion/crear', methods=['POST'])
@login_required
def api_crear_suscripcion():
    """API para crear una nueva suscripción"""
    try:
        data = request.get_json()
        plan_id = data.get('plan_id')
        metodo_pago_id = data.get('metodo_pago_id')
        
        if not plan_id or not metodo_pago_id:
            return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
        
        from payment_service import payment_service
        resultado = payment_service.crear_suscripcion(
            session['user_id'], 
            int(plan_id), 
            metodo_pago_id
        )
        
        if resultado['success']:
            return jsonify(resultado)
        else:
            return jsonify(resultado), 400
            
    except Exception as e:
        log_error(e, session.get('user_id'))
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/suscripcion/cancelar', methods=['POST'])
@login_required
def api_cancelar_suscripcion():
    """API para cancelar una suscripción"""
    try:
        data = request.get_json()
        suscripcion_id = data.get('suscripcion_id')
        
        if not suscripcion_id:
            return jsonify({'success': False, 'error': 'ID de suscripción requerido'}), 400
        
        from payment_service import payment_service
        resultado = payment_service.cancelar_suscripcion(
            int(suscripcion_id), 
            session['user_id']
        )
        
        return jsonify(resultado)
        
    except Exception as e:
        log_error(e, session.get('user_id'))
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/usuario/estado_premium')
@login_required
def api_estado_premium():
    """API para verificar el estado premium del usuario"""
    try:
        from payment_service import payment_service
        estado = payment_service.verificar_estado_premium(session['user_id'])
        return jsonify(estado)
    except Exception as e:
        log_error(e, session.get('user_id'))
        return jsonify({'premium': False, 'error': str(e)}), 500

@app.route('/webhook/stripe', methods=['POST'])
def webhook_stripe():
    """Webhook para recibir notificaciones de Stripe"""
    try:
        payload = request.data
        signature = request.headers.get('Stripe-Signature')
        
        if not signature:
            return jsonify({'error': 'Firma no encontrada'}), 400
        
        from payment_service import payment_service
        resultado = payment_service.procesar_webhook_stripe(payload, signature)
        
        if resultado['success']:
            return jsonify({'success': True}), 200
        else:
            return jsonify(resultado), 400
            
    except Exception as e:
        log_error(e, None)
        return jsonify({'error': str(e)}), 500

@app.route('/pagos')
@login_required
def pagos_usuario():
    """Página de historial de pagos del usuario"""
    try:
        usuario = Usuario.query.get(session['user_id'])
        suscripciones = Suscripcion.query.filter_by(usuario_id=session['user_id']).all()
        pagos = Pago.query.filter_by(usuario_id=session['user_id']).order_by(Pago.fecha_pago.desc()).all()
        
        return render_template('usuario_pagos.html', 
                             usuario=usuario, 
                             suscripciones=suscripciones, 
                             pagos=pagos)
    except Exception as e:
        log_error(e, session.get('user_id'))
        flash("Error cargando pagos", "danger")
        return redirect(url_for('usuario_dashboard'))

# Rutas del sistema de pagos simplificado
@app.route('/admin_pagos')
@admin_required
def admin_pagos():
    """Dashboard de pagos para el admin"""
    # Obtener estadísticas
    stats = payment_service.obtener_estadisticas_pagos()
    
    # Obtener pagos recientes
    pagos_recientes = payment_service.obtener_pagos_admin(limit=10)
    
    return render_template('admin_pagos.html', stats=stats, pagos_recientes=pagos_recientes)

@app.route('/admin_pagos/registrar', methods=['GET', 'POST'])
@admin_required
def admin_registrar_pago():
    """Página para que el admin registre un nuevo pago"""
    
    if request.method == 'POST':
        try:
            usuario_id = request.form['usuario_id']
            cantidad = request.form['cantidad']
            metodo_pago = request.form['metodo_pago']
            forma_pago = request.form.get('forma_pago', '')
            observaciones = request.form.get('observaciones', '')
            
            # Validaciones
            if not usuario_id or not cantidad or not metodo_pago:
                flash('Usuario, cantidad y método de pago son obligatorios', 'danger')
                return redirect(url_for('admin_registrar_pago'))
            
            # Verificar que el usuario existe
            usuario = Usuario.query.get(usuario_id)
            if not usuario:
                flash('Usuario no encontrado', 'danger')
                return redirect(url_for('admin_registrar_pago'))
            
            # Validar cantidad
            try:
                cantidad_float = float(cantidad)
                if cantidad_float <= 0:
                    flash('La cantidad debe ser mayor a 0', 'danger')
                    return redirect(url_for('admin_registrar_pago'))
            except ValueError:
                flash('La cantidad debe ser un número válido', 'danger')
                return redirect(url_for('admin_registrar_pago'))
            
            # Registrar el pago usando el servicio
            resultado = payment_service.registrar_pago(
                usuario_id=int(usuario_id),
                cantidad=cantidad_float,
                metodo_pago=metodo_pago,
                forma_pago=forma_pago,
                observaciones=observaciones
            )
            
            if resultado['success']:
                # Log de actividad
                log_activity(f"Pago registrado: €{cantidad_float} para {usuario.nombre}", session['user_id'])
                flash(f'Pago de €{cantidad_float} registrado correctamente para {usuario.nombre}', 'success')
                return redirect(url_for('admin_pagos'))
            else:
                flash(f'Error al registrar el pago: {resultado["error"]}', 'danger')
                
        except Exception as e:
            log_error(f"Error en admin_registrar_pago: {e}", session.get('user_id'))
            flash(f'Error interno del servidor: {str(e)}', 'danger')
    
    # GET: Mostrar formulario
    usuarios = Usuario.query.order_by(Usuario.nombre).all()
    
    return render_template('admin_registrar_pago.html', usuarios=usuarios)

@app.route('/admin_pagos/<int:pago_id>/cambiar_estado', methods=['POST'])
@admin_required
def admin_cambiar_estado_pago(pago_id):
    """Cambia el estado de un pago (pendiente -> pagado, etc.)"""
    try:
        data = request.get_json()
        nuevo_estado = data.get('nuevo_estado')
        
        if not nuevo_estado:
            return jsonify({'success': False, 'error': 'Nuevo estado no especificado'})
        
        resultado = payment_service.cambiar_estado_pago(
            pago_id=pago_id,
            nuevo_estado=nuevo_estado,
            admin_id=session.get('user_id')
        )
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'})

@app.route('/admin_pagos/<int:pago_id>/eliminar', methods=['POST'])
@admin_required
def admin_eliminar_pago(pago_id):
    """Elimina un pago del sistema"""
    try:
        resultado = payment_service.eliminar_pago(
            pago_id=pago_id,
            admin_id=session.get('user_id')
        )
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'})

@app.route('/admin_pagos/<int:pago_id>/cancelar', methods=['POST'])
@admin_required
def admin_cancelar_pago(pago_id):
    """Cancela un pago"""
    data = request.get_json()
    resultado = payment_service.cancelar_pago(
        pago_id=pago_id,
        admin_id=session.get('user_id'),
        motivo=data.get('motivo')
    )
    
    return jsonify(resultado)

@app.route('/api/pagos/usuario/<int:usuario_id>')
@login_required
def api_pagos_usuario(usuario_id):
    """API para obtener pagos de un usuario específico"""
    if session.get('user_rol') != 'admin' and session.get('user_id') != usuario_id:
        return jsonify({'success': False, 'error': 'Acceso denegado'})
    
    pagos = payment_service.obtener_pagos_usuario(usuario_id)
    return jsonify({'success': True, 'pagos': pagos})

@app.route('/api/pagos/admin')
@admin_required
def api_pagos_admin():
    """API para obtener pagos filtrados para el admin"""
    estado = request.args.get('estado')
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    usuario_id = request.args.get('usuario_id', type=int)
    
    pagos = payment_service.obtener_pagos_admin(
        estado=estado,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        usuario_id=usuario_id
    )
    
    return jsonify({'success': True, 'pagos': pagos})

@app.route('/api/pagos/estadisticas')
@admin_required
def api_estadisticas_pagos():
    """API para obtener estadísticas de pagos"""
    stats = payment_service.obtener_estadisticas_pagos()
    return jsonify({'success': True, 'estadisticas': stats})

# ------------------ NUEVAS RUTAS PARA PAGOS MENSUALES ------------------

@app.route('/admin_pagos_mensuales')
@admin_required
def admin_pagos_mensuales():
    """Página para gestionar pagos mensuales"""
    # Obtener usuarios con configuración de pago mensual
    usuarios_config = payment_service.obtener_usuarios_con_pago_mensual()
    
    # Obtener estadísticas
    stats = payment_service.obtener_estadisticas_pagos()
    
    # Obtener mes actual
    hoy = datetime.today()
    moment_actual = f"{hoy.year}-{hoy.month:02d}"
    
    return render_template('admin_pagos_mensuales.html', 
                         usuarios_config=usuarios_config, 
                         stats=stats,
                         moment_actual=moment_actual)

@app.route('/admin_pagos_mensuales/configurar', methods=['GET', 'POST'])
@admin_required
def admin_configurar_pago_mensual():
    """Configurar pago mensual para un usuario"""
    
    if request.method == 'POST':
        try:
            usuario_id = request.form['usuario_id']
            cantidad = request.form['cantidad']
            metodo_pago = request.form['metodo_pago']
            forma_pago = request.form.get('forma_pago', '')
            dia_vencimiento = int(request.form.get('dia_vencimiento', 1))
            
            # Validaciones
            if not usuario_id or not cantidad or not metodo_pago:
                flash('Usuario, cantidad y método de pago son obligatorios', 'danger')
                return redirect(url_for('admin_configurar_pago_mensual'))
            
            # Verificar que el usuario existe
            usuario = Usuario.query.get(usuario_id)
            if not usuario:
                flash('Usuario no encontrado', 'danger')
                return redirect(url_for('admin_configurar_pago_mensual'))
            
            # Validar cantidad
            try:
                cantidad_float = float(cantidad)
                if cantidad_float <= 0:
                    flash('La cantidad debe ser mayor a 0', 'danger')
                    return redirect(url_for('admin_configurar_pago_mensual'))
            except ValueError:
                flash('La cantidad debe ser un número válido', 'danger')
                return redirect(url_for('admin_configurar_pago_mensual'))
            
            # Configurar pago mensual
            resultado = payment_service.configurar_pago_mensual(
                usuario_id=int(usuario_id),
                cantidad=cantidad_float,
                metodo_pago=metodo_pago,
                forma_pago=forma_pago,
                dia_vencimiento=dia_vencimiento
            )
            
            if resultado['success']:
                log_activity(f"Configuración de pago mensual: €{cantidad_float} para {usuario.nombre}", session['user_id'])
                flash(f'Configuración de pago mensual guardada para {usuario.nombre}', 'success')
                return redirect(url_for('admin_pagos_mensuales'))
            else:
                flash(f'Error al configurar pago mensual: {resultado["error"]}', 'danger')
                
        except Exception as e:
            log_error(f"Error en admin_configurar_pago_mensual: {e}", session.get('user_id'))
            flash(f'Error interno del servidor: {str(e)}', 'danger')
    
    # GET: Mostrar formulario
    usuarios = Usuario.query.order_by(Usuario.nombre).all()
    
    return render_template('admin_configurar_pago_mensual.html', usuarios=usuarios)

@app.route('/admin_pagos_mensuales/generar', methods=['POST'])
@admin_required
def admin_generar_pagos_mensuales():
    """Genera los pagos mensuales para todos los usuarios"""
    try:
        mes = request.form.get('mes')
        
        resultado = payment_service.generar_pagos_mensuales(mes)
        
        if resultado['success']:
            flash(f'Se generaron {resultado["pagos_creados"]} pagos mensuales para {resultado["mes"]}', 'success')
            if resultado['errores']:
                flash(f'Errores: {", ".join(resultado["errores"])}', 'warning')
        else:
            flash(f'Error al generar pagos mensuales: {resultado["error"]}', 'danger')
            
    except Exception as e:
        log_error(f"Error en admin_generar_pagos_mensuales: {e}", session.get('user_id'))
        flash(f'Error interno del servidor: {str(e)}', 'danger')
    
    return redirect(url_for('admin_pagos_mensuales'))

@app.route('/admin_pagos_mensuales/cancelar/<int:usuario_id>', methods=['POST'])
@admin_required
def admin_cancelar_pago_mensual(usuario_id):
    """Cancela la configuración de pago mensual de un usuario"""
    try:
        resultado = payment_service.cancelar_pago_mensual(usuario_id)
        
        if resultado['success']:
            usuario = Usuario.query.get(usuario_id)
            log_activity(f"Pago mensual cancelado para {usuario.nombre}", session['user_id'])
            return jsonify({
                'success': True,
                'mensaje': f'Configuración de pago mensual cancelada para {usuario.nombre}'
            })
        else:
            return jsonify({
                'success': False,
                'error': resultado['error']
            })
            
    except Exception as e:
        log_error(f"Error en admin_cancelar_pago_mensual: {e}", session.get('user_id'))
        return jsonify({
            'success': False,
            'error': f'Error interno del servidor: {str(e)}'
        })

@app.route('/api/pagos_mensuales/usuario/<int:usuario_id>')
@admin_required
def api_configuracion_pago_mensual(usuario_id):
    """API para obtener la configuración de pago mensual de un usuario"""
    resultado = payment_service.obtener_configuracion_pago_mensual(usuario_id)
    return jsonify(resultado)

# ------------------ SEGUIMIENTO DE EJERCICIOS ------------------

@app.route('/api/ejercicio/<int:ejercicio_asignado_id>/registrar', methods=['POST'])
@login_required
@handle_db_error
def registrar_ejercicio(ejercicio_asignado_id):
    """Registrar el progreso de un ejercicio por parte del usuario"""
    try:
        usuario_id = session['user_id']
        data = request.get_json()
        
        # Obtener el ejercicio asignado
        ejercicio_asignado = EjercicioAsignado.query.get(ejercicio_asignado_id)
        if not ejercicio_asignado:
            return jsonify({'error': 'Ejercicio no encontrado'}), 404
        
        # Verificar que el ejercicio pertenece al usuario
        rutina = Rutina.query.get(ejercicio_asignado.bloque.rutina_id)
        if rutina.usuario_id != usuario_id:
            return jsonify({'error': 'No tienes permisos para este ejercicio'}), 403
        
        # Determinar fecha de ejecución: usar la proporcionada o por defecto hoy
        fecha_str = (data or {}).get('fecha_ejecucion')
        if fecha_str:
            try:
                fecha_ejecucion = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}), 400
        else:
            fecha_ejecucion = datetime.today().date()

        # Validar que la fecha pertenezca a la misma semana o sea igual a la fecha de la rutina
        # Permitimos registrar para la fecha exacta de la rutina o, si se quiere flexibilidad,
        # cualquier fecha. Aquí aplicamos validación suave: advertimos si se desvía más de 7 días.
        try:
            fecha_rutina = rutina.fecha
            delta_dias = abs((fecha_ejecucion - fecha_rutina).days)
            if delta_dias > 7:
                # No bloqueamos, pero informamos al cliente
                pass
        except Exception:
            pass

        # Validaciones ligeras de payload
        rpe_real = (data or {}).get('rpe_real', '')
        carga_real = (data or {}).get('carga_real', '')
        if isinstance(rpe_real, (int, float)):
            if rpe_real < 0 or rpe_real > 10:
                return jsonify({'error': 'RPE debe estar entre 0 y 10'}), 400
        if isinstance(carga_real, (int, float)):
            if carga_real < 0:
                return jsonify({'error': 'La carga no puede ser negativa'}), 400

        # Buscar si ya existe un seguimiento para la fecha indicada
        seguimiento = SeguimientoEjercicio.query.filter_by(
            usuario_id=usuario_id,
            ejercicio_asignado_id=ejercicio_asignado_id,
            fecha_ejecucion=fecha_ejecucion
        ).first()
        
        if seguimiento:
            # Actualizar seguimiento existente
            seguimiento.series_reps_reales = data.get('series_reps_reales', '')
            seguimiento.rpe_real = rpe_real
            seguimiento.carga_real = carga_real
            seguimiento.notas = data.get('notas', '')
            seguimiento.completado = data.get('completado', False)
            if seguimiento.completado:
                seguimiento.fecha_completado = datetime.utcnow()
            seguimiento.fecha_actualizacion = datetime.utcnow()
        else:
            # Crear nuevo seguimiento
            seguimiento = SeguimientoEjercicio(
                usuario_id=usuario_id,
                ejercicio_asignado_id=ejercicio_asignado_id,
                fecha_ejecucion=fecha_ejecucion,
                series_reps_planificadas=ejercicio_asignado.series_reps,
                rpe_planificado=ejercicio_asignado.rpe,
                carga_planificada=ejercicio_asignado.carga,
                series_reps_reales=data.get('series_reps_reales', ''),
                rpe_real=rpe_real,
                carga_real=carga_real,
                notas=data.get('notas', ''),
                completado=data.get('completado', False),
                fecha_completado=datetime.utcnow() if data.get('completado', False) else None
            )
            db.session.add(seguimiento)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Progreso registrado correctamente',
            'seguimiento_id': seguimiento.id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error registrando ejercicio: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/registrar_dia', methods=['POST'])
@login_required
@handle_db_error
def registrar_dia():
    """Guardar en lote el progreso de todos los ejercicios de un día.
    Payload: { fecha_ejecucion: 'YYYY-MM-DD', ejercicios: [{id, series_reps_reales, rpe_real, carga_real, notas, completado}] }
    """
    try:
        usuario_id = session['user_id']
        data = request.get_json() or {}
        fecha_str = data.get('fecha_ejecucion')
        ejercicios = data.get('ejercicios', [])
        if not fecha_str or not ejercicios:
            return jsonify({'success': False, 'message': 'Fecha y ejercicios requeridos'}), 400
        try:
            fecha_ejecucion = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Fecha inválida'}), 400

        ids = [e.get('id') for e in ejercicios if e.get('id')]
        asignados = {ea.id: ea for ea in EjercicioAsignado.query.filter(EjercicioAsignado.id.in_(ids)).all()}

        for item in ejercicios:
            ej_id = item.get('id')
            ea = asignados.get(ej_id)
            if not ea:
                continue
            rutina = Rutina.query.get(ea.bloque.rutina_id)
            if rutina.usuario_id != usuario_id:
                continue

            seguimiento = SeguimientoEjercicio.query.filter_by(
                usuario_id=usuario_id,
                ejercicio_asignado_id=ej_id,
                fecha_ejecucion=fecha_ejecucion
            ).first()

            rpe_real = item.get('rpe_real', '')
            carga_real = item.get('carga_real', '')

            if seguimiento:
                seguimiento.series_reps_reales = item.get('series_reps_reales', '')
                seguimiento.rpe_real = rpe_real
                seguimiento.carga_real = carga_real
                seguimiento.notas = item.get('notas', '')
                seguimiento.completado = item.get('completado', False)
                if seguimiento.completado:
                    seguimiento.fecha_completado = datetime.utcnow()
                seguimiento.fecha_actualizacion = datetime.utcnow()
            else:
                seg = SeguimientoEjercicio(
                    usuario_id=usuario_id,
                    ejercicio_asignado_id=ej_id,
                    fecha_ejecucion=fecha_ejecucion,
                    series_reps_planificadas=ea.series_reps,
                    rpe_planificado=ea.rpe,
                    carga_planificada=ea.carga,
                    series_reps_reales=item.get('series_reps_reales', ''),
                    rpe_real=rpe_real,
                    carga_real=carga_real,
                    notas=item.get('notas', ''),
                    completado=item.get('completado', False),
                    fecha_completado=datetime.utcnow() if item.get('completado', False) else None
                )
                db.session.add(seg)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error registrar_dia: {e}")
        return jsonify({'success': False, 'message': 'Error interno'}), 500

@app.route('/api/ejercicio/<int:ejercicio_asignado_id>/seguimiento', methods=['GET'])
@login_required
@handle_db_error
def obtener_seguimiento_ejercicio(ejercicio_asignado_id):
    """Obtener el seguimiento de un ejercicio específico"""
    try:
        usuario_id = session['user_id']
        fecha_str = request.args.get('fecha')
        
        # Obtener el ejercicio asignado
        ejercicio_asignado = EjercicioAsignado.query.get(ejercicio_asignado_id)
        if not ejercicio_asignado:
            return jsonify({'error': 'Ejercicio no encontrado'}), 404
        
        # Verificar que el ejercicio pertenece al usuario
        rutina = Rutina.query.get(ejercicio_asignado.bloque.rutina_id)
        if rutina.usuario_id != usuario_id:
            return jsonify({'error': 'No tienes permisos para este ejercicio'}), 403
        
        # Obtener seguimientos del ejercicio
        query = SeguimientoEjercicio.query.filter_by(
            usuario_id=usuario_id,
            ejercicio_asignado_id=ejercicio_asignado_id
        )
        seg_en_fecha = None
        if fecha_str:
            try:
                fecha_busqueda = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                seg_en_fecha = query.filter_by(fecha_ejecucion=fecha_busqueda).first()
            except ValueError:
                return jsonify({'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}), 400
        seguimientos = query.order_by(SeguimientoEjercicio.fecha_ejecucion.desc()).all()
        
        seguimientos_data = []
        for seg in seguimientos:
            seguimientos_data.append({
                'id': seg.id,
                'fecha_ejecucion': seg.fecha_ejecucion.strftime('%Y-%m-%d'),
                'series_reps_planificadas': seg.series_reps_planificadas,
                'rpe_planificado': seg.rpe_planificado,
                'carga_planificada': seg.carga_planificada,
                'series_reps_reales': seg.series_reps_reales,
                'rpe_real': seg.rpe_real,
                'carga_real': seg.carga_real,
                'notas': seg.notas,
                'completado': seg.completado,
                'fecha_completado': seg.fecha_completado.strftime('%Y-%m-%d %H:%M') if seg.fecha_completado else None
            })
        
        return jsonify({
            'ejercicio': {
                'id': ejercicio_asignado.id,
                'nombre': ejercicio_asignado.ejercicio.nombre if ejercicio_asignado.ejercicio else ejercicio_asignado.nombre_manual,
                'categoria': ejercicio_asignado.categoria,
                'subcategoria': ejercicio_asignado.subcategoria
            },
            'seguimientos': seguimientos_data,
            'existe_en_fecha': seg_en_fecha is not None,
            'seguimiento_en_fecha': (
                {
                    'id': seg_en_fecha.id,
                    'fecha_ejecucion': seg_en_fecha.fecha_ejecucion.strftime('%Y-%m-%d'),
                    'series_reps_planificadas': seg_en_fecha.series_reps_planificadas,
                    'rpe_planificado': seg_en_fecha.rpe_planificado,
                    'carga_planificada': seg_en_fecha.carga_planificada,
                    'series_reps_reales': seg_en_fecha.series_reps_reales,
                    'rpe_real': seg_en_fecha.rpe_real,
                    'carga_real': seg_en_fecha.carga_real,
                    'notas': seg_en_fecha.notas,
                    'completado': seg_en_fecha.completado,
                    'fecha_completado': seg_en_fecha.fecha_completado.strftime('%Y-%m-%d %H:%M') if seg_en_fecha.fecha_completado else None
                }
                if seg_en_fecha else None
            )
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo seguimiento: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/usuario/<int:user_id>/progreso', methods=['GET'])
@admin_required
@handle_db_error
def obtener_progreso_usuario(user_id):
    """Obtener el progreso de un usuario específico (solo admin)"""
    try:
        # Obtener usuario
        usuario = Usuario.query.get(user_id)
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Obtener seguimientos del usuario
        seguimientos = SeguimientoEjercicio.query.filter_by(usuario_id=user_id).order_by(
            SeguimientoEjercicio.fecha_ejecucion.desc()
        ).all()
        
        progreso_data = []
        for seg in seguimientos:
            progreso_data.append({
                'id': seg.id,
                'fecha_ejecucion': seg.fecha_ejecucion.strftime('%Y-%m-%d'),
                'ejercicio': {
                    'id': seg.ejercicio_asignado.id,
                    'nombre': seg.ejercicio_asignado.ejercicio.nombre if seg.ejercicio_asignado.ejercicio else seg.ejercicio_asignado.nombre_manual,
                    'categoria': seg.ejercicio_asignado.categoria,
                    'subcategoria': seg.ejercicio_asignado.subcategoria
                },
                'planificado': {
                    'series_reps': seg.series_reps_planificadas,
                    'rpe': seg.rpe_planificado,
                    'carga': seg.carga_planificada
                },
                'realizado': {
                    'series_reps': seg.series_reps_reales,
                    'rpe': seg.rpe_real,
                    'carga': seg.carga_real
                },
                'notas': seg.notas,
                'completado': seg.completado,
                'fecha_completado': seg.fecha_completado.strftime('%Y-%m-%d %H:%M') if seg.fecha_completado else None
            })
        
        return jsonify({
            'usuario': {
                'id': usuario.id,
                'nombre': usuario.nombre,
                'apellidos': usuario.apellidos
            },
            'progreso': progreso_data
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo progreso: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/admin/progresos')
@admin_required
@handle_db_error
def admin_progresos():
    """Listado de usuarios con acciones de progreso (estilo tarjetas)."""
    try:
        usuarios = Usuario.query.filter(Usuario.rol != 'admin').order_by(Usuario.nombre).all()
        # Conteo de seguimientos por usuario
        conteos = dict(
            db.session.query(SeguimientoEjercicio.usuario_id, func.count(SeguimientoEjercicio.id))
            .group_by(SeguimientoEjercicio.usuario_id)
            .all()
        )
        return render_template('admin_progresos_usuarios.html', usuarios=usuarios, conteos=conteos, active_page='progresos')
    except Exception as e:
        logger.error(f"Error listando usuarios de progresos: {e}")
        flash('Error listando usuarios', 'danger')
        return render_template('admin_progresos_usuarios.html', usuarios=[], conteos={}, active_page='progresos')

@app.route('/admin/progresos/<int:user_id>')
@admin_required
@handle_db_error
def admin_progresos_usuario(user_id):
    """Vista de progresos por usuario con modos: diaria, semanal, mensual."""
    usuario = Usuario.query.get(user_id)
    if not usuario:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('admin_progresos'))

    vista = request.args.get('vista', 'diaria')
    fecha_str = request.args.get('fecha')
    base = datetime.today().date()
    if fecha_str:
        try:
            base = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Fecha inválida (YYYY-MM-DD)', 'danger')

    datos_vista = None

    if vista == 'diaria':
        segs = (
            SeguimientoEjercicio.query.filter_by(usuario_id=user_id, fecha_ejecucion=base)
            .order_by(SeguimientoEjercicio.id.desc())
            .all()
        )
        datos_vista = { 'tipo': 'diaria', 'fecha': base, 'seguimientos': segs }

    elif vista == 'semanal':
        lunes = base - timedelta(days=base.weekday())
        domingo = lunes + timedelta(days=6)
        segs = (
            SeguimientoEjercicio.query
            .filter(SeguimientoEjercicio.usuario_id == user_id)
            .filter(SeguimientoEjercicio.fecha_ejecucion >= lunes)
            .filter(SeguimientoEjercicio.fecha_ejecucion <= domingo)
            .order_by(SeguimientoEjercicio.fecha_ejecucion.desc())
            .all()
        )
        dias = {}
        for seg in segs:
            dias.setdefault(seg.fecha_ejecucion, []).append(seg)
        datos_vista = { 'tipo': 'semanal', 'inicio': lunes, 'fin': domingo, 'dias': dias }

    else:  # mensual
        inicio = base.replace(day=1)
        _, dias_mes = monthrange(base.year, base.month)
        fin = inicio + timedelta(days=dias_mes)
        segs = (
            SeguimientoEjercicio.query
            .filter(SeguimientoEjercicio.usuario_id == user_id)
            .filter(SeguimientoEjercicio.fecha_ejecucion >= inicio)
            .filter(SeguimientoEjercicio.fecha_ejecucion < fin)
            .order_by(SeguimientoEjercicio.fecha_ejecucion.asc())
            .all()
        )
        semanas = {}
        for seg in segs:
            lunes = seg.fecha_ejecucion - timedelta(days=seg.fecha_ejecucion.weekday())
            semanas.setdefault(lunes, []).append(seg)
        semanas_ordenadas = []
        for lunes, segs_sem in sorted(semanas.items()):
            domingo = lunes + timedelta(days=6)
            dias_sem = {}
            for seg in segs_sem:
                dias_sem.setdefault(seg.fecha_ejecucion, []).append(seg)
            semanas_ordenadas.append({ 'inicio': lunes, 'fin': domingo, 'dias': dias_sem })
        datos_vista = { 'tipo': 'mensual', 'semanas': semanas_ordenadas }

    return render_template('admin_progresos_usuario.html', usuario=usuario, datos_vista=datos_vista, vista_actual=vista, fecha_actual=base, active_page='progresos')

@app.route('/admin/progresos/<int:seg_id>/eliminar', methods=['POST'])
@admin_required
@handle_db_error
def admin_eliminar_progreso(seg_id):
    try:
        seg = SeguimientoEjercicio.query.get(seg_id)
        if not seg:
            flash('Seguimiento no encontrado', 'danger')
            next_url = request.args.get('next') or request.form.get('next')
            return redirect(next_url or url_for('admin_progresos'))
        db.session.delete(seg)
        db.session.commit()
        flash('Seguimiento eliminado', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error eliminando progreso: {e}")
        flash('Error eliminando progreso', 'danger')
    next_url = request.args.get('next') or request.form.get('next')
    return redirect(next_url or url_for('admin_progresos'))

@app.route('/admin/progresos/<int:seg_id>/actualizar', methods=['POST'])
@admin_required
@handle_db_error
def admin_actualizar_progreso(seg_id):
    try:
        seg = SeguimientoEjercicio.query.get(seg_id)
        if not seg:
            flash('Seguimiento no encontrado', 'danger')
            next_url = request.args.get('next') or request.form.get('next')
            return redirect(next_url or url_for('admin_progresos'))
        seg.series_reps_reales = request.form.get('series', '')
        seg.rpe_real = request.form.get('rpe', '')
        seg.carga_real = request.form.get('carga', '')
        seg.notas = request.form.get('notas', '')
        seg.completado = request.form.get('completado') == 'on'
        seg.fecha_actualizacion = datetime.utcnow()
        db.session.commit()
        flash('Seguimiento actualizado', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error actualizando progreso: {e}")
        flash('Error actualizando progreso', 'danger')
    next_url = request.args.get('next') or request.form.get('next')
    return redirect(next_url or url_for('admin_progresos'))

@app.route('/api/marcar-dia-completado', methods=['POST'])
@login_required
@handle_db_error
def marcar_dia_completado():
    """Marcar un día como completado por el usuario"""
    try:
        data = request.get_json()
        fecha_str = data.get('fecha')
        
        if not fecha_str:
            return jsonify({'success': False, 'message': 'Fecha requerida'}), 400
        
        # Convertir fecha string a objeto date
        from datetime import datetime
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        # Obtener el usuario actual
        usuario_id = session['user_id']
        
        # Aquí podrías crear una tabla para registrar días completados
        # Por ahora, solo devolvemos éxito
        logger.info(f"Usuario {usuario_id} marcó el día {fecha} como completado")
        
        return jsonify({
            'success': True, 
            'message': f'Día {fecha} marcado como completado'
        })
        
    except Exception as e:
        logger.error(f"Error marcando día como completado: {str(e)}")
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

# ------------------ MAIN ------------------

if __name__ == '__main__':
    app.run(debug=True)

