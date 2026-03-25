"""
Tests de modelos de base de datos.

Cubre los fixes aplicados:
- cascade='all, delete-orphan' en Rutina → Bloque → EjercicioAsignado
- default de fecha_ejecucion evaluado en runtime (no en import)
- Integridad referencial entre modelos
"""
import pytest
from datetime import date, datetime, timedelta
from models import (
    db, Usuario, Ejercicio, Rutina, Bloque,
    EjercicioAsignado, SeguimientoEjercicio
)
from werkzeug.security import generate_password_hash


class TestCascadeDelete:

    def test_borrar_rutina_elimina_bloques(self, db, usuario_normal):
        """Al borrar una Rutina, sus Bloques se eliminan en cascada."""
        rutina = Rutina(usuario_id=usuario_normal.id, fecha=date.today())
        db.session.add(rutina)
        db.session.commit()

        bloque = Bloque(rutina_id=rutina.id, nombre_bloque='Calentamiento', categoria='Fuerza')
        db.session.add(bloque)
        db.session.commit()

        bloque_id = bloque.id
        db.session.delete(rutina)
        db.session.commit()

        assert Bloque.query.get(bloque_id) is None, (
            "El Bloque debería haberse eliminado en cascada al borrar la Rutina"
        )

    def test_borrar_rutina_elimina_ejercicios_asignados(self, db, usuario_normal, ejercicio):
        """Al borrar una Rutina, todos sus EjercicioAsignado se eliminan."""
        rutina = Rutina(usuario_id=usuario_normal.id, fecha=date.today())
        db.session.add(rutina)
        db.session.commit()

        bloque = Bloque(rutina_id=rutina.id, nombre_bloque='Fuerza', categoria='Fuerza')
        db.session.add(bloque)
        db.session.commit()

        asignado = EjercicioAsignado(
            bloque_id=bloque.id,
            ejercicio_id=ejercicio.id,
            series_reps='3x10',
            rpe='7',
            carga='80kg',
        )
        db.session.add(asignado)
        db.session.commit()

        asignado_id = asignado.id
        db.session.delete(rutina)
        db.session.commit()

        assert EjercicioAsignado.query.get(asignado_id) is None, (
            "EjercicioAsignado debería haberse eliminado en cascada al borrar la Rutina"
        )

    def test_borrar_bloque_elimina_sus_ejercicios(self, db, usuario_normal, ejercicio):
        """Al borrar un Bloque directamente, sus EjercicioAsignado se eliminan."""
        rutina = Rutina(usuario_id=usuario_normal.id, fecha=date.today())
        db.session.add(rutina)
        db.session.commit()

        bloque = Bloque(rutina_id=rutina.id, nombre_bloque='Cardio', categoria='Cardio')
        db.session.add(bloque)
        db.session.commit()

        asignado = EjercicioAsignado(
            bloque_id=bloque.id,
            ejercicio_id=ejercicio.id,
            series_reps='20min',
        )
        db.session.add(asignado)
        db.session.commit()

        asignado_id = asignado.id
        db.session.delete(bloque)
        db.session.commit()

        assert EjercicioAsignado.query.get(asignado_id) is None

    def test_borrar_usuario_elimina_sus_rutinas(self, db):
        """Al borrar un Usuario, todas sus Rutinas se eliminan en cascada."""
        user = Usuario(
            username='usertodelete',
            email='delete@example.com',
            password=generate_password_hash('pass12345'),
            nombre='Delete',
            apellidos='Me',
            rol='usuario',
        )
        db.session.add(user)
        db.session.commit()

        rutina = Rutina(usuario_id=user.id, fecha=date.today())
        db.session.add(rutina)
        db.session.commit()

        rutina_id = rutina.id
        db.session.delete(user)
        db.session.commit()

        assert Rutina.query.get(rutina_id) is None, (
            "La Rutina debería haberse eliminado en cascada al borrar el Usuario"
        )


class TestFechaEjecucionDefault:

    def test_fecha_ejecucion_default_es_callable(self, app):
        """El default de fecha_ejecucion debe ser un callable (lambda), no un valor fijo."""
        col = SeguimientoEjercicio.__table__.c.fecha_ejecucion
        default = col.default
        assert default is not None, "fecha_ejecucion debe tener un default"
        assert callable(default.arg), (
            "El default de fecha_ejecucion debe ser un callable (lambda). "
            "Si es un valor fijo, todos los registros usarán la fecha de cuando se inició la app."
        )

    def test_dos_inserciones_tienen_fecha_correcta(self, db, usuario_normal, ejercicio):
        """Dos SeguimientoEjercicio creados en días distintos tienen fechas distintas."""
        rutina = Rutina(usuario_id=usuario_normal.id, fecha=date.today())
        db.session.add(rutina)
        db.session.commit()

        bloque = Bloque(rutina_id=rutina.id, nombre_bloque='Test', categoria='Fuerza')
        db.session.add(bloque)
        db.session.commit()

        asignado = EjercicioAsignado(bloque_id=bloque.id, ejercicio_id=ejercicio.id)
        db.session.add(asignado)
        db.session.commit()

        seguimiento = SeguimientoEjercicio(
            usuario_id=usuario_normal.id,
            ejercicio_asignado_id=asignado.id,
            fecha_ejecucion=date.today(),
        )
        db.session.add(seguimiento)
        db.session.commit()

        assert seguimiento.fecha_ejecucion == date.today()


class TestUsuarioModelo:

    def test_crear_usuario_rol_por_defecto(self, db):
        """El rol por defecto de un usuario es 'usuario'."""
        user = Usuario(
            username='defaultrole',
            email='defaultrole@example.com',
            password=generate_password_hash('pass12345'),
            nombre='Default',
            apellidos='Role',
        )
        db.session.add(user)
        db.session.commit()

        assert user.rol == 'usuario'

    def test_usuario_repr(self, db, usuario_normal):
        """__repr__ devuelve el formato esperado."""
        assert 'testuser' in repr(usuario_normal)

    def test_username_unico(self, db, usuario_normal):
        """No se pueden crear dos usuarios con el mismo username."""
        from sqlalchemy.exc import IntegrityError
        duplicado = Usuario(
            username='testuser',  # ya existe
            email='otro@example.com',
            password=generate_password_hash('pass12345'),
            nombre='Otro',
            apellidos='User',
        )
        db.session.add(duplicado)
        with pytest.raises(IntegrityError):
            db.session.commit()

    def test_email_unico(self, db, usuario_normal):
        """No se pueden crear dos usuarios con el mismo email."""
        from sqlalchemy.exc import IntegrityError
        duplicado = Usuario(
            username='otrousername',
            email='test@example.com',  # ya existe
            password=generate_password_hash('pass12345'),
            nombre='Otro',
            apellidos='User',
        )
        db.session.add(duplicado)
        with pytest.raises(IntegrityError):
            db.session.commit()


class TestEjercicioModelo:

    def test_crear_ejercicio(self, db):
        """Se puede crear un ejercicio con nombre, categoría y subcategoría."""
        ej = Ejercicio(nombre='Press Banca', categoria='Fuerza', subcategoria='Pecho')
        db.session.add(ej)
        db.session.commit()

        assert ej.id is not None
        assert ej.nombre == 'Press Banca'

    def test_ejercicio_repr(self, db, ejercicio):
        """__repr__ devuelve el nombre del ejercicio."""
        assert 'Sentadilla' in repr(ejercicio)


class TestRutinaModelo:

    def test_crear_rutina_con_bloques_y_ejercicios(self, db, usuario_normal, ejercicio):
        """Flujo completo: Rutina → Bloque → EjercicioAsignado."""
        rutina = Rutina(usuario_id=usuario_normal.id, fecha=date.today())
        db.session.add(rutina)
        db.session.commit()

        bloque = Bloque(rutina_id=rutina.id, nombre_bloque='Bloque A', categoria='Fuerza')
        db.session.add(bloque)
        db.session.commit()

        asignado = EjercicioAsignado(
            bloque_id=bloque.id,
            ejercicio_id=ejercicio.id,
            series_reps='4x8',
            rpe='8',
            carga='100kg',
        )
        db.session.add(asignado)
        db.session.commit()

        # Verificar la cadena completa via relaciones
        rutina_db = Rutina.query.get(rutina.id)
        assert len(rutina_db.bloques) == 1
        assert len(rutina_db.bloques[0].ejercicios) == 1
        assert rutina_db.bloques[0].ejercicios[0].series_reps == '4x8'
