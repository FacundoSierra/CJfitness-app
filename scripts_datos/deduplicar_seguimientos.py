#!/usr/bin/env python3
"""
Deduplicar seguimientos antiguos por (usuario_id, ejercicio_asignado_id, fecha_ejecucion).

Estrategia: conservar el más reciente (fecha_actualizacion o id mayor) y eliminar el resto.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, SeguimientoEjercicio


def deduplicar():
    with app.app_context():
        print('Buscando duplicados...')
        # Agrupar por clave
        filas = db.session.execute(
            db.text(
                """
                SELECT usuario_id, ejercicio_asignado_id, fecha_ejecucion, COUNT(*) as cnt
                FROM seguimiento_ejercicios
                GROUP BY usuario_id, ejercicio_asignado_id, fecha_ejecucion
                HAVING COUNT(*) > 1
                """
            )
        ).fetchall()

        total_eliminados = 0
        for (usuario_id, ejercicio_asignado_id, fecha, cnt) in filas:
            duplicados = (
                SeguimientoEjercicio.query
                .filter_by(usuario_id=usuario_id, ejercicio_asignado_id=ejercicio_asignado_id, fecha_ejecucion=fecha)
                .order_by(SeguimientoEjercicio.fecha_actualizacion.desc(), SeguimientoEjercicio.id.desc())
                .all()
            )
            # Conservar el primero (más reciente)
            conservar = duplicados[0]
            eliminar = duplicados[1:]
            for seg in eliminar:
                db.session.delete(seg)
                total_eliminados += 1
            db.session.commit()
            print(f"Clave ({usuario_id},{ejercicio_asignado_id},{fecha}) -> conservado {conservar.id}, eliminados {len(eliminar)}")

        print(f"Hecho. Total eliminados: {total_eliminados}")


if __name__ == '__main__':
    deduplicar()


