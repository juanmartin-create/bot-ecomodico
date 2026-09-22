"""Acceso al catálogo público de ecomodico.com.

El sitio (Drubbit Commerce, Vue SSR) no expone una API pública documentada, pero
cada página renderizada trae el estado completo en `window.__SERVER_DATA__`.
Leemos eso: es la misma información que ve el cliente en la web, en tiempo real.
"""

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
    data = json.loads(m.group(1).strip().rstrip(";"))["_resolvedData"]
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
    return {
        "id": p["id"],
        "variante_id": v.get("id"),
        "nombre": p["name"],
        "marca": (p.get("brand") or {}).get("name"),
        "categoria": " > ".join(c["name"] for c in p.get("categories", [])),
        "precio": actual,
        "precio_anterior": prev if prev > actual else None,
        "descuento_pct": round(precio.get("discountPct") or 0) or None,
        "stock": stock.get("qty"),
        "disponible": stock.get("availability") == "InStock" and p.get("buyable", True),
        "url": f"{BASE}/p/{p['urlName']}/{p['id']}",
        "imagen": img,
    }


async def buscar_productos(consulta: str, orden: str = "relevancia", limite: int = 8) -> dict:
    sort = SORTS.get(orden)
    path = f"/shop/sort-by-{sort}" if sort else "/shop"
    data = await _server_data(f"{path}?search={quote(consulta)}")
    shop = data.get("shop") or {}
    productos = [_resumen(p) for p in shop.get("products", [])]
    productos = [p for p in productos if p["disponible"]] + [p for p in productos if not p["disponible"]]
    return {
        "consulta": consulta,
        "total_resultados": (shop.get("pagination") or {}).get("itemsLength", len(productos)),
        "productos": productos[: max(1, min(limite, 12))],
    }


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
