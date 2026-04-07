"""
NutritionService — motor de recomendación nutricional.

Arquitectura dual:
  - ComidaCompleta  → genera menús diarios (comidas predefinidas con macros reales)
  - Alimento (BEDCA)→ biblioteca consultable por el usuario (valores por 100g)

Algoritmo anti-monotonía:
  1. Obtiene historial de los últimos 7 días del usuario.
  2. Para cada franja, filtra candidatos por preferencias (vegetariano, sin_gluten…).
  3. Puntúa con similitud coseno + penalización por repetición reciente.
  4. Elige 1 de los top-8 con random.choices ponderado.
"""

import logging
import random
import requests
from datetime import date, timedelta

logger = logging.getLogger('fitness_app')

# ── Constantes ────────────────────────────────────────────────────────────────

MULTIPLICADORES_ACTIVIDAD = {
    'sedentario':  1.2,
    'ligero':      1.375,
    'moderado':    1.55,
    'activo':      1.725,
    'muy_activo':  1.9,
}

AJUSTE_OBJETIVO = {
    'perder_peso':         0.82,
    'ganar_masa':          1.12,
    'mantener':            1.0,
    'mejorar_rendimiento': 1.0,
}

MACROS_OBJETIVO = {
    'perder_peso':         {'proteinas': 0.30, 'carbohidratos': 0.40, 'grasas': 0.30},
    'ganar_masa':          {'proteinas': 0.25, 'carbohidratos': 0.50, 'grasas': 0.25},
    'mantener':            {'proteinas': 0.20, 'carbohidratos': 0.50, 'grasas': 0.30},
    'mejorar_rendimiento': {'proteinas': 0.25, 'carbohidratos': 0.55, 'grasas': 0.20},
}

DISTRIBUCION_FRANJAS = {
    'desayuno': 0.25,
    'almuerzo': 0.35,
    'cena':     0.30,
    'snack':    0.10,
}

# Palabras clave para detectar tipo de proteína principal (bonus diversidad)
PROTEINA_TIPOS = {
    'pollo':    ('pollo', 'pechuga', 'muslo', 'alita'),
    'ternera':  ('ternera', 'buey', 'vaca', 'res', 'carne picada'),
    'cerdo':    ('cerdo', 'lomo', 'costilla', 'jamón', 'panceta'),
    'pescado':  ('pescado', 'merluza', 'salmón', 'atún', 'bacalao', 'dorada', 'lubina'),
    'mariscos': ('marisco', 'gamba', 'langostino', 'mejillón', 'calamar', 'sepia'),
    'huevo':    ('huevo', 'tortilla'),
    'legumbre': ('lentejas', 'garbanzos', 'alubias', 'judías', 'soja'),
}

OFF_SEARCH_URL = 'https://world.openfoodfacts.org/cgi/search.pl'
OFF_TIMEOUT    = 3

_JUNK_KEYWORDS = {
    'pizza', 'burger', 'mcdonald', 'kfc', 'subway', 'kebab',
    'chips', 'cola', 'soda', 'candy',
}


class NutritionService:

    # ── Cálculos energéticos ─────────────────────────────────────────────────

    def calcular_tmb(self, peso_kg: float, altura_cm: float, edad: int, genero: str) -> float:
        base = (10 * peso_kg) + (6.25 * altura_cm) - (5 * edad)
        return base + 5 if genero and genero.lower() in ('hombre', 'masculino', 'male', 'm') else base - 161

    def calcular_calorias_objetivo(self, perfil, usuario) -> int:
        if not perfil.peso_kg or not perfil.altura_cm:
            return 2000
        edad   = self._calcular_edad(usuario.fecha_nacimiento)
        genero = usuario.genero or 'hombre'
        tmb    = self.calcular_tmb(perfil.peso_kg, perfil.altura_cm, edad, genero)
        tdee   = tmb * MULTIPLICADORES_ACTIVIDAD.get(perfil.nivel_actividad, 1.55)
        return round(tdee * AJUSTE_OBJETIVO.get(perfil.objetivo, 1.0))

    def calcular_macros_objetivo(self, calorias: int, objetivo: str) -> dict:
        dist = MACROS_OBJETIVO.get(objetivo, MACROS_OBJETIVO['mantener'])
        return {
            'proteinas':     round(calorias * dist['proteinas']     / 4),
            'carbohidratos': round(calorias * dist['carbohidratos'] / 4),
            'grasas':        round(calorias * dist['grasas']        / 9),
        }

    # ── Generación del menú (arquitectura dual + anti-monotonía) ────────────

    def generar_menu(self, perfil, usuario, recomendacion_anterior=None) -> dict:
        """
        Genera un menú diario usando ComidaCompleta con lógica anti-monotonía.
        Retorna dict con: menu_json, calorias_totales, macros_json
        """
        from models import ComidaCompleta, RecomendacionDiaria, PreferenciaAlimento, ValoracionComida
        from collections import defaultdict

        calorias_obj = perfil.calorias_objetivo or self.calcular_calorias_objetivo(perfil, usuario)
        objetivo     = perfil.objetivo or 'mantener'
        dist_macros  = MACROS_OBJETIVO.get(objetivo, MACROS_OBJETIVO['mantener'])

        # ── Cargar datos de personalización del usuario ───────────────────
        excluidos_raw     = PreferenciaAlimento.query.filter_by(usuario_id=usuario.id, tipo='no_me_gusta').all()
        nombres_excluidos = {p.nombre_alimento.lower() for p in excluidos_raw}

        valoraciones_raw  = ValoracionComida.query.filter_by(usuario_id=usuario.id).all()
        val_acum = defaultdict(list)
        for v in valoraciones_raw:
            val_acum[v.nombre_comida.lower()].append(v.valoracion)
        media_valoraciones = {n: sum(vs) / len(vs) for n, vs in val_acum.items()}

        # ── Paso 1: historial reciente ────────────────────────────────────
        hoy          = date.today()
        hace_3       = hoy - timedelta(days=3)
        hace_7       = hoy - timedelta(days=7)

        historial_7  = RecomendacionDiaria.query.filter(
            RecomendacionDiaria.usuario_id == usuario.id,
            RecomendacionDiaria.fecha >= hace_7,
            RecomendacionDiaria.fecha < hoy,
        ).all()

        nombres_3dias: set = set()
        nombres_7dias: set = set()
        proteina_ayer: str = ''

        for rec in historial_7:
            if not rec.menu_json:
                continue
            for franja, item in rec.menu_json.items():
                if not isinstance(item, dict):
                    continue
                nombre_lower = item.get('nombre', '').lower()
                nombres_7dias.add(nombre_lower)
                if rec.fecha >= hace_3:
                    nombres_3dias.add(nombre_lower)
                # Detectar proteína del almuerzo de ayer para diversidad
                if franja == 'almuerzo' and rec.fecha == hoy - timedelta(days=1):
                    proteina_ayer = self._detectar_tipo_proteina(nombre_lower)

        # ── Paso 2-3-4: construir menú franja a franja ────────────────────
        menu      = {}
        totales   = {'proteinas': 0.0, 'carbohidratos': 0.0, 'grasas': 0.0, 'calorias': 0}

        for franja, fraccion in DISTRIBUCION_FRANJAS.items():
            # Vector objetivo para esta franja
            vector_obj = [
                dist_macros['proteinas'],
                dist_macros['carbohidratos'],
                dist_macros['grasas'],
            ]

            # Candidatos filtrados por franja y preferencias
            q = ComidaCompleta.query.filter_by(franja=franja)
            preferencias = perfil.preferencias or []
            if 'vegetariano' in preferencias or 'vegano' in preferencias:
                q = q.filter_by(vegetariano=True)
            if 'sin gluten' in preferencias:
                q = q.filter_by(sin_gluten=True)
            if 'sin lactosa' in preferencias:
                q = q.filter_by(sin_lacteos=True)
            candidatos = q.all()

            if not candidatos:
                # Sin candidatos tras filtrar — usar todos los de esa franja
                candidatos = ComidaCompleta.query.filter_by(franja=franja).all()

            if not candidatos:
                continue

            # Relajar penalización si hay < 8 candidatos
            penalizar_3dias = len(candidatos) >= 8

            # Puntuar cada candidato
            scored = []
            for c in candidatos:
                vec_c = [c.proteinas_g, c.carbohidratos_g, c.grasas_g]
                sim          = self._similitud_coseno(vector_obj, vec_c)
                nombre_lower = c.nombre.lower()
                desc_lower   = (c.descripcion or '').lower()

                # Excluir si contiene ingrediente que el usuario marcó como "no me gusta"
                if nombres_excluidos and any(exc in nombre_lower or exc in desc_lower for exc in nombres_excluidos):
                    sim = 0.0

                if sim > 0:
                    if nombre_lower in nombres_3dias and penalizar_3dias:
                        sim *= 0.0   # excluir de los últimos 3 días
                    elif nombre_lower in nombres_7dias:
                        sim *= 0.3   # penalizar si apareció en la semana

                    # Bonus diversidad de proteína en almuerzo
                    if franja == 'almuerzo' and proteina_ayer:
                        tipo_c = self._detectar_tipo_proteina(nombre_lower)
                        if tipo_c and tipo_c == proteina_ayer:
                            sim *= 0.5

                    # Ajuste por valoraciones históricas del usuario
                    avg = media_valoraciones.get(nombre_lower)
                    if avg is not None:
                        if avg >= 4.0:
                            sim *= 1.3
                        elif avg <= 1.5:
                            sim = 0.0
                        elif avg <= 2.0:
                            sim *= 0.4

                scored.append((sim, c))

            # Ordenar, filtrar excluidos y tomar top-8
            scored.sort(key=lambda x: x[0], reverse=True)
            scored_validos = [(s, c) for s, c in scored if s > 0.0]
            if not scored_validos:
                scored_validos = scored  # fallback: usar todos si todos son 0
            top8 = scored_validos[:8]

            # Elección aleatoria ponderada por puntuación
            pesos      = [s for s, _ in top8]
            elegida    = random.choices([c for _, c in top8], weights=pesos, k=1)[0]

            # Escalar macros al objetivo calórico del usuario para esta franja
            cal_objetivo_franja = calorias_obj * fraccion
            factor = (cal_objetivo_franja / elegida.calorias) if elegida.calorias else 1.0

            item = {
                'nombre':           elegida.nombre,
                'descripcion':      elegida.descripcion or '',
                'calorias':         round(cal_objetivo_franja),
                'proteinas_g':      round(elegida.proteinas_g * factor, 1),
                'carbohidratos_g':  round(elegida.carbohidratos_g * factor, 1),
                'grasas_g':         round(elegida.grasas_g * factor, 1),
                'vegetariano':      elegida.vegetariano,
                'sin_gluten':       elegida.sin_gluten,
                'sin_lacteos':      elegida.sin_lacteos,
            }
            menu[franja] = item

            totales['proteinas']     += item['proteinas_g']
            totales['carbohidratos'] += item['carbohidratos_g']
            totales['grasas']        += item['grasas_g']
            totales['calorias']      += item['calorias']

        macros = {
            'proteinas':     round(totales['proteinas'], 1),
            'carbohidratos': round(totales['carbohidratos'], 1),
            'grasas':        round(totales['grasas'], 1),
        }

        return {
            'menu_json':        menu,
            'calorias_totales': round(totales['calorias']),
            'macros_json':      macros,
        }

    # ── Similitud coseno ─────────────────────────────────────────────────────

    def _similitud_coseno(self, v1: list, v2: list) -> float:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            a = np.array(v1).reshape(1, -1)
            b = np.array(v2).reshape(1, -1)
            return float(cosine_similarity(a, b)[0][0])
        except ImportError:
            dot  = sum(a * b for a, b in zip(v1, v2))
            mag1 = sum(x ** 2 for x in v1) ** 0.5
            mag2 = sum(x ** 2 for x in v2) ** 0.5
            return dot / (mag1 * mag2) if mag1 and mag2 else 0.0

    def _detectar_tipo_proteina(self, nombre_lower: str) -> str:
        for tipo, palabras in PROTEINA_TIPOS.items():
            if any(p in nombre_lower for p in palabras):
                return tipo
        return ''

    # ── Búsqueda de alimentos (biblioteca BEDCA + OFF) ───────────────────────

    def buscar_alimento(self, query: str) -> list:
        """Busca en tabla alimentos (BEDCA); complementa con OFF si < 3 resultados."""
        from models import Alimento

        locales = Alimento.query.filter(
            Alimento.nombre.ilike(f'%{query}%')
        ).limit(20).all()

        if len(locales) < 3:
            self.buscar_alimento_off(query)
            locales = Alimento.query.filter(
                Alimento.nombre.ilike(f'%{query}%')
            ).limit(20).all()

        return [self._alimento_to_dict(a) for a in locales]

    def buscar_por_categoria(self, categoria: str) -> list:
        from models import Alimento
        resultados = Alimento.query.filter_by(categoria=categoria).limit(50).all()
        return [self._alimento_to_dict(a) for a in resultados]

    # ── Open Food Facts ──────────────────────────────────────────────────────

    def buscar_alimento_off(self, nombre: str) -> list:
        """Busca en OFF España. Fallback silencioso si falla."""
        try:
            resp = requests.get(
                OFF_SEARCH_URL,
                params={
                    'search_terms':   nombre,
                    'tagtype_0':      'countries',
                    'tag_contains_0': 'contains',
                    'tag_0':          'spain',
                    'action':         'process',
                    'json':           1,
                    'page_size':      5,
                    'fields':         'product_name,nutriments,categories_tags,code',
                },
                timeout=OFF_TIMEOUT,
            )
            if resp.status_code != 200:
                return []

            guardados = []
            for p in resp.json().get('products', []):
                if self._es_comida_basura(p):
                    continue
                resultado = self._guardar_producto_off(p)
                if resultado:
                    guardados.append(resultado)
            return guardados

        except Exception as exc:
            logger.debug(f'OFF lookup silently failed for "{nombre}": {exc}')
            return []

    def _es_comida_basura(self, producto: dict) -> bool:
        nombre = (producto.get('product_name') or '').lower()
        tags   = ' '.join(producto.get('categories_tags') or []).lower()
        return any(k in nombre + ' ' + tags for k in _JUNK_KEYWORDS)

    def _guardar_producto_off(self, producto: dict):
        from models import db, Alimento

        barcode    = str(producto.get('code', '') or '')
        nombre     = (producto.get('product_name') or '').strip()
        nutriments = producto.get('nutriments', {})

        if not nombre:
            return None

        try:
            kcal  = float(nutriments.get('energy-kcal_100g') or nutriments.get('energy_100g', 0) or 0)
            prot  = float(nutriments.get('proteins_100g', 0) or 0)
            carbs = float(nutriments.get('carbohydrates_100g', 0) or 0)
            fat   = float(nutriments.get('fat_100g', 0) or 0)
        except (ValueError, TypeError):
            return None

        if kcal <= 0:
            return None

        fuente_id = f'off_{barcode}' if barcode else f'off_name_{nombre[:50]}'
        existing  = Alimento.query.filter_by(fuente_id=fuente_id).first()
        if existing:
            return existing

        alimento = Alimento(
            nombre             = nombre,
            calorias_100g      = kcal,
            proteinas_100g     = prot,
            carbohidratos_100g = carbs,
            grasas_100g        = fat,
            categoria          = self._inferir_categoria(nombre),
            fuente             = 'openfoodfacts',
            fuente_id          = fuente_id,
        )
        try:
            db.session.add(alimento)
            db.session.commit()
            return alimento
        except Exception:
            db.session.rollback()
            return None

    # ── Utilidades ───────────────────────────────────────────────────────────

    def _calcular_edad(self, fecha_nacimiento) -> int:
        if not fecha_nacimiento:
            return 30
        hoy  = date.today()
        edad = hoy.year - fecha_nacimiento.year
        if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
            edad -= 1
        return max(edad, 1)

    def _inferir_categoria(self, nombre: str) -> str:
        n = nombre.lower()
        if any(k in n for k in ('chicken', 'beef', 'fish', 'egg', 'turkey', 'pork',
                                 'salmon', 'tuna', 'pollo', 'ternera', 'atún',
                                 'cerdo', 'jamón', 'carne')):
            return 'proteina'
        if any(k in n for k in ('rice', 'bread', 'pasta', 'oat', 'wheat', 'corn',
                                 'potato', 'arroz', 'pan', 'avena', 'trigo',
                                 'maíz', 'patata', 'cereal')):
            return 'cereal'
        if any(k in n for k in ('milk', 'yogurt', 'cheese', 'cream', 'leche',
                                 'yogur', 'queso', 'nata')):
            return 'lacteo'
        if any(k in n for k in ('apple', 'banana', 'orange', 'berry', 'fruit',
                                 'grape', 'manzana', 'plátano', 'naranja',
                                 'fresa', 'uva', 'fruta', 'pera', 'melon')):
            return 'fruta'
        if any(k in n for k in ('oil', 'butter', 'nuts', 'almond', 'walnut',
                                 'avocado', 'aceite', 'mantequilla', 'nuez',
                                 'almendra', 'aguacate')):
            return 'grasa'
        if any(k in n for k in ('lentejas', 'garbanzos', 'alubias', 'judías',
                                 'soja', 'legumbre', 'bean', 'lentil')):
            return 'legumbre'
        return 'verdura'

    def _alimento_to_dict(self, a) -> dict:
        return {
            'id':                 a.id,
            'nombre':             a.nombre,
            'calorias_100g':      a.calorias_100g,
            'proteinas_100g':     a.proteinas_100g,
            'carbohidratos_100g': a.carbohidratos_100g,
            'grasas_100g':        a.grasas_100g,
            'categoria':          a.categoria,
            'fuente':             a.fuente,
        }


# Instancia global
nutrition_service = NutritionService()
