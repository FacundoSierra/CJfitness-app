#!/usr/bin/env python3
"""
Script de migración para añadir índices y unicidad a seguimiento_ejercicios.

Aplica:
- UNIQUE (usuario_id, ejercicio_asignado_id, fecha_ejecucion)
- INDEX (usuario_id, fecha_ejecucion)
- INDEX (ejercicio_asignado_id, fecha_ejecucion)

Compatible con PostgreSQL y SQLite.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db
from sqlalchemy import text


def ejecutar(sql: str):
    with db.engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()


def migrar_postgres():
    # Índices normales
    ejecutar("CREATE INDEX IF NOT EXISTS ix_seguimiento_usuario_fecha ON seguimiento_ejercicios (usuario_id, fecha_ejecucion);")
    ejecutar("CREATE INDEX IF NOT EXISTS ix_seguimiento_ejercicio_fecha ON seguimiento_ejercicios (ejercicio_asignado_id, fecha_ejecucion);")
    # Unicidad: usar índice único (equivalente efectivo a una constraint única)
    ejecutar("CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_ejercicio_fecha_idx ON seguimiento_ejercicios (usuario_id, ejercicio_asignado_id, fecha_ejecucion);")


def migrar_sqlite():
    # SQLite permite CREATE UNIQUE INDEX IF NOT EXISTS
    ejecutar("CREATE INDEX IF NOT EXISTS ix_seguimiento_usuario_fecha ON seguimiento_ejercicios (usuario_id, fecha_ejecucion);")
    ejecutar("CREATE INDEX IF NOT EXISTS ix_seguimiento_ejercicio_fecha ON seguimiento_ejercicios (ejercicio_asignado_id, fecha_ejecucion);")
    ejecutar("CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_ejercicio_fecha_idx ON seguimiento_ejercicios (usuario_id, ejercicio_asignado_id, fecha_ejecucion);")


if __name__ == "__main__":
    with app.app_context():
        dialect = db.engine.dialect.name
        print(f"➡️ Ejecutando migración de índices en dialecto: {dialect}")
        if dialect == 'postgresql':
            migrar_postgres()
        elif dialect == 'sqlite':
            migrar_sqlite()
        else:
            raise RuntimeError(f"Dialecto no soportado para migración automática: {dialect}")
        print("✅ Migración de índices de seguimiento completada")


