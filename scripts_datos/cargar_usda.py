"""
Script de carga inicial del dataset USDA FoodData Central.

Uso:
    cd /ruta/del/proyecto
    python scripts_datos/cargar_usda.py \
        --food      ruta/food.csv \
        --nutrient  ruta/nutrient.csv \
        --fn        ruta/food_nutrient.csv

Descarga los CSVs en: https://fdc.nal.usda.gov/download-foods.html
(Full Download → Foundation Foods o SR Legacy)

El script hace JOIN de los tres archivos para obtener por alimento:
  nombre, kcal/100g, proteínas/100g, carbohidratos/100g, grasas/100g.

Solo se insertan alimentos con los 4 macros disponibles.
Los datos quedan en la tabla `alimentos` y en producción (Railway + Supabase)
se ejecuta una sola vez — no depende de archivos en disco en runtime.
"""

import sys
import os
import argparse

# Asegurarnos de que el proyecto raíz esté en el path de Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def inferir_categoria(nombre: str) -> str:
    n = nombre.lower()
    if any(k in n for k in ('chicken', 'beef', 'fish', 'egg', 'turkey',
                             'pork', 'salmon', 'tuna', 'lamb', 'veal',
                             'shrimp', 'crab', 'lobster', 'sardine')):
        return 'proteina'
    if any(k in n for k in ('rice', 'bread', 'pasta', 'oat', 'wheat',
                             'corn', 'potato', 'flour', 'cereal', 'grain',
                             'barley', 'quinoa', 'noodle', 'tortilla')):
        return 'cereal'
    if any(k in n for k in ('milk', 'yogurt', 'cheese', 'cream', 'butter',
                             'whey', 'dairy', 'cheddar', 'mozzarella')):
        return 'lacteo'
    if any(k in n for k in ('apple', 'banana', 'orange', 'berry', 'grape',
                             'mango', 'pear', 'peach', 'plum', 'cherry',
                             'strawberry', 'blueberry', 'watermelon', 'melon',
                             'pineapple', 'fruit')):
        return 'fruta'
    if any(k in n for k in ('oil', 'nuts', 'almond', 'walnut', 'cashew',
                             'peanut', 'avocado', 'olive', 'seed', 'lard',
                             'margarine', 'coconut', 'sunflower')):
        return 'grasa'
    return 'verdura'


def cargar(food_path: str, nutrient_path: str, fn_path: str, batch_size: int = 500):
    try:
        import pandas as pd
    except ImportError:
        print("ERROR: pandas no está instalado. Ejecuta: pip install pandas")
        sys.exit(1)

    from app import app
    from models import db, Alimento

    # ── IDs de nutrientes de interés en USDA ──────────────────────────────
    # 1008 = Energy (kcal), 1003 = Protein, 1005 = Carbohydrate by difference,
    # 1004 = Total lipid (fat)
    NUTRIENTE_IDS = {
        1008: 'kcal',
        1003: 'proteinas',
        1005: 'carbohidratos',
        1004: 'grasas',
    }

    print("Cargando food.csv…")
    foods = pd.read_csv(food_path, usecols=['fdc_id', 'description'], low_memory=False)
    foods['fdc_id'] = foods['fdc_id'].astype(str)
    print(f"  {len(foods)} alimentos encontrados en food.csv")

    print("Cargando nutrient.csv…")
    nutrients = pd.read_csv(nutrient_path, usecols=['id', 'name'], low_memory=False)
    # Filtrar solo los nutrientes que nos interesan
    nutrientes_utiles = nutrients[nutrients['id'].isin(NUTRIENTE_IDS.keys())].copy()

    print("Cargando food_nutrient.csv…")
    fn = pd.read_csv(fn_path, usecols=['fdc_id', 'nutrient_id', 'amount'], low_memory=False)
    fn['fdc_id'] = fn['fdc_id'].astype(str)
    fn = fn[fn['nutrient_id'].isin(NUTRIENTE_IDS.keys())].copy()
    fn['macro'] = fn['nutrient_id'].map(NUTRIENTE_IDS)

    print("Pivotando tabla de nutrientes…")
    pivot = fn.pivot_table(
        index='fdc_id', columns='macro', values='amount', aggfunc='first'
    ).reset_index()

    # Unir con nombres de alimentos
    merged = foods.merge(pivot, on='fdc_id', how='inner')

    # Filtrar los que tienen los 4 macros
    macros = ['kcal', 'proteinas', 'carbohidratos', 'grasas']
    merged = merged.dropna(subset=macros)
    merged = merged[merged['kcal'] > 0]

    print(f"  {len(merged)} alimentos con los 4 macros disponibles")

    with app.app_context():
        procesados = 0
        cargados   = 0
        batch      = []

        for _, row in merged.iterrows():
            procesados += 1
            fdc_id     = str(row['fdc_id'])
            fuente_id  = f'usda_{fdc_id}'

            # Saltar si ya existe
            if Alimento.query.filter_by(fuente_id=fuente_id).first():
                continue

            alimento = Alimento(
                nombre             = str(row['description'])[:300],
                calorias_100g      = float(row['kcal']),
                proteinas_100g     = float(row['proteinas']),
                carbohidratos_100g = float(row['carbohidratos']),
                grasas_100g        = float(row['grasas']),
                categoria          = inferir_categoria(str(row['description'])),
                fuente             = 'usda',
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

    print(f"\nCarga completada: {cargados} alimentos de {procesados} procesados.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Carga dataset USDA FoodData Central')
    parser.add_argument('--food',     required=True, help='Ruta al archivo food.csv')
    parser.add_argument('--nutrient', required=True, help='Ruta al archivo nutrient.csv')
    parser.add_argument('--fn',       required=True, help='Ruta al archivo food_nutrient.csv')
    parser.add_argument('--batch',    type=int, default=500, help='Tamaño de lote (default: 500)')
    args = parser.parse_args()

    cargar(args.food, args.nutrient, args.fn, args.batch)