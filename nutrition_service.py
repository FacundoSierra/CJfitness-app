"""
NutritionService — motor de recomendación nutricional basado en contenido + reglas.

Algoritmo:
  1. Calcula TDEE con Mifflin-St Jeor y ajusta por objetivo.
  2. Distribuye macronutrientes según objetivo.
  3. Para cada comida, selecciona alimentos usando similitud coseno entre el
     vector de macros del alimento y el vector objetivo del usuario.
  4. Construye menú diario con distribución calórica: desayuno 25%, almuerzo 35%,
     cena 30%, snack 10%.
  5. Consulta Open Food Facts (sin credenciales) si no hay suficientes alimentos
     en la BD local.
"""

import logging
import requests
from datetime import date, datetime

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

# Porcentajes de macros por objetivo (proteína, carbos, grasas)
MACROS_OBJETIVO = {
    'perder_peso':         {'proteinas': 0.30, 'carbohidratos': 0.40, 'grasas': 0.30},
    'ganar_masa':          {'proteinas': 0.25, 'carbohidratos': 0.50, 'grasas': 0.25},
    'mantener':            {'proteinas': 0.20, 'carbohidratos': 0.50, 'grasas': 0.30},
    'mejorar_rendimiento': {'proteinas': 0.25, 'carbohidratos': 0.55, 'grasas': 0.20},
}

# Distribución calórica por comida
DISTRIBUCION_COMIDAS = {
    'desayuno': 0.25,
    'almuerzo': 0.35,
    'cena':     0.30,
    'snack':    0.10,
}

# Cantidad de alimentos por comida
ALIMENTOS_POR_COMIDA = {
    'desayuno': 2,
    'almuerzo': 3,
    'cena':     3,
    'snack':    1,
}

OFF_SEARCH_URL = 'https://world.openfoodfacts.org/cgi/search.pl'
OFF_TIMEOUT    = 3  # segundos


class NutritionService:

    # ── Cálculos energéticos ─────────────────────────────────────────────────

    def calcular_tmb(self, peso_kg: float, altura_cm: float, edad: int, genero: str) -> float:
        """Fórmula Mifflin-St Jeor."""
        base = (10 * peso_kg) + (6.25 * altura_cm) - (5 * edad)
        return base + 5 if genero and genero.lower() in ('hombre', 'masculino', 'male', 'm') else base - 161

    def calcular_calorias_objetivo(self, perfil, usuario) -> int:
        """Devuelve las calorías diarias objetivo para el usuario."""
        if not perfil.peso_kg or not perfil.altura_cm:
            return 2000  # fallback razonable

        edad = self._calcular_edad(usuario.fecha_nacimiento)
        genero = usuario.genero or 'hombre'
        tmb  = self.calcular_tmb(perfil.peso_kg, perfil.altura_cm, edad, genero)
        tdee = tmb * MULTIPLICADORES_ACTIVIDAD.get(perfil.nivel_actividad, 1.55)
        ajuste = AJUSTE_OBJETIVO.get(perfil.objetivo, 1.0)
        return round(tdee * ajuste)

    def calcular_macros_objetivo(self, calorias: int, objetivo: str) -> dict:
        """Devuelve los gramos objetivo de cada macro."""
        dist = MACROS_OBJETIVO.get(objetivo, MACROS_OBJETIVO['mantener'])
        return {
            'proteinas':     round(calorias * dist['proteinas']     / 4),
            'carbohidratos': round(calorias * dist['carbohidratos'] / 4),
            'grasas':        round(calorias * dist['grasas']        / 9),
        }

    # ── Generación del menú ──────────────────────────────────────────────────

    def generar_menu(self, perfil, usuario, recomendacion_anterior=None) -> dict:
        """
        Genera un menú diario completo. Retorna dict con:
          menu_json, calorias_totales, macros_json
        """
        from models import Alimento

        calorias_objetivo = perfil.calorias_objetivo or self.calcular_calorias_objetivo(perfil, usuario)
        objetivo = perfil.objetivo or 'mantener'

        # Vector objetivo de macros (normalizado para similitud coseno)
        dist = MACROS_OBJETIVO.get(objetivo, MACROS_OBJETIVO['mantener'])
        vector_objetivo = [dist['proteinas'], dist['carbohidratos'], dist['grasas']]

        # Alimentos excluidos (alergias + preferencias)
        alimentos_excluidos = self._nombres_excluidos(perfil)

        # Alimentos ya usados el día anterior (para rotar)
        usados_ayer: set = set()
        if recomendacion_anterior and recomendacion_anterior.menu_json:
            usados_ayer = self._nombres_del_menu(recomendacion_anterior.menu_json)

        # Cargar alimentos compatibles desde BD
        candidatos = Alimento.query.all()
        candidatos = [a for a in candidatos if not self._esta_excluido(a, alimentos_excluidos)]

        # Si hay muy pocos alimentos, buscar en OFF los básicos
        if len(candidatos) < 20:
            self._poblar_desde_off(['pollo', 'arroz', 'huevos', 'avena', 'manzana', 'yogur'])
            candidatos = Alimento.query.all()
            candidatos = [a for a in candidatos if not self._esta_excluido(a, alimentos_excluidos)]

        # Construir menú comida a comida
        menu = {}
        usados_hoy: set = set()
        totales = {'proteinas': 0, 'carbohidratos': 0, 'grasas': 0, 'calorias': 0}

        for comida, fraccion in DISTRIBUCION_COMIDAS.items():
            cal_comida = calorias_objetivo * fraccion
            n_alimentos = ALIMENTOS_POR_COMIDA[comida]

            seleccionados = self._seleccionar_alimentos(
                candidatos, vector_objetivo, cal_comida,
                n_alimentos, usados_hoy, usados_ayer, comida
            )

            items = []
            for alimento, gramos in seleccionados:
                factor = gramos / 100
                item = {
                    'nombre':         alimento.nombre,
                    'cantidad_g':     round(gramos),
                    'calorias':       round(alimento.calorias_100g * factor),
                    'proteinas_g':    round(alimento.proteinas_100g * factor, 1),
                    'carbohidratos_g':round(alimento.carbohidratos_100g * factor, 1),
                    'grasas_g':       round(alimento.grasas_100g * factor, 1),
                    'categoria':      alimento.categoria,
                }
                items.append(item)
                usados_hoy.add(alimento.nombre.lower())
                totales['proteinas']     += item['proteinas_g']
                totales['carbohidratos'] += item['carbohidratos_g']
                totales['grasas']        += item['grasas_g']
                totales['calorias']      += item['calorias']

            menu[comida] = items

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

    # ── Similitud coseno (sin sklearn si no está disponible) ─────────────────

    def _similitud_coseno(self, v1: list, v2: list) -> float:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            a = np.array(v1).reshape(1, -1)
            b = np.array(v2).reshape(1, -1)
            return float(cosine_similarity(a, b)[0][0])
        except ImportError:
            # Implementación manual si sklearn no está instalado
            dot   = sum(a * b for a, b in zip(v1, v2))
            mag1  = sum(x ** 2 for x in v1) ** 0.5
            mag2  = sum(x ** 2 for x in v2) ** 0.5
            if mag1 == 0 or mag2 == 0:
                return 0.0
            return dot / (mag1 * mag2)

    def _seleccionar_alimentos(self, candidatos, vector_objetivo, cal_comida,
                                n_alimentos, usados_hoy, usados_ayer, comida):
        """
        Ordena candidatos por similitud coseno con el vector objetivo,
        penaliza los usados (hoy o ayer), selecciona los top-n y calcula
        los gramos necesarios para alcanzar cal_comida distribuida en partes iguales.
        """
        cal_por_alimento = cal_comida / max(n_alimentos, 1)

        scored = []
        for a in candidatos:
            if a.calorias_100g <= 0:
                continue
            nombre_lower = a.nombre.lower()
            vec_a = [a.proteinas_100g, a.carbohidratos_100g, a.grasas_100g]
            sim = self._similitud_coseno(vector_objetivo, vec_a)

            # Penalizar repetición
            if nombre_lower in usados_hoy:
                sim -= 1.0
            elif nombre_lower in usados_ayer:
                sim -= 0.3

            scored.append((sim, a))

        scored.sort(key=lambda x: x[0], reverse=True)

        resultado = []
        for _, alimento in scored[:n_alimentos]:
            # Calcular gramos para aportar cal_por_alimento
            gramos = (cal_por_alimento / alimento.calorias_100g) * 100
            gramos = max(20, min(gramos, 400))  # entre 20g y 400g
            resultado.append((alimento, gramos))

        return resultado

    # ── Open Food Facts ──────────────────────────────────────────────────────

    def buscar_alimento_off(self, nombre: str) -> list:
        """
        Busca alimentos en Open Food Facts (sin credenciales).
        Guarda los resultados nuevos en la tabla Alimento.
        Retorna lista vacía silenciosamente si falla.
        """
        try:
            resp = requests.get(
                OFF_SEARCH_URL,
                params={
                    'search_terms': nombre,
                    'json':         'true',
                    'page_size':    5,
                    'fields':       'product_name,nutriments,code,pnns_groups_1',
                },
                timeout=OFF_TIMEOUT,
            )
            if resp.status_code != 200:
                return []

            productos = resp.json().get('products', [])
            guardados = []
            for p in productos:
                resultado = self._guardar_producto_off(p)
                if resultado:
                    guardados.append(resultado)
            return guardados

        except Exception as exc:
            logger.debug(f'OFF lookup silently failed for "{nombre}": {exc}')
            return []

    def _guardar_producto_off(self, producto: dict):
        """Persiste un producto de OFF en la BD si no existe ya."""
        from models import db, Alimento

        barcode    = str(producto.get('code', '') or '')
        nombre     = (producto.get('product_name') or '').strip()
        nutriments = producto.get('nutriments', {})

        if not nombre:
            return None

        kcal  = nutriments.get('energy-kcal_100g') or nutriments.get('energy_100g', 0)
        prot  = nutriments.get('proteins_100g', 0) or 0
        carbs = nutriments.get('carbohydrates_100g', 0) or 0
        fat   = nutriments.get('fat_100g', 0) or 0

        # Descartar si no tiene datos nutricionales mínimos
        try:
            kcal, prot, carbs, fat = float(kcal), float(prot), float(carbs), float(fat)
        except (ValueError, TypeError):
            return None

        if kcal <= 0:
            return None

        fuente_id = f'off_{barcode}' if barcode else f'off_name_{nombre[:50]}'

        # Evitar duplicados
        existing = Alimento.query.filter_by(fuente_id=fuente_id).first()
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

    def _poblar_desde_off(self, terminos: list):
        """Busca una lista de términos en OFF para poblar la BD inicial."""
        for termino in terminos:
            self.buscar_alimento_off(termino)

    # ── Búsqueda combinada (BD local + OFF) ──────────────────────────────────

    def buscar_alimento(self, query: str) -> list:
        """
        Busca primero en BD local; si hay < 3 resultados, complementa con OFF.
        Devuelve lista de dicts serializables.
        """
        from models import Alimento

        locales = Alimento.query.filter(
            Alimento.nombre.ilike(f'%{query}%')
        ).limit(10).all()

        if len(locales) < 3:
            self.buscar_alimento_off(query)
            locales = Alimento.query.filter(
                Alimento.nombre.ilike(f'%{query}%')
            ).limit(10).all()

        return [self._alimento_to_dict(a) for a in locales]

    # ── Utilidades ───────────────────────────────────────────────────────────

    def _calcular_edad(self, fecha_nacimiento) -> int:
        if not fecha_nacimiento:
            return 30  # valor por defecto
        hoy = date.today()
        edad = hoy.year - fecha_nacimiento.year
        if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
            edad -= 1
        return max(edad, 1)

    def _inferir_categoria(self, nombre: str) -> str:
        n = nombre.lower()
        if any(k in n for k in ('chicken', 'beef', 'fish', 'egg', 'turkey',
                                 'pork', 'salmon', 'tuna', 'pollo', 'ternera',
                                 'atún', 'cerdo', 'jamón', 'carne')):
            return 'proteina'
        if any(k in n for k in ('rice', 'bread', 'pasta', 'oat', 'wheat',
                                 'corn', 'potato', 'arroz', 'pan', 'avena',
                                 'trigo', 'maíz', 'patata', 'cereal')):
            return 'cereal'
        if any(k in n for k in ('milk', 'yogurt', 'cheese', 'cream',
                                 'leche', 'yogur', 'queso', 'nata')):
            return 'lacteo'
        if any(k in n for k in ('apple', 'banana', 'orange', 'berry', 'fruit',
                                 'grape', 'manzana', 'plátano', 'naranja',
                                 'fresa', 'uva', 'fruta', 'pera', 'melon')):
            return 'fruta'
        if any(k in n for k in ('oil', 'butter', 'nuts', 'almond', 'walnut',
                                 'avocado', 'aceite', 'mantequilla', 'nuez',
                                 'almendra', 'aguacate', 'palta')):
            return 'grasa'
        return 'verdura'

    def _nombres_excluidos(self, perfil) -> set:
        excluidos = set()
        alergias = perfil.alergias or []
        for alergia in alergias:
            excluidos.add(alergia.lower())
        return excluidos

    def _esta_excluido(self, alimento, excluidos: set) -> bool:
        if not excluidos:
            return False
        nombre_lower = alimento.nombre.lower()
        return any(exc in nombre_lower for exc in excluidos)

    def _nombres_del_menu(self, menu_json: dict) -> set:
        nombres = set()
        for items in menu_json.values():
            for item in items:
                nombres.add(item.get('nombre', '').lower())
        return nombres

    def _alimento_to_dict(self, a) -> dict:
        return {
            'id':                a.id,
            'nombre':            a.nombre,
            'calorias_100g':     a.calorias_100g,
            'proteinas_100g':    a.proteinas_100g,
            'carbohidratos_100g':a.carbohidratos_100g,
            'grasas_100g':       a.grasas_100g,
            'categoria':         a.categoria,
            'fuente':            a.fuente,
        }


# Instancia global (importable directamente)
nutrition_service = NutritionService()