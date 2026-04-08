"""
Script de carga de taxonomía de ejercicios. Idempotente — ejecutable varias veces.

Carga la estructura jerárquica inicial:
  BloqueTaxonomia → CategoriaTaxonomia → SubcategoriaTaxonomia
  CaracteristicaTipo → CaracteristicaValor

Los bloques Potencia, Preparación y DSE se crean vacíos — el admin los rellena desde la app.

Uso:
    cd /ruta/del/proyecto
    python3 scripts_datos/cargar_taxonomia.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, BloqueTaxonomia, CategoriaTaxonomia, SubcategoriaTaxonomia, CaracteristicaTipo, CaracteristicaValor

# ── Taxonomía: bloque → {categoria → [subcategorias]} ─────────────────────────
TAXONOMIA = {
    "Fuerza": {
        "PRINCIPALES": [
            "3FE", "Bisagra de cadera", "Press H (Horizontal)",
            "Press OH (Overhead)", "Pull H (Horizontal)", "Pull V (Vertical)", "Core"
        ],
        "AUXILIARES": [
            "Variantes de 3FE", "Asimétricas de 3FE",
            "Variantes de Bisagra de cadera", "Asimétricas de Bisagra de cadera",
            "Variantes de Press H y OH", "Variantes de Pull H y V"
        ],
        "COMPLEMENTARIOS": ["Complementario 1", "Complementario 2", "Complementario 3"]
    },
    "Core": {
        "Patron_Respiratorio": ["PRV", "BV"],
        "Anti_Movimiento":     ["Anti-extensión", "Anti-flexión lateral", "Anti-rotación"],
        "Movimiento":          ["Extensión", "Flexión lateral", "Rotación"]
    },
    "Potencia":    {},
    "Preparación": {},
    "DSE":         {},
}

# ── Características: bloque → {tipo → [valores]} ──────────────────────────────
CARACTERISTICAS = {
    "Fuerza": {
        "Base":   [],   # valores por determinar — el admin los añadirá desde la app
        "Agarre": [],   # valores por determinar — el admin los añadirá desde la app
    },
    "Core": {
        "Posturas": ["C1", "C2", "C3", "C4", "C5"],   # nombres provisionales
    },
}


def cargar():
    with app.app_context():
        creados = {"bloques": 0, "categorias": 0, "subcategorias": 0, "tipos": 0, "valores": 0}

        for orden_bloque, (nombre_bloque, categorias) in enumerate(TAXONOMIA.items()):
            bloque = BloqueTaxonomia.query.filter_by(nombre=nombre_bloque).first()
            if not bloque:
                bloque = BloqueTaxonomia(nombre=nombre_bloque, orden=orden_bloque)
                db.session.add(bloque)
                db.session.flush()
                creados["bloques"] += 1

            for orden_cat, (nombre_cat, subcats) in enumerate(categorias.items()):
                cat = CategoriaTaxonomia.query.filter_by(
                    bloque_id=bloque.id, nombre=nombre_cat
                ).first()
                if not cat:
                    cat = CategoriaTaxonomia(bloque_id=bloque.id, nombre=nombre_cat, orden=orden_cat)
                    db.session.add(cat)
                    db.session.flush()
                    creados["categorias"] += 1

                for orden_sub, nombre_sub in enumerate(subcats):
                    sub = SubcategoriaTaxonomia.query.filter_by(
                        categoria_id=cat.id, nombre=nombre_sub
                    ).first()
                    if not sub:
                        sub = SubcategoriaTaxonomia(
                            categoria_id=cat.id, nombre=nombre_sub, orden=orden_sub
                        )
                        db.session.add(sub)
                        creados["subcategorias"] += 1

        # Características
        for nombre_bloque, tipos in CARACTERISTICAS.items():
            bloque = BloqueTaxonomia.query.filter_by(nombre=nombre_bloque).first()
            if not bloque:
                continue

            for nombre_tipo, valores in tipos.items():
                tipo = CaracteristicaTipo.query.filter_by(
                    bloque_id=bloque.id, nombre=nombre_tipo
                ).first()
                if not tipo:
                    tipo = CaracteristicaTipo(bloque_id=bloque.id, nombre=nombre_tipo)
                    db.session.add(tipo)
                    db.session.flush()
                    creados["tipos"] += 1

                for orden_val, nombre_val in enumerate(valores):
                    val = CaracteristicaValor.query.filter_by(
                        tipo_id=tipo.id, nombre=nombre_val
                    ).first()
                    if not val:
                        val = CaracteristicaValor(
                            tipo_id=tipo.id, nombre=nombre_val, orden=orden_val
                        )
                        db.session.add(val)
                        creados["valores"] += 1

        db.session.commit()

        print("Taxonomía cargada:")
        print(f"  {creados['bloques']} bloques nuevos")
        print(f"  {creados['categorias']} categorías nuevas")
        print(f"  {creados['subcategorias']} subcategorías nuevas")
        print(f"  {creados['tipos']} tipos de característica nuevos")
        print(f"  {creados['valores']} valores de característica nuevos")

        total = BloqueTaxonomia.query.count()
        print(f"\nTotal bloques en BD: {total}")


if __name__ == "__main__":
    cargar()
