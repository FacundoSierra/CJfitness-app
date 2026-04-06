"""
Script de carga de datos nutricionales. Idempotente — ejecutable varias veces.

Carga 1: comidas_espanolas_completas.csv → tabla comidas_completas
Carga 2: alimentos_espanoles_bedca.csv   → tabla alimentos (fuente='bedca')

Uso:
    cd /ruta/del/proyecto
    python3 scripts_datos/cargar_alimentos.py
"""

import sys
import os
import csv as csv_mod

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR             = os.path.join(os.path.dirname(__file__), 'data')
CSV_COMIDAS          = os.path.join(DATA_DIR, 'comidas_espanolas_completas.csv')
CSV_ALIMENTOS        = os.path.join(DATA_DIR, 'alimentos_espanoles_bedca.csv')


def _bool(valor: str) -> bool:
    return str(valor).strip().lower() in ('si', 'sí', 'true', '1', 'yes')


def cargar_comidas(db, ComidaCompleta) -> int:
    """Carga comidas_espanolas_completas.csv → tabla comidas_completas."""
    print(f"Cargando comidas desde {CSV_COMIDAS}…")

    # Vaciar tabla y resetear IDs para una carga limpia
    from sqlalchemy import text
    with db.engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE comidas_completas RESTART IDENTITY CASCADE"))
        conn.commit()

    cargadas = 0
    with open(CSV_COMIDAS, newline='', encoding='utf-8') as f:
        reader = csv_mod.DictReader(f)
        batch = []
        for row in reader:
            nombre = row.get('nombre', '').strip()
            if not nombre:
                continue
            try:
                comida = ComidaCompleta(
                    nombre          = nombre,
                    franja          = row.get('franja', 'almuerzo').strip(),
                    calorias        = int(float(row['calorias'])),
                    proteinas_g     = float(row['proteinas_g']),
                    carbohidratos_g = float(row['carbohidratos_g']),
                    grasas_g        = float(row['grasas_g']),
                    vegetariano     = _bool(row.get('vegetariano', 'no')),
                    sin_gluten      = _bool(row.get('sin_gluten', 'no')),
                    sin_lacteos     = _bool(row.get('sin_lacteos', 'no')),
                    descripcion     = row.get('descripcion', '').strip() or None,
                )
                batch.append(comida)
            except (ValueError, KeyError):
                continue

        db.session.add_all(batch)
        db.session.commit()
        cargadas = len(batch)

    return cargadas


def cargar_alimentos_bedca(db, Alimento) -> int:
    """Carga alimentos_espanoles_bedca.csv → tabla alimentos."""
    print(f"Cargando alimentos BEDCA desde {CSV_ALIMENTOS}…")

    # Limpiar registros bedca anteriores y resetear secuencia
    from sqlalchemy import text
    with db.engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE alimentos RESTART IDENTITY CASCADE"))
        conn.commit()

    cargados = 0
    with open(CSV_ALIMENTOS, newline='', encoding='utf-8') as f:
        reader = csv_mod.DictReader(f)
        batch = []
        for row in reader:
            nombre = row.get('nombre', '').strip()
            if not nombre:
                continue
            fuente_id = f"bedca_{nombre[:80].lower().replace(' ', '_')}"
            try:
                cals  = float(row['calorias_100g'])
                prot  = float(row['proteinas_100g'])
                carbs = float(row['carbohidratos_100g'])
                fat   = float(row['grasas_100g'])
            except (ValueError, KeyError):
                continue
            if cals <= 0:
                continue

            alimento = Alimento(
                nombre             = nombre,
                calorias_100g      = cals,
                proteinas_100g     = prot,
                carbohidratos_100g = carbs,
                grasas_100g        = fat,
                categoria          = row.get('categoria', 'otro').strip() or 'otro',
                fuente             = 'bedca',
                fuente_id          = fuente_id,
            )
            batch.append(alimento)

        db.session.add_all(batch)
        db.session.commit()
        cargados = len(batch)

    return cargados


def main():
    from app import app
    from models import db, ComidaCompleta, Alimento

    with app.app_context():
        comidas_n   = cargar_comidas(db, ComidaCompleta)
        alimentos_n = cargar_alimentos_bedca(db, Alimento)

    print(f"\nResumen: {comidas_n} comidas cargadas, {alimentos_n} alimentos cargados.")


if __name__ == '__main__':
    main()
