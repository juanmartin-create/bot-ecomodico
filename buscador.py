"""Buscador propio del catálogo de ecomodico.com.

El buscador de Drubbit busca por coincidencia de texto: no entiende "cocacola" ni "champu",
y mezcla Coca-Cola con Glade Coco porque "coca" se parece a "coco". Este arma su propio índice
con los 5.800 productos y busca como lo haría Google, pero en chico:

1. Normaliza (minúsculas, sin tildes, "omega3" -> "omega 3", "400ml" -> "400 ml") y reduce
   plurales ("leches", "pañales") para que singular y plural sean lo mismo.
2. Sinónimos argentinos (champú -> shampoo, tele -> televisor, birra -> cerveza...).
3. Palabras pegadas ("cocacola" -> "coca cola") y errores de tipeo ("lehce" -> "leche"),
   pero solo si la palabra NO existe en el catálogo (así "coca" nunca trae "coco").
4. Ordena por relevancia: pesa más el nombre que la marca, la categoría o los atributos,
   suma si la categoría coincide (busco "leche" -> primero la categoría Leches, no galletitas),
   y desempata con stock, más vendidos, orden de la tienda y descuento.
5. Opcional (BUSCADOR_IA=1, apagado por defecto): si la búsqueda es una frase ("algo para el
   desayuno") o no trae nada, Claude Haiku la traduce a términos de catálogo. Se guarda en caché.

El índice se baja de /shop (las mismas páginas que ve el cliente) y se renueva cada hora.
"""

import asyncio
import json
import math
import os
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from rapidfuzz import process
from rapidfuzz.distance import DamerauLevenshtein

import catalogo

ROOT = Path(__file__).parent
ARCHIVO_INDICE = ROOT / "indice.json"
ARCHIVO_IA = ROOT / "busquedas_ia.json"
REFRESCO = 3600  # el catálogo se vuelve a bajar cada hora
MODELO_IA = os.getenv("BUSCADOR_MODEL", "claude-haiku-5-5")
# Apagada por defecto: el buscador no gasta tokens. Con BUSCADOR_IA=1, Claude interpreta frases y búsquedas sin resultados.
USAR_IA = os.getenv("BUSCADOR_IA", "0") == "1"

# Peso de cada campo: una palabra en el nombre vale más que en la marca, la categoría o un atributo.
PESOS = {"nombre": 10.0, "marca": 8.0, "categoria": 7.0, "familia": 4.0, "atributo": 3.0}

STOP = set("""de del la las el los lo para por con en y e o a al un una unos unas x que mi me te se su sus
quiero busco buscando necesito tenes tienen hay algo cosa cosas comprar compra precio precios online
venta barato barata baratos economico economica envio domicilio delivery producto productos""".split())
OFERTA = {"oferta", "promo", "promocion", "descuento", "liquidacion", "sale"}  # se comparan por raíz
# Palabras que describen la tienda y no el producto ("supermercado online a domicilio"). Salen de la búsqueda;
# si no queda nada, se muestra lo más vendido. Salen de las keywords reales de Google Ads.
GENERICAS = set("""online on line web site sitio tienda tiendas delivery domicilio envio envios cerca pedido pedidos
pedir compras ecomodico super supermercado supermercados mercado hiper hipermercado mayorista argentina caba amba
buenos aires capital""".split())
# Competidores. Si la búsqueda es solo el nombre, se reemplaza por lo que la gente va a buscar ahí.
# Los ambiguos (disco de pesas, talle jumbo, protector "día") solo cuentan si vinieron con "online", "super"...
COMPETIDORES = {
    "coto": "", "coto digital": "", "carrefour": "", "changomas": "", "chango mas": "", "la anonima": "",
    "walmart": "", "vea": "", "dia": "", "disco": "", "jumbo": "",
    "farmacity": "cuidado personal", "famacity": "cuidado personal", "selma": "cuidado personal",
    "nutrishop": "suplementos deportivos", "disfit": "suplementos deportivos", "entreno": "suplementos deportivos",
    "entreno com ar": "suplementos deportivos", "pitbull": "suplementos deportivos", "suplementate": "suplementos deportivos",
    "ibera": "suplementos deportivos", "suple ya": "suplementos deportivos", "supleya": "suplementos deportivos",
    "army fitness": "suplementos deportivos", "newgarden": "suplementos deportivos", "new garden": "suplementos deportivos",
    "capsulandia": "cafe capsula", "pitbull suplementos": "suplementos deportivos",
    "central suplementos": "suplementos deportivos", "ibera suplementos": "suplementos deportivos",
}
COMPETIDORES_AMBIGUOS = {"dia", "disco", "jumbo", "vea", "pitbull"}
# Búsquedas que son una categoría entera: se muestra lo más vendido de esas categorías (hoja o familia).
CATEGORIAS_ALIAS = {
    "limpieza": ["Cuidado Del Hogar"], "producto limpieza": ["Cuidado Del Hogar"],
    "productos limpieza": ["Cuidado Del Hogar"], "articulos limpieza": ["Cuidado Del Hogar"],
    "limpieza hogar": ["Cuidado Del Hogar"], "hogar limpieza": ["Cuidado Del Hogar"],
    "bebidas sin alcohol": ["Gaseosa", "Jugos", "Aguas", "Aguas Saborizadas"],
    "bebidas alcoholicas": ["Bebidas Con Alcohol", "Vinos"], "bebidas con alcohol": ["Bebidas Con Alcohol", "Vinos"],
    "electrodomesticos": ["Electro Y Hogar"], "pequenos electrodomesticos": ["Pequeños Electrodomésticos"],
    "suplementos": ["Suplementos Deportivos", "Vitaminas, Minerales Y Antioxidantes"],
    "suplementos fitness": ["Suplementos Deportivos"], "suplementos gym": ["Suplementos Deportivos"],
    "articulos hogar": ["Hogar"], "articulos para el hogar": ["Hogar"],
    "comida": ["Almacén"],
}
# Frases que suenan a pregunta o pedido abierto: ahí conviene que Claude interprete.
FRASE_ABIERTA = re.compile(r"\b(algo|cosas?|ideas?|regalo|para (hacer|tomar|comer|llevar|cocinar|preparar)|que (sirva|me)|recomend\w*)\b", re.I)

# Frases que se reemplazan enteras antes de buscar (ya normalizadas, sin tildes).
FRASES = {
    "papel de bano": "papel higienico",
    "rollo de cocina": "rollo cocina",
    "papel de cocina": "rollo cocina",
    "crema dental": "pasta dental",
    "comida para": "alimento para",
    "comida de": "alimento para",
    "gel antibacterial": "alcohol gel",
    "alcohol en gel": "alcohol gel",
    "on line": "online",
    "jabon para ropa": "jabon ropa",
    "jabon para lavar ropa": "jabon ropa",
    "maquina de afeitar": "afeitadora",
    "aire acondicionado": "aire acondicionado",
    "lavaplatos": "detergente",
    "lava platos": "detergente",
    "agua lavandina": "lavandina",
    "toallitas femeninas": "toallas femeninas",
    "toallas higienicas": "toallas femeninas",
    "pantalla solar": "protector solar",
    "bloqueador solar": "protector solar",
    "dulce leche": "dulce de leche",
}
# Palabra -> con qué buscarla en el catálogo (se reemplaza; si querés conservarla, incluila).
SINONIMOS = {
    "champu": ["shampoo"], "champoo": ["shampoo"], "shampo": ["shampoo"], "sampu": ["shampoo"],
    "tele": ["televisor", "tv"], "televisor": ["televisor", "tv"], "tv": ["tv", "televisor"],
    "celu": ["celular"], "auris": ["auricular"], "compu": ["notebook", "computadora"],
    "micro": ["microonda"], "heladera": ["heladera", "refrigerador"], "nevera": ["heladera"],
    "lavadora": ["lavarropa"], "lavarropas": ["lavarropa"],
    "birra": ["cerveza"], "birras": ["cerveza"], "chela": ["cerveza"],
    "yogur": ["yogur", "yogurt"], "yogurt": ["yogurt", "yogur"],
    "galleta": ["galletita", "galleta"], "galletas": ["galletita", "galleta"],
    "cloro": ["lavandina", "cloro"],
    "whey": ["whey"], "prote": ["proteina"], "protein": ["proteina", "protein"],
    "creatine": ["creatina"], "crea": ["creatina"],
    "barrita": ["barra", "barrita"], "barritas": ["barra", "barrita"],
    "vitc": ["vitamina"],
    "toallitas": ["toallita", "toalla"],
    "desodorante": ["desodorante"], "deo": ["desodorante"],
    "afeitar": ["afeitar", "afeitadora", "maquina"], "gillette": ["gillette"],
    "nespresso": ["nespresso"], "capsula": ["capsula"],
    "perro": ["perro"], "perros": ["perro"], "gato": ["gato"], "gatos": ["gato"], "gatito": ["gatito", "kitten"],
    "cachorro": ["cachorro", "puppy"],
    "comida": ["alimento", "comida"],  # "comida gato"; sola, "comida" va a la categoría Almacén
}
UNIDADES = {"gr": "g", "grs": "g", "gramo": "g", "gramos": "g", "kilo": "kg", "kilos": "kg", "kgs": "kg",
            "lt": "l", "lts": "l", "litro": "l", "litros": "l", "cc": "ml", "mililitro": "ml", "mililitros": "ml"}
# Atributos que describen al producto (no los administrativos tipo "Con fecha de vencimiento").
ATRIBUTOS_UTILES = re.compile(r"sabor|tipo|formato del|variedad|suplemento|aroma|fragancia|edad|raza|tamano|tama|linea|color", re.I)

_estado = {"productos": [], "por_id": {}, "indice": {}, "familias": {}, "urls_cat": {}, "vocab": [], "frec": Counter(), "superficie": {},
           "actualizado": 0.0, "cargando": None}
_cache_ia: dict[str, list[str]] = {}


# ---------- texto ----------

def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"(\d)([a-z])", r"\1 \2", s)
    s = re.sub(r"([a-z])(\d)", r"\1 \2", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def raiz(t: str) -> str:
    """Raíz liviana para español: 'leches'/'leche' -> 'lech', 'pañales'/'pañal' -> 'panal'."""
    t = UNIDADES.get(t, t)
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        t = t[:-1]
    if len(t) > 3 and t.endswith("e"):
        t = t[:-1]
    return t


def tokens(s: str) -> list[str]:
    return [raiz(t) for t in normalizar(s).split()]


# ---------- índice ----------

def _doc(p: dict, pos: int, top: set) -> dict:
    r = catalogo._resumen(p)
    cats = p.get("categories") or []
    hoja = max(cats, key=lambda c: len(c.get("familyNames") or []), default={})
    attrs = [a["v"] for a in p.get("attrs") or []
             if a.get("attrKey") and ATRIBUTOS_UTILES.search(normalizar(a["attrKey"]["k"]))
             and isinstance(a.get("v"), str) and normalizar(a["v"]) not in ("si", "no")]
    # Ley 27.743 (Transparencia Fiscal): hay que mostrar el precio sin impuestos nacionales, como hace la tienda.
    pv = ((p.get("variants") or [{}])[0].get("pvPrice") or {})
    imp = (pv.get("ivaTaxPct") or 0) + (pv.get("internalTaxPct") or 0)
    r["precio_sin_impuestos"] = round(r["precio"] / (1 + imp / 100), 2) if r.get("precio") else None
    r.update(pos=pos, top_ventas=p["id"] in top, cat_hoja=hoja.get("name") or "",
             familia=[c["name"] for c in cats if c is not hoja], atributos=attrs[:6],
             cat_urls={c["name"]: "/" + "/".join(c.get("familyUrlNames") or [c.get("urlName") or ""]) for c in cats})
    return r


async def _bajar_catalogo() -> list[dict]:
    primera = await catalogo._server_data("/shop?page=1")
    ultima = (primera["shop"].get("pagination") or {}).get("lastPage") or 1
    try:
        r = await catalogo._http.get(catalogo.BASE + "/api/catalog/top-sales")
        top = {p["id"] for p in r.json()["data"]["products"]}
    except Exception:
        top = set()
    sem = asyncio.Semaphore(6)  # de a 6 páginas: rápido, sin castigar a la tienda

    async def pagina(n: int) -> list[dict]:
        if n == 1:
            return primera["shop"]["products"]
        async with sem:
            for intento in range(3):
                try:
                    r = await catalogo._http.get(f"{catalogo.BASE}/shop?page={n}")
                    r.raise_for_status()
                    m = catalogo._SERVER_DATA.search(r.text)
                    return json.loads(m.group(1).strip().rstrip(";"))["_resolvedData"]["shop"]["products"]
                except Exception:
                    await asyncio.sleep(1 + intento)
        return []

    paginas = await asyncio.gather(*(pagina(n) for n in range(1, ultima + 1)))
    vistos, docs = set(), []
    for prods in paginas:
        for p in prods:
            if p["id"] not in vistos:
                vistos.add(p["id"])
                docs.append(_doc(p, len(docs), top))
    return docs


def _armar(docs: list[dict]) -> None:
    indice: dict[str, dict[str, float]] = defaultdict(dict)
    frec, superficie = Counter(), defaultdict(Counter)
    for d in docs:
        campos = [("nombre", d["nombre"]), ("marca", d["marca"] or ""), ("categoria", d["cat_hoja"]),
                  ("familia", " ".join(d["familia"])), ("atributo", " ".join(d["atributos"]))]
        vistos = set()
        for campo, texto in campos:
            for crudo in normalizar(texto).split():
                t = raiz(crudo)
                superficie[t][crudo] += 1
                if PESOS[campo] > indice[t].get(d["id"], 0):
                    indice[t][d["id"]] = PESOS[campo]
                vistos.add(t)
        frec.update(vistos)
        d["_nombre_norm"] = " " + " ".join(tokens(d["nombre"])) + " "
        d["_cat_tokens"] = set(tokens(d["cat_hoja"]))
        d["_cat_norm"] = " ".join(tokens(d["cat_hoja"]))
    familias = {_clave(f): f for d in docs for f in d["familia"]}
    urls_cat = {n: u for d in docs for n, u in (d.get("cat_urls") or {}).items()}
    _estado.update(productos=docs, por_id={d["id"]: d for d in docs}, indice=dict(indice), familias=familias, urls_cat=urls_cat,
                   vocab=list(indice), frec=frec,
                   superficie={t: c.most_common(1)[0][0] for t, c in superficie.items()},
                   actualizado=time.time())


async def actualizar(forzar: bool = False) -> int:
    """Baja el catálogo si está viejo. Si hay un índice guardado, arranca con ese al instante."""
    if not _estado["productos"] and ARCHIVO_INDICE.exists() and not forzar:
        guardado = json.loads(ARCHIVO_INDICE.read_text(encoding="utf-8"))
        _armar(guardado["productos"])
        _estado["actualizado"] = guardado["ts"]
    if not forzar and time.time() - _estado["actualizado"] < REFRESCO:
        return len(_estado["productos"])
    if _estado["cargando"] is None:
        async def tarea():
            try:
                docs = await _bajar_catalogo()
                if len(docs) > 100:  # si la tienda falló a mitad de camino, no pisamos un índice bueno
                    _armar(docs)
                    limpio = [{k: v for k, v in d.items() if not k.startswith("_")} for d in docs]
                    ARCHIVO_INDICE.write_text(json.dumps({"ts": time.time(), "productos": limpio}, ensure_ascii=False), encoding="utf-8")
            finally:
                _estado["cargando"] = None
        _estado["cargando"] = asyncio.create_task(tarea())
    if not _estado["productos"]:
        await _estado["cargando"]
    return len(_estado["productos"])


async def refrescar_siempre() -> None:
    while True:
        try:
            await actualizar()
        except Exception as e:
            print("buscador: no se pudo actualizar el catálogo:", e)
        await asyncio.sleep(300)


# ---------- búsqueda ----------

def _alternativas(t: str, ultimo: bool, idx: dict, corregir: bool = True) -> tuple[list[tuple[str, float]], str | None]:
    """Con qué palabras del catálogo puede coincidir una palabra de la búsqueda.
    Devuelve [(palabra_del_índice, calidad 0-1)] y, si hubo corrección, la palabra corregida."""
    alts: dict[str, float] = {}
    if t in idx:
        alts[t] = 1.0
    if ultimo and len(t) >= 2:
        # Mientras se escribe: "lec" ya sugiere "leche". Las más frecuentes primero.
        pref = [v for v in _estado["vocab"] if v.startswith(t) and v != t]
        for v in sorted(pref, key=lambda v: -_estado["frec"][v])[:25]:
            alts.setdefault(v, 0.85)
    corregida = None
    if not alts and corregir and len(t) >= 4:
        dist = 1 if len(t) < 8 else 2
        cands = process.extract(t, _estado["vocab"], scorer=DamerauLevenshtein.distance,
                                score_cutoff=dist, limit=8)
        # Casi nadie se equivoca en la primera letra: "lehce" -> leche sí, "helado" -> pelado no.
        cands = [c for c in cands if c[0][0] == t[0]]
        if cands:
            mejor = min(cands, key=lambda c: (c[1], c[0][0] != t[0], -_estado["frec"][c[0]]))
            for v, d, _ in cands:
                if d == mejor[1]:
                    alts[v] = 0.75 if d == 1 else 0.6
            corregida = mejor[0]
    return list(alts.items()), corregida


def _partir(t: str, idx: dict) -> list[str] | None:
    """'cocacola' -> ['coca', 'cola'] si ambas mitades existen en el catálogo."""
    if t in idx or len(t) < 6:
        return None
    mejores = [(t[:i], t[i:]) for i in range(3, len(t) - 2) if raiz(t[:i]) in idx and raiz(t[i:]) in idx]
    if not mejores:
        return None
    a, b = max(mejores, key=lambda ab: _estado["frec"][raiz(ab[0])] + _estado["frec"][raiz(ab[1])])
    return [raiz(a), raiz(b)]


def _es_oferta(c: str) -> bool:
    return c in OFERTA or raiz(c) in OFERTA


def _es_generica(c: str) -> bool:
    return c in GENERICAS or raiz(c) in GENERICAS


def _clave(texto: str) -> str:
    """Forma comparable de una búsqueda o un nombre de categoría: 'Cuidado Del Hogar' -> 'cuidado hogar'."""
    return " ".join(raiz(t) for t in normalizar(texto).split() if t not in STOP)


def interpretar(q: str) -> dict:
    """Pasa la búsqueda a palabras del catálogo: sinónimos, palabras pegadas, plurales."""
    norm = normalizar(q)
    for frase, reemplazo in sorted(FRASES.items(), key=lambda x: -len(x[0])):
        norm = re.sub(rf"\b{frase}\b", reemplazo, norm)
    crudos = norm.split()
    oferta = any(_es_oferta(c) for c in crudos)
    generica = any(_es_generica(c) for c in crudos)
    crudos = [c for c in crudos if not _es_generica(c)]
    resto = " ".join(c for c in crudos if c not in STOP and not _es_oferta(c))
    competidor = None
    if resto in COMPETIDORES and (resto not in COMPETIDORES_AMBIGUOS or generica):
        competidor, crudos = resto, COMPETIDORES[resto].split()
    idx = _estado["indice"]
    grupos, mostrar = [], []  # cada grupo = una palabra de la búsqueda con sus variantes
    for c in crudos:
        if c in STOP or _es_oferta(c):
            continue
        if c in SINONIMOS:
            vs = [raiz(v) for v in SINONIMOS[c]]
            grupos.append(vs); mostrar.append(c if raiz(c) in vs else SINONIMOS[c][0])
            continue
        t = raiz(c)
        partes = _partir(t, idx)
        if partes:
            grupos += [[p] for p in partes]; mostrar += [_estado["superficie"].get(p, p) for p in partes]
        else:
            grupos.append([t]); mostrar.append(c)
    return {"grupos": grupos, "mostrar": mostrar, "oferta": oferta, "normalizada": norm,
            "generica": generica or competidor is not None, "competidor": competidor, "clave": _clave(" ".join(crudos))}


def _categorias_de(clave: str) -> list[str] | None:
    """Si la búsqueda es el nombre de una familia ('bebidas', 'mascotas') o un alias ('limpieza'), sus categorías."""
    alias = {_clave(k): v for k, v in CATEGORIAS_ALIAS.items()}
    if clave in alias:
        return alias[clave]
    if clave in _estado["familias"]:
        return [_estado["familias"][clave]]
    return None


def _listar(categorias: list[str] | None, oferta: bool) -> list:
    """Lo más vendido (de unas categorías o de toda la tienda), con stock primero."""
    cats, total = set(categorias or []), len(_estado["productos"]) or 1
    res = []
    for d in _estado["productos"]:
        if cats and d["cat_hoja"] not in cats and not cats & set(d["familia"]):
            continue
        desc = min(d.get("descuento_pct") or 0, 60)
        s = (3 if d.get("top_ventas") else 0) + (2 if d["disponible"] else -50) + (1 - d["pos"] / total) * 2
        s += (desc / 10) if oferta else (desc / 60)
        res.append((s, d))
    res.sort(key=lambda x: -x[0])
    return res


def _buscar(grupos: list[list[str]], parcial: bool, oferta: bool, minimo: int | None = None):
    idx = _estado["indice"]
    if not grupos:
        return [], {}
    por_grupo, correcciones = [], {}
    for i, variantes in enumerate(grupos):
        alts: dict[str, float] = {}
        exacta = any(v in idx for v in variantes)  # "comida gato": si "alimento" existe, no corregir "comida"
        for v in variantes:
            a, corr = _alternativas(v, parcial and i == len(grupos) - 1, idx, corregir=not exacta)
            for w, q in a:
                alts[w] = max(alts.get(w, 0), q)
            if corr:
                correcciones[v] = corr
        por_grupo.append(alts)

    puntos: dict[str, list[float]] = defaultdict(lambda: [0.0] * len(grupos))
    for i, alts in enumerate(por_grupo):
        for w, calidad in alts.items():
            for pid, peso in idx.get(w, {}).items():
                s = calidad * peso
                if s > puntos[pid][i]:
                    puntos[pid][i] = s
    n = len(grupos)
    minimo = n if minimo is None else minimo
    frase = " ".join(max(alts, key=alts.get) if alts else g[0] for g, alts in zip(grupos, por_grupo))
    total = len(_estado["productos"]) or 1
    res = []
    for pid, ps in puntos.items():
        coinciden = sum(1 for x in ps if x > 0)
        if coinciden < minimo:
            continue
        d = _estado["por_id"][pid]
        s = sum(ps) / n
        palabras = [w for alts in por_grupo for w, q in alts.items() if q >= 0.75]
        if d["_cat_tokens"] & set(palabras):
            s += 3  # "leche" -> primero lo que está en la categoría Leches
            if d["_cat_norm"] == frase:
                s += 2.5  # y antes la categoría "Leche" que "Leches De Fórmula"
        if por_grupo and any(d["_nombre_norm"].startswith(" " + w + " ") for w in por_grupo[0]):
            s += 1.5
        if n > 1 and all(any(f" {w} " in d["_nombre_norm"] for w in alts) for alts in por_grupo):
            s += 1.5
        s += 2 if d["disponible"] else -6
        s += 1.5 if d.get("top_ventas") else 0
        s += 1.0 * (1 - d["pos"] / total)
        desc = min(d.get("descuento_pct") or 0, 60)
        s += (desc / 10) if oferta else (desc / 60 * 0.8)
        res.append((s, d))
    res.sort(key=lambda x: -x[0])
    return res, correcciones


def _publico(d: dict) -> dict:
    return {k: d[k] for k in ("id", "variante_id", "nombre", "marca", "precio", "precio_anterior", "descuento_pct",
                              "disponible", "stock", "max_por_compra", "envio_gratis", "url", "imagen")} | {"precio_sin_impuestos": d.get("precio_sin_impuestos")} | {"categoria": d["cat_hoja"]}


def _facetas(res: list) -> list[dict]:
    c = Counter(d["cat_hoja"] for _, d in res[:60] if d["cat_hoja"])
    return [{"nombre": k, "cantidad": v} for k, v in c.most_common(5)]


ORDENES = {
    "precio_asc": lambda d: (not d["disponible"], d["precio"] or 0),
    "precio_desc": lambda d: (not d["disponible"], -(d["precio"] or 0)),
    "descuento": lambda d: (not d["disponible"], -(d.get("descuento_pct") or 0)),
    "nombre": lambda d: (not d["disponible"], normalizar(d["nombre"])),
}


async def buscar(q: str, limite: int = 8, parcial: bool = False, categoria: str | None = None, desde: int = 0,
                 marcas: list[str] | None = None, ofertas: bool = False, orden: str = "relevancia",
                 completo: bool = False) -> dict:
    """completo=True es para la página de resultados: devuelve todas las categorías y marcas con su cantidad
    (los filtros de la columna izquierda), y acepta filtrar por marcas/ofertas y ordenar."""
    t0 = time.perf_counter()
    await actualizar()
    q = (q or "").strip()[:120]
    inter = interpretar(q)
    titulo = url_todos = None
    cats = _categorias_de(inter["clave"]) if inter["grupos"] else None
    if cats:
        # "bebidas", "limpieza", "cuidado personal": la categoría entera, lo más vendido primero.
        res, corr, via = _listar(cats, inter["oferta"]), {}, "categoria"
        nombre = cats[0] if len(cats) == 1 else " ".join(inter["mostrar"]).capitalize()
        titulo = "Lo más vendido en " + nombre
        url_todos = _estado["urls_cat"].get(cats[0])
    elif not inter["grupos"] and (inter["generica"] or inter["oferta"]):
        # "supermercado online", "coto digital", "ofertas": no nombra un producto.
        res, corr, via = _listar(None, inter["oferta"]), {}, "ofertas" if inter["oferta"] else "destacados"
        titulo = "Las mejores ofertas de Ecomodico" if inter["oferta"] else "Lo más vendido en Ecomodico"
        url_todos = "/shop"
    else:
        res, corr = _buscar(inter["grupos"], parcial, inter["oferta"])
        via = "indice"
        if not res and len(inter["grupos"]) > 1:
            # Ninguno tiene todas las palabras: aceptamos los que tienen la mayoría.
            res, corr = _buscar(inter["grupos"], parcial, inter["oferta"], minimo=max(1, math.ceil(len(inter["grupos"]) / 2)))
            via = "parcial"
    facetas = _facetas(res)
    if completo:
        # En el orden en que aparecen (la categoría más relevante primero), no por cantidad.
        facetas = [{"nombre": k, "cantidad": v} for k, v in Counter(d["cat_hoja"] for _, d in res if d["cat_hoja"]).items()]
    if categoria:
        res = [(s, d) for s, d in res if d["cat_hoja"] == categoria]
    facetas_marca, n_ofertas = [], 0
    if completo:
        facetas_marca = [{"nombre": k, "cantidad": v} for k, v in Counter(d["marca"] for _, d in res if d["marca"]).most_common()]
    if marcas:
        res = [(s, d) for s, d in res if d["marca"] in marcas]
    if completo:
        n_ofertas = sum(1 for _, d in res if (d.get("descuento_pct") or 0) > 0)
    if ofertas:
        res = [(s, d) for s, d in res if (d.get("descuento_pct") or 0) > 0]
    if orden in ORDENES:
        res = sorted(res, key=lambda x: ORDENES[orden](x[1]))
    corregida = None
    if via in ("indice", "parcial"):
        mostrar = [corr.get(raiz(m), None) for m in inter["mostrar"]]
        corregida = " ".join(_estado["superficie"].get(c, c) if c else m for c, m in zip(mostrar, inter["mostrar"]))
        # Si cambió algo más que tildes/plurales, se lo contamos al cliente ("Mostrando resultados de shampoo").
        orig = [raiz(x) for x in normalizar(q).split() if x not in STOP and not _es_oferta(x) and not _es_generica(x)]
        # Sin resultados no hay nada que "mostrar en vez de": la corrección quedaría rara ("regalo dia pares").
        if [raiz(x) for x in normalizar(corregida).split()] == orig or not corregida or not res:
            corregida = None
    if inter["competidor"] is not None and via in ("indice", "parcial", "categoria"):
        corregida = corregida or " ".join(inter["mostrar"])
    todos_en = None
    if via == "indice" and res and not url_todos:
        # "arroz", "leche", "pañales": si lo buscado es el nombre de la categoría del primer resultado, "Ver todos"
        # va a esa categoría de la tienda. La búsqueda de Drubbit pone primero jabones Rexona para "arroz".
        cat = res[0][1]["cat_hoja"]
        buscado = {raiz(x) for x in normalizar(corregida or " ".join(inter["mostrar"])).split()}
        if buscado and buscado <= res[0][1]["_cat_tokens"] and cat in _estado["urls_cat"]:
            url_todos, todos_en = _estado["urls_cat"][cat], cat
    return {
        "consulta": q,
        "corregida": corregida,
        "titulo": titulo,
        "url_todos": url_todos or ("/shop?search=" + (corregida or " ".join(inter["mostrar"]) or q)),
        "todos_en": todos_en,
        "total": len(res),
        "productos": [_publico(d) for _, d in res[max(0, desde):max(0, desde) + max(1, min(limite, 48))]],
        "categorias": facetas,
        "marcas": facetas_marca,
        "ofertas": n_ofertas,
        "via": via,
        "sugerir_ia": USAR_IA and via in ("indice", "parcial") and ((not res) or bool(FRASE_ABIERTA.search(q))),
        "ms": round((time.perf_counter() - t0) * 1000, 1),
    }


# ---------- frases: Claude traduce a términos de catálogo ----------

PROMPT_IA = """Sos el buscador de ecomodico.com, un supermercado online argentino (almacén, bebidas, limpieza,
perfumería, bebés, mascotas, suplementos deportivos, electro y hogar). El cliente escribió en el buscador:

"{q}"

Categorías que existen en el catálogo (usá estos nombres o productos concretos de ellas; no propongas
cosas que no estén): {categorias}

Devolvé SOLO un JSON con hasta 5 búsquedas cortas (1 a 3 palabras, como figuran los productos en un súper)
que respondan a lo que quiere, de la más a la menos relevante. Ej: "algo para el desayuno" ->
{{"busquedas": ["cafe", "cereales", "mermelada", "galletitas", "leche"]}}. Si no tiene sentido, {{"busquedas": []}}."""


def _cargar_cache_ia() -> None:
    if not _cache_ia and ARCHIVO_IA.exists():
        try:
            _cache_ia.update(json.loads(ARCHIVO_IA.read_text(encoding="utf-8")))
        except Exception:
            pass


async def _terminos_ia(q: str, client) -> list[str]:
    _cargar_cache_ia()
    clave = normalizar(q)
    if clave in _cache_ia:
        return _cache_ia[clave]
    r = await client.messages.create(
        model=MODELO_IA, max_tokens=1000,
        thinking={"type": "adaptive"}, output_config={"effort": "low"},
        messages=[{"role": "user", "content": PROMPT_IA.format(
            q=q, categorias=", ".join(sorted({d["cat_hoja"] for d in _estado["productos"] if d["cat_hoja"]})))}],
    )
    texto = "".join(b.text for b in r.content if b.type == "text")
    m = re.search(r"\{.*\}", texto, re.S)
    terminos = [t for t in (json.loads(m.group(0)).get("busquedas") if m else []) if isinstance(t, str)][:5]
    _cache_ia[clave] = terminos
    ARCHIVO_IA.write_text(json.dumps(_cache_ia, ensure_ascii=False, indent=1), encoding="utf-8")
    return terminos


async def buscar_con_ia(q: str, client, limite: int = 8) -> dict:
    if not USAR_IA:
        return await buscar(q, limite)
    t0 = time.perf_counter()
    await actualizar()
    terminos = await _terminos_ia(q, client)
    grupos = []
    for t in terminos:
        r = await buscar(t, limite=8)
        prods = r["productos"]
        if prods:
            principal = prods[0]["categoria"]
            grupos.append({"termino": t, "productos": [p for p in prods if p["categoria"] == principal][:4]})
    # Intercalamos: el mejor de cada término primero, así se ve variedad arriba.
    productos, vistos = [], set()
    for i in range(4):
        for g in grupos:
            if i < len(g["productos"]) and g["productos"][i]["id"] not in vistos:
                vistos.add(g["productos"][i]["id"]); productos.append(g["productos"][i])
    return {"consulta": q, "corregida": None, "terminos": terminos, "total": len(productos),
            "productos": productos[:limite], "categorias": [], "via": "ia", "sugerir_ia": False,
            "ms": round((time.perf_counter() - t0) * 1000, 1)}
