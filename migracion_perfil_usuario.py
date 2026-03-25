#!/usr/bin/env python3
"""
Añade columnas de perfil a la tabla 'usuarios':
- fecha_nacimiento DATE
- genero VARCHAR(20)
- direccion VARCHAR(255)
- ciudad VARCHAR(100)
- codigo_postal VARCHAR(20)
- fecha_registro TIMESTAMP

Seguro de ejecutar con el mismo entorno de la app.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db
from sqlalchemy import text


def column_exists(table: str, column: str) -> bool:
    insp = db.inspect(db.engine)
    cols = [c['name'] for c in insp.get_columns(table)]
    return column in cols


def run_migration():
    with app.app_context():
        dialect = db.engine.dialect.name
        print(f"➡️ Dialecto detectado: {dialect}")

        alters = []
        if not column_exists('usuarios', 'fecha_nacimiento'):
            alters.append("ADD COLUMN fecha_nacimiento DATE")
        if not column_exists('usuarios', 'genero'):
            alters.append("ADD COLUMN genero VARCHAR(20)")
        if not column_exists('usuarios', 'direccion'):
            alters.append("ADD COLUMN direccion VARCHAR(255)")
        if not column_exists('usuarios', 'ciudad'):
            alters.append("ADD COLUMN ciudad VARCHAR(100)")
        if not column_exists('usuarios', 'codigo_postal'):
            alters.append("ADD COLUMN codigo_postal VARCHAR(20)")
        if not column_exists('usuarios', 'fecha_registro'):
            if dialect == 'sqlite':
                # SQLite no soporta DEFAULT NOW() directo en ALTER, se inserta NULL y app rellena
                alters.append("ADD COLUMN fecha_registro TIMESTAMP")
            else:
                alters.append("ADD COLUMN fecha_registro TIMESTAMP")

        if not alters:
            print("✅ No hay cambios: columnas ya existen")
            return

        sql = f"ALTER TABLE usuarios {' , '.join(alters)};"
        print(f"Ejecutando: {sql}")
        with db.engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        print("✅ Migración aplicada correctamente")


if __name__ == '__main__':
    run_migration()


