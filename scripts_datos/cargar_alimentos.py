"""
Script de carga de alimentos desde la fuente BEDCA (alimentos españoles).

Uso:
    cd /ruta/del/proyecto
    python3 scripts_datos/cargar_alimentos.py

Carga el CSV scripts_datos/data/alimentos_espanoles_bedca.csv en la tabla
`alimentos`. Borra previamente los registros con fuente='usda' que pudieran
existir de cargas anteriores.

Columnas esperadas en el CSV:
  nombre, calorias_100g, proteinas_100g, carbohidratos_100g, grasas_100g, categoria
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CSV_PATH = os.path.join(os.path.dirname(__file__), 'data', 'alimentos_espanoles_bedca.csv')


def cargar(csv_path: str = CSV_PATH, batch_size: int = 200):
    try:
        import csv as csv_mod
    except ImportError:
        print("ERROR: módulo csv no disponible")
        sys.exit(1)

    from app import app
    from models import db, Alimento

    with app.app_context():

        # ── Limpiar toda la tabla y resetear IDs ───────────────────────────
        from sqlalchemy import text
        with db.engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE alimentos RESTART IDENTITY CASCADE"))
            conn.commit()
        print("Tabla alimentos vaciada y secuencia de IDs reseteada a 1.")

        # ── Cargar BEDCA ──────────────────────────────────────────────────
        print(f"Cargando {csv_path}…")

        procesados = 0
        cargados   = 0
        saltados   = 0
        batch      = []

        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                procesados += 1
                nombre = row.get('nombre', '').strip()
                if not nombre:
                    saltados += 1
                    continue

                fuente_id = f"bedca_{nombre[:80].lower().replace(' ', '_')}"

                # Evitar duplicados
                if Alimento.query.filter_by(fuente_id=fuente_id).first():
                    saltados += 1
                    continue

                try:
                    cals  = float(row['calorias_100g'])
                    prot  = float(row['proteinas_100g'])
                    carbs = float(row['carbohidratos_100g'])
                    fat   = float(row['grasas_100g'])
                except (ValueError, KeyError):
                    saltados += 1
                    continue

                if cals <= 0:
                    saltados += 1
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

                if len(batch) >= batch_size:
                    db.session.add_all(batch)
                    db.session.commit()
                    cargados += len(batch)
                    batch = []
                    print(f"  Cargados {cargados} alimentos de {procesados} procesados…")

        if batch:
            db.session.add_all(batch)
            db.session.commit()
            cargados += len(batch)

    print(f"\nCarga completada: {cargados} cargados, {saltados} saltados, {procesados} procesados.")


if __name__ == '__main__':
    cargar()
