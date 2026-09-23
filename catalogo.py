"""Acceso al catálogo público de ecomodico.com.

El sitio (Drubbit Commerce, Vue SSR) no expone una API pública documentada, pero
cada página renderizada trae el estado completo en `window.__SERVER_DATA__`.
Leemos eso: es la misma información que ve el cliente en la web, en tiempo real.
"""

import asyncio
import json
import re
import time
from urllib.parse import quote

import httpx

BASE = "https://ecomodico.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (EcomodicoBot/0.1)"}
SORTS = {
    "relevancia": None,
    "mayor_descuento": "discount-high-to-low",
    "menor_precio": "price-low-to-high",
    "mayor_precio": "price-high-to-low",
}
_SERVER_DATA = re.compile(r"window\.__SERVER_DATA__\s*=\s*(.*?)</script>", re.S)
_CACHE: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 300  # 5 min: precios y stock cambian, pero no cada segundo

# Regla de envío gratis de la tienda (orderTotalGoalProgressConfig). Se actualiza con
# lo que dice el sitio en cada página que leemos; estos son los valores de respaldo.
ENVIO_GRATIS = {"coleccion": "57", "meta": 75000,
                "descripcion": "Envío gratis para CABA y AMBA (no incluye productos de Electro y Hogar)"}

_http = httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True)


async def _server_data(path: str) -> dict:
    hit = _CACHE.get(path)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    r = await _http.get(BASE + path)
    r.raise_for_status()
    m = _SERVER_DATA.search(r.text)
    if not m:
        raise RuntimeError(f"No se encontró __SERVER_DATA__ en {path}")
    todo = json.loads(m.group(1).strip().rstrip(";"))
    cfg = todo.get("orderTotalGoalProgressConfig") or {}
    if cfg.get("collectionId") and cfg.get("orderTotalGoal"):
        ENVIO_GRATIS.update(coleccion=str(cfg["collectionId"]), meta=int(float(cfg["orderTotalGoal"])),
                            descripcion=cfg.get("description") or ENVIO_GRATIS["descripcion"])
    data = todo["_resolvedData"]
    _CACHE[path] = (time.time(), data)
    return data


def _resumen(p: dict) -> dict:
    """Reduce un producto de Drubbit a lo que el vendedor necesita."""
    v = next((x for x in p.get("variants", []) if x.get("main")), (p.get("variants") or [{}])[0])
    precio = v.get("pvPrice") or {}
    stock = v.get("stock") or {}
    imgs = p.get("images") or []
    img = None
    if imgs:
        sq = imgs[0].get("square") or imgs[0].get("thumb") or {}
        img = sq.get("fullUrl") or imgs[0].get("fullUrl")
    prev = precio.get("prevPrice") or 0
    actual = precio.get("price") or 0
    disponible = stock.get("availability") == "InStock" and p.get("buyable", True)
    qty = None if stock.get("infiniteQty") else stock.get("qty")
    return {
        "id": p["id"],
        "variante_id": v.get("id"),
        "nombre": p["name"],
        "marca": (p.get("brand") or {}).get("name"),
        "categoria": " > ".join(c["name"] for c in p.get("categories", [])),
        "precio": actual,
        "precio_anterior": prev if prev > actual else None,
        "descuento_pct": round(precio.get("discountPct") or 0) or None,
        "stock": qty if disponible else 0,
        "disponible": disponible,
        "max_por_compra": stock.get("maxBuyableQty"),
        "envio_gratis": ENVIO_GRATIS["coleccion"] in [str(c) for c in p.get("collectionsIds") or []],
        "url": f"{BASE}/p/{p['urlName']}/{p['id']}",
        "imagen": img,
    }


async def buscar_productos(consulta: str, orden: str = "relevancia", limite: int = 8) -> dict:
    sort = SORTS.get(orden)
    path = f"/shop/sort-by-{sort}" if sort else "/shop"
    data = await _server_data(f"{path}?search={quote(consulta)}")
    shop = data.get("shop") or {}
    todos = [_resumen(p) for p in shop.get("products", [])]
    con_stock = [p for p in todos if p["disponible"]]
    sin_stock = [p for p in todos if not p["disponible"]]
    limite = max(1, min(limite, 12))
    # Primero lo que se puede comprar. Lo agotado solo si hace falta para completar.
    productos = con_stock[:limite]
    if len(productos) < 3:
        productos += sin_stock[: limite - len(productos)]
    return {
        "consulta": consulta,
        "total_resultados": (shop.get("pagination") or {}).get("itemsLength", len(todos)),
        "sin_stock_omitidos": max(0, len(sin_stock) - (len(productos) - len(con_stock[:limite]))),
        "productos": productos,
    }


async def buscar_varios(consultas: list[str], orden: str = "relevancia", limite: int = 4) -> dict:
    """Varias búsquedas en paralelo (ej. una lista de compras)."""
    consultas = [c.strip() for c in consultas if isinstance(c, str) and c.strip()][:12]
    resultados = await asyncio.gather(*(buscar_productos(c, orden, limite) for c in consultas), return_exceptions=True)
    salida = []
    for consulta, r in zip(consultas, resultados):
        if isinstance(r, Exception):
            salida.append({"consulta": consulta, "error": str(r), "productos": []})
        else:
            salida.append(r)
    return {"busquedas": salida}


async def ver_producto(url: str) -> dict:
    m = re.search(r"/p/[^/?#]+/[0-9a-f-]{36}", url)
    if not m:
        raise ValueError("URL de producto inválida; tiene que ser https://ecomodico.com/p/<nombre>/<id>")
    data = await _server_data(m.group(0))
    p = data["product"]
    info = p.get("info") or {}
    desc = (info.get("templateData") or {}).get("description") or info.get("description") or ""
    out = _resumen(p)
    out["descripcion"] = re.sub(r"<[^>]+>", " ", desc)[:2500]
    out["atributos"] = {a["attrKey"]["k"]: a["v"] for a in p.get("attrs", []) if a.get("attrKey")}
    out["relacionados"] = [_resumen(r) for r in (data.get("relatedProducts") or [])[:4]]
    return out
