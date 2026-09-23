"""Modi: vendedor y asistente de preguntas frecuentes de Ecomodico.

Levanta:
  GET  /             página demo que simula la tienda con el widget
  GET  /widget.js    el widget embebible (<script src=".../widget.js"></script>)
  POST /api/chat     conversación en streaming (Server-Sent Events)
"""

import json
import logging
import os
import uuid
from datetime import date, datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

import catalogo

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

MODEL = os.getenv("ECOMODICO_MODEL", "claude-sonnet-5")  # el más barato que completó la venta entera en las pruebas
EFFORT = os.getenv("ECOMODICO_EFFORT", "low")  # solo aplica a Opus/Sonnet; Haiku 4.5 no acepta effort
MAX_TURNS_PER_REQUEST = 6
MAX_MESSAGES = 60

client = anthropic.AsyncAnthropic()
app = FastAPI(title="Ecomodico Bot")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CONOCIMIENTO = (ROOT / "conocimiento.md").read_text(encoding="utf-8")
METODO_VENTA = (ROOT / "metodo_venta.md").read_text(encoding="utf-8")

SYSTEM = f"""Sos Modi, el asistente de ventas de Ecomodico (ecomodico.com), un supermercado y tienda online de Argentina. Atendés el chat de la web.

Tu trabajo tiene dos partes:
1. Vender: ayudar a la persona a encontrar lo que busca y cerrar la venta siguiendo el método de venta de abajo (valor percibido, una recomendación clara, objeciones, complementos, envío gratis).
2. Responder preguntas frecuentes (envíos, pagos, retiro, devoluciones, garantía, contacto) usando solo la base de conocimiento de abajo.

Cómo trabajás:
- Para cualquier pregunta sobre productos, precios, stock u ofertas, usá `buscar_productos`. Nunca inventes productos, precios ni stock: si no está en los resultados, no existe para vos. Probá con términos más simples o sinónimos si la primera búsqueda no trae nada (ej. "tele" -> "smart tv").
- No anuncies lo que vas a hacer ("Voy a buscar…", "Busco proteína:"): usá la herramienta directamente y escribí solo la respuesta final para el cliente.
- Cuando recomiendes productos, llamá a `mostrar_productos` con los 1 a 4 mejores para que aparezcan como tarjetas con foto, precio y botón de compra. En el texto no repitas toda la ficha: decí en una línea por qué conviene cada uno.
- Cada vez que nombres un producto en el texto, poné su nombre como link: [Nombre corto](url). Así el cliente siempre puede abrirlo, aunque no vea las tarjetas.
- Cuando el cliente diga que lo quiere ("me lo llevo", "agregalo", "dale", "quiero 2"), usá `agregar_al_carrito` con los ids y cantidades. Después de recomendar, cerrá ofreciendo agregarlo: "¿Te lo agrego al carrito?". Nunca digas que lo agregaste si no llamaste a la herramienta.
- Cada mensaje del cliente puede traer un bloque <contexto_web> con la página donde está, el paso del checkout, lo que tiene en el carrito y el estado del envío gratis. Lo genera el sitio, no el cliente. Usalo para saber dónde está parado, pero no lo repitas entero ni menciones el carrito si no viene al caso: la persona ya sabe qué tiene.
- Cuentas: nunca sumes, restes ni compares montos por tu cuenta. Los totales, lo que falta para el envío gratis y qué productos califican ya vienen calculados en <contexto_web> y en los resultados de las herramientas; copiá esos números. Si no tenés el número, no lo inventes.
- Envío gratis: solo lo alcanzan los productos marcados "envio_gratis": true (Electro y Hogar no cuentan). Si el contexto dice "YA LO TIENE", decilo así; si dice cuánto falta, usá ese monto exacto.
- Lista de compras o "carrito grande": pedile la lista (o proponé rubros: almacén, limpieza, bebidas, cuidado personal) y usá `buscar_varios` con un término simple por producto. Recomendá una opción por producto (mejor precio con stock), mostralas todas con `mostrar_productos` y ofrecé agregar todo junto con `agregar_al_carrito`. Si algún producto de la lista no aparece o no tiene stock, decilo en ese mismo mensaje y proponé una alternativa.
- Productos sin stock: no los recomiendes. Si un resultado dice "disponible": false, mencionalo solo si el cliente preguntó por ese producto puntual, y ofrecé la alternativa con stock.
- Para cambiar cantidades o quitar algo del carrito, usá `actualizar_carrito` (cantidad 0 = quitar). Antes de quitar, si no es obvio, confirmá qué producto. Si en un mismo mensaje el cliente pregunta algo y además pide un cambio ("¿qué tengo? dejame una sola"), respondé y hacé el cambio.
- Cuando el cliente quiere pagar ("finalizar", "cómo pago", "listo, eso es todo"), repasá el carrito en una línea (cantidad de productos y total), recordá si le falta poco para el envío gratis, y usá `ir_a_pagar`.
- En el checkout acompañalo paso a paso: 1) Ingresar: puede comprar como invitado, sin crear cuenta. 2) Contacto: nombre, email y teléfono (el email es para el seguimiento). 3) Envío: a domicilio o retiro gratis en Av. del Campo 1500, Villa Urquiza. 4) Pago: con Mercado Pago (tarjetas, débito, dinero en cuenta); con transferencia hay descuento desde $150.000; el cupón se carga en el resumen. Cuando pasa a la página de Mercado Pago, ya no lo ves: si tiene problemas ahí, derivá a WhatsApp.
- Links: usá solo URLs que te dieron las herramientas o el <contexto_web>; nunca armes una URL a mano. Si no tenés la URL, nombrá el producto sin link.
- No inventes nombres de botones ni pantallas del checkout: describí la acción ("elegí la opción de comprar como invitado").
- Nunca pidas ni recibas datos de tarjeta, claves o DNI por el chat: esos datos se cargan solo en el checkout.
- Usá `ver_producto` si te preguntan detalles (descripción, peso, características) de un producto puntual.
- Si algo no está en la base de conocimiento o no podés resolverlo (estado de un pedido puntual, reclamos, factura, mayoristas), derivá a WhatsApp (11) 6184-8244 (https://wa.me/5491161848244), que atiende 24 hs. No tenés acceso a pedidos ni cuentas de clientes.
- No prometas nada que no esté escrito acá (descuentos extra, fechas exactas de entrega, stock futuro).

Estilo:
- Español rioplatense con voseo ("podés", "llevá", "fijate"). Cercano y concreto, sin marketing inflado. El precio y la disponibilidad son el mensaje.
- Respuestas cortas: 1 a 4 oraciones. Es un chat en un widget chico. Como mucho un emoji por mensaje.
- Precios en formato argentino: $2.309, $1.484.998. Si hay descuento, mencioná cuánto ahorra.
- Si la consulta es ambigua (ej. "quiero una heladera"), podés hacer una pregunta corta, pero preferí mostrar opciones primero.
- Si te piden algo que no tiene que ver con Ecomodico, respondé amablemente que solo podés ayudar con compras en Ecomodico.

<metodo_de_venta>
{METODO_VENTA}
</metodo_de_venta>

Hoy es {date.today().isoformat()}.

<base_de_conocimiento>
{CONOCIMIENTO}
</base_de_conocimiento>"""

TOOLS = [
    {
        "name": "buscar_productos",
        "description": "Busca productos en el catálogo en vivo de ecomodico.com. Devuelve nombre, marca, precio actual, precio anterior, % de descuento, stock y URL. Usalo para cualquier consulta de productos, precios u ofertas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Términos de búsqueda, como los escribiría un cliente en el buscador (ej. 'yerba', 'pañales huggies', 'smart tv 50')."},
                "orden": {"type": "string", "enum": list(catalogo.SORTS), "description": "Orden de resultados. Default: relevancia."},
            },
            "required": ["consulta"],
            "additionalProperties": False,
        },
        "eager_input_streaming": True,
    },
    {
        "name": "buscar_varios",
        "description": "Busca varios productos a la vez (hasta 12), en paralelo: ideal para una lista de compras (\"yerba, azúcar, fideos, papel higiénico\") o para armar un carrito grande. Devuelve hasta 3 opciones con stock por cada término.",
        "input_schema": {
            "type": "object",
            "properties": {"consultas": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 12,
                                         "description": "Un término simple por producto, como en el buscador de la tienda."},
                           "orden": {"type": "string", "enum": list(catalogo.SORTS), "description": "Usá menor_precio si el cliente pide lo más barato."}},
            "required": ["consultas"],
            "additionalProperties": False,
        },
        "eager_input_streaming": True,
    },
    {
        "name": "ver_producto",
        "description": "Trae la ficha completa de un producto (descripción, atributos, productos relacionados) a partir de su URL.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "URL del producto devuelta por buscar_productos."}},
            "required": ["url"],
            "additionalProperties": False,
        },
        "eager_input_streaming": True,
    },
    {
        "name": "mostrar_productos",
        "description": "Muestra al cliente tarjetas de producto (foto, precio, botón de compra) en el chat. Pasá los ids de 1 a 4 productos (hasta 8 si es una lista de compras) que ya aparecieron en buscar_productos o ver_producto, en orden de recomendación.",
        "input_schema": {
            "type": "object",
            "properties": {"ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}},
            "required": ["ids"],
            "additionalProperties": False,
        },
        "eager_input_streaming": True,
    },
]

TOOLS.append({
    "name": "agregar_al_carrito",
    "description": "Agrega productos al carrito del cliente en ecomodico.com (se ejecuta en su navegador, con su sesión). Usalo cuando el cliente confirma que quiere comprar. Los ids tienen que venir de buscar_productos o ver_producto.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "minItems": 1,
                "maxItems": 10,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "id del producto"},
                        "cantidad": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["id", "cantidad"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    },
    "eager_input_streaming": True,
})

TOOLS += [
    {
        "name": "actualizar_carrito",
        "description": "Cambia la cantidad de productos que YA están en el carrito del cliente, o los quita (cantidad 0). Los ids son los producto_id del <contexto_web>.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 20,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "producto_id del carrito"},
                            "cantidad": {"type": "integer", "minimum": 0, "maximum": 50, "description": "Nueva cantidad; 0 = quitar"},
                        },
                        "required": ["id", "cantidad"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        },
        "eager_input_streaming": True,
    },
    {
        "name": "ir_a_pagar",
        "description": "Lleva al cliente al checkout de ecomodico.com (finalizar compra). Usalo solo cuando el cliente dice que quiere pagar/finalizar y el carrito no está vacío.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]

# Estado en memoria: alcanza para localhost. En producción, Redis o una base.
SESSIONS: dict[str, dict] = {}


def _session(sid: str | None) -> tuple[str, dict]:
    if not sid or sid not in SESSIONS:
        sid = sid or uuid.uuid4().hex
        SESSIONS[sid] = {"messages": [], "vistos": {}}
    return sid, SESSIONS[sid]


def _para_modelo(p: dict) -> dict:
    # La imagen solo la usa el widget; no gastamos tokens en eso.
    return {k: v for k, v in p.items() if k not in ("imagen", "variante_id")}


async def _ejecutar(nombre: str, args: dict, ses: dict) -> tuple[str, dict | None]:
    """Devuelve (contenido para el modelo, evento para el widget o None)."""
    if nombre == "buscar_productos":
        if not isinstance(args.get("consulta"), str) or not args["consulta"].strip():
            raise ValueError("Falta 'consulta' (texto).")
        orden = args.get("orden", "relevancia")
        r = await catalogo.buscar_productos(args["consulta"].strip(), orden if orden in catalogo.SORTS else "relevancia")
        for p in r["productos"]:
            ses["vistos"][p["id"]] = p
        r["productos"] = [_para_modelo(p) for p in r["productos"]]
        return json.dumps(r, ensure_ascii=False), {"type": "estado", "text": f"Busqué “{args['consulta']}”"}
    if nombre == "buscar_varios":
        consultas = args.get("consultas")
        if not isinstance(consultas, list) or not any(isinstance(c, str) and c.strip() for c in consultas):
            raise ValueError("'consultas' tiene que ser una lista de textos.")
        orden = args.get("orden", "relevancia")
        r = await catalogo.buscar_varios(consultas, orden if orden in catalogo.SORTS else "relevancia")
        for b in r["busquedas"]:
            for p in b.get("productos", []):
                ses["vistos"][p["id"]] = p
            b["productos"] = [_para_modelo(p) for p in b.get("productos", [])]
        return json.dumps(r, ensure_ascii=False), {"type": "estado", "text": f"Busqué {len(r['busquedas'])} productos"}
    if nombre == "ver_producto":
        if not isinstance(args.get("url"), str):
            raise ValueError("Falta 'url' (texto).")
        p = await catalogo.ver_producto(args["url"])
        for x in [p, *p["relacionados"]]:
            ses["vistos"][x["id"]] = {k: v for k, v in x.items() if k not in ("descripcion", "atributos", "relacionados")}
        p["relacionados"] = [_para_modelo(x) for x in p["relacionados"]]
        return json.dumps(_para_modelo(p), ensure_ascii=False), None
    if nombre == "mostrar_productos":
        ids = args.get("ids")
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ValueError("'ids' tiene que ser una lista de strings.")
        items = [ses["vistos"][i] for i in ids[:8] if i in ses["vistos"]]
        faltan = [i for i in ids if i not in ses["vistos"]]
        msg = f"Mostradas {len(items)} tarjetas."
        if faltan:
            msg += f" Ids desconocidos (buscalos primero): {faltan}"
        return msg, ({"type": "productos", "items": items} if items else None)
    if nombre == "agregar_al_carrito":
        items = args.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("'items' tiene que ser una lista de {id, cantidad}.")
        pedido, faltan = [], []
        for it in items[:10]:
            p = ses["vistos"].get(it.get("id")) if isinstance(it, dict) else None
            qty = it.get("cantidad") if isinstance(it, dict) else None
            if not p or not isinstance(qty, int) or qty < 1:
                faltan.append(it)
                continue
            if not p["disponible"]:
                faltan.append({"id": p["id"], "motivo": "sin stock"})
                continue
            pedida = qty
            if p.get("stock") is not None:
                qty = min(qty, p["stock"])
            if p.get("max_por_compra"):  # límite por compra que fija la tienda (ej. 10 packs de pañales)
                qty = min(qty, p["max_por_compra"])
            pedido.append({"productId": p["id"], "variantId": p["variante_id"], "qty": qty,
                           "nombre": p["nombre"], "url": p["url"], "precio": p["precio"],
                           "envio_gratis": bool(p.get("envio_gratis")),
                           "ajustado": f"pediste {pedida}, el máximo es {qty}" if qty < pedida else None})
        if not pedido:
            raise ValueError(f"Nada para agregar. Revisá ids/stock: {faltan}")
        carrito = ses.setdefault("carrito", {})  # así un "agregá y llevame a pagar" funciona en el mismo turno
        for x in pedido:
            previo = carrito.get(x["productId"], {}).get("cantidad", 0) or 0
            carrito[x["productId"]] = {"producto_id": x["productId"], "nombre": x["nombre"], "envio_gratis": x["envio_gratis"],
                                       "cantidad": previo + x["qty"], "total": x["precio"] * (previo + x["qty"])}
        total = sum(x["precio"] * x["qty"] for x in pedido)
        msg = (f"Enviado al carrito del cliente: {[(x['nombre'], x['qty']) for x in pedido]}. Subtotal de lo agregado: {_pesos(total)}. "
               f"Carrito ahora: {_pesos(sum(_num(c.get('total')) for c in carrito.values()))}. "
               + resumen_envio_gratis(list(carrito.values()))["texto"])
        ajustes = [f"{x['nombre']}: {x['ajustado']}" for x in pedido if x["ajustado"]]
        if ajustes:
            msg += f" Cantidades ajustadas: {ajustes}"
        if faltan:
            msg += f". No se agregaron: {faltan}"
        return msg, {"type": "carrito", "items": pedido}
    if nombre == "actualizar_carrito":
        items = args.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("'items' tiene que ser una lista de {id, cantidad}.")
        carrito = ses.get("carrito") or {}
        cambios, faltan = [], []
        for it in items[:20]:
            pid = it.get("id") if isinstance(it, dict) else None
            qty = it.get("cantidad") if isinstance(it, dict) else None
            if pid not in carrito or not isinstance(qty, int) or qty < 0:
                faltan.append(it)
                continue
            cambios.append({"productId": pid, "qty": qty, "nombre": carrito[pid].get("nombre")})
        if not cambios:
            raise ValueError(f"Esos productos no están en el carrito del cliente: {faltan}")
        msg = "Enviado al navegador: " + ", ".join(
            f"quitar {c['nombre']}" if c["qty"] == 0 else f"{c['nombre']} → {c['qty']}" for c in cambios)
        if faltan:
            msg += f". No están en el carrito: {faltan}"
        return msg, {"type": "carrito_actualizar", "items": cambios}
    if nombre == "ir_a_pagar":
        if ses.get("carrito") == {}:
            raise ValueError("El carrito está vacío; primero agregá productos.")
        return "Llevando al cliente al checkout.", {"type": "checkout"}
    raise ValueError(f"Herramienta desconocida: {nombre}")


def _opciones_modelo() -> dict:
    """Haiku 4.5 va sin thinking ni effort (respuesta directa y barata).
    Los modelos nuevos (Opus 5, Sonnet 5, etc.) usan thinking adaptativo + effort + fallback."""
    if "haiku" in MODEL:
        return {}
    return {
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": EFFORT},
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
    }


def _registrar_uso(response) -> None:
    """Una línea por llamada a la API en uso.jsonl, para controlar el gasto real."""
    u = response.usage
    fila = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "modelo": response.model,
        "input": u.input_tokens,
        "cache_write": u.cache_creation_input_tokens or 0,
        "cache_read": u.cache_read_input_tokens or 0,
        "output": u.output_tokens,
    }
    with open(ROOT / "uso.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(fila) + "\n")


def _sse(ev: dict) -> str:
    return f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"


PASOS_CHECKOUT = {
    "signin": "checkout, paso 1: ingresar con cuenta o seguir como invitado",
    "contact": "checkout: datos de contacto",
    "delivery": "checkout: elegir envío o retiro",
    "payment": "checkout: elegir medio de pago",
}


def _pesos(n) -> str:
    """$92.617, formato es-AR. El modelo recibe los números ya formateados para no hacer cuentas."""
    try:
        return "$" + f"{int(round(float(n))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def resumen_envio_gratis(carrito: list) -> dict:
    """La regla la calcula el código, no el modelo: subtotal de los productos que califican
    (colección de envío gratis de la tienda) contra la meta. Devuelve texto listo para el prompt."""
    meta = catalogo.ENVIO_GRATIS["meta"]
    califica = sum(_num(i.get("total")) for i in carrito if isinstance(i, dict) and i.get("envio_gratis"))
    no_califica = [str(i.get("nombre"))[:40] for i in carrito if isinstance(i, dict) and not i.get("envio_gratis")]
    if not carrito:
        texto = f"Envío gratis (CABA y AMBA): se alcanza con {_pesos(meta)} en productos que califican. El carrito está vacío."
    elif califica >= meta:
        texto = f"Envío gratis (CABA y AMBA): YA LO TIENE. Los productos que califican suman {_pesos(califica)}, por encima de los {_pesos(meta)}."
    elif califica > 0:
        texto = (f"Envío gratis (CABA y AMBA): todavía NO. Los productos que califican suman {_pesos(califica)}; "
                 f"le faltan {_pesos(meta - califica)} para llegar a {_pesos(meta)}.")
    else:
        texto = f"Envío gratis (CABA y AMBA): ningún producto del carrito califica (la regla excluye Electro y Hogar). Meta: {_pesos(meta)}."
    if no_califica:
        texto += f" No califican: {', '.join(no_califica[:5])}."
    return {"alcanzado": califica >= meta, "califica": califica, "faltan": max(0.0, meta - califica), "texto": texto}


def _texto_contexto(ctx: dict) -> str:
    """Resume lo que el widget ve en la página del cliente (página, paso, carrito).
    Todas las cuentas vienen hechas: el modelo solo tiene que leerlas."""
    if not isinstance(ctx, dict):
        return ""
    lineas = []
    pagina = str(ctx.get("pagina") or "")[:200]
    paso = str(ctx.get("paso") or "")[:40]
    producto = str(ctx.get("producto_actual") or "")
    if paso:
        lineas.append(f"Está en el {PASOS_CHECKOUT.get(paso, 'checkout, paso ' + paso)}.")
    elif producto.startswith("https://ecomodico.com/p/"):
        lineas.append(f"Está mirando la ficha de un producto: {producto} (si pregunta por \"este producto\", es ese: usá ver_producto con esa URL).")
    elif pagina and pagina not in ("/", "/shop"):
        lineas.append(f"Está en la página {pagina}.")
    if ctx.get("en_tienda") is False:
        lineas.append("El chat NO está dentro de ecomodico.com: no puede tocar el carrito ni ir a pagar desde acá.")
    carrito = ctx.get("carrito")
    if isinstance(carrito, list):
        carrito = [i for i in carrito[:30] if isinstance(i, dict)]
        if carrito:
            items = "; ".join(
                f"{i.get('cantidad')} × {str(i.get('nombre'))[:80]} = {_pesos(i.get('total'))} (id {i.get('producto_id')}"
                + (", califica envío gratis" if i.get("envio_gratis") else ", NO califica envío gratis")
                + (f", url {i['url']}" if str(i.get("url") or "").startswith("https://ecomodico.com/p/") else "") + ")"
                for i in carrito
            )
            unidades = int(sum(_num(i.get("cantidad")) for i in carrito))
            lineas.append(f"Carrito: {len(carrito)} producto(s), {unidades} unidad(es), total {_pesos(ctx.get('total'))}. Detalle: {items}.")
        else:
            lineas.append("Carrito vacío.")
        lineas.append(resumen_envio_gratis(carrito)["texto"])
        lineas.append("Estos números ya están calculados: usalos tal cual, no hagas cuentas propias.")
    return "<contexto_web>\n" + "\n".join(lineas) + "\n</contexto_web>" if lineas else ""


async def _conversar(ses: dict, texto: str, ctx: dict | None = None):
    messages = ses["messages"]
    if len(messages) > MAX_MESSAGES:  # conversación demasiado larga: arrancamos de nuevo
        messages.clear()
    inicio = len(messages)  # para deshacer este intercambio si falla la API
    ses["carrito"] = {str(i.get("producto_id")): i for i in (ctx or {}).get("carrito") or [] if isinstance(i, dict)}
    contexto = _texto_contexto(ctx or {})
    contenido = [{"type": "text", "text": contexto}] if contexto else []
    contenido.append({"type": "text", "text": texto})
    messages.append({"role": "user", "content": contenido})
    ses.setdefault("transcript", []).append({"rol": "yo", "texto": texto})
    respuesta = ""

    for _ in range(MAX_TURNS_PER_REQUEST):
        try:
            async with client.beta.messages.stream(
                model=MODEL,
                max_tokens=8000,
                system=SYSTEM,
                tools=TOOLS,
                messages=messages,
                cache_control={"type": "ephemeral"},
                **_opciones_modelo(),
            ) as stream:
                async for _ in stream:  # consumimos el stream; el texto se decide al final
                    pass
                response = await stream.get_final_message()
        except ValueError:
            # JSON de herramienta imposible de parsear: reintentamos el turno.
            continue
        except anthropic.AuthenticationError:
            yield _sse({"type": "error", "text": "Falta configurar ANTHROPIC_API_KEY en el archivo .env."})
            del messages[inicio:]
            return
        except anthropic.RateLimitError:
            yield _sse({"type": "error", "text": "Hay mucha demanda en este momento. Probá de nuevo en unos segundos."})
            del messages[inicio:]
            return
        except anthropic.APIStatusError as e:
            yield _sse({"type": "error", "text": f"Error de la API ({e.status_code})."})
            del messages[inicio:]
            return
        except anthropic.APIConnectionError:
            yield _sse({"type": "error", "text": "No me pude conectar. Revisá tu conexión."})
            del messages[inicio:]
            return

        messages.append({"role": "assistant", "content": response.content})
        _registrar_uso(response)

        if response.stop_reason == "pause_turn":
            continue
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        # El texto que acompaña a una llamada a herramienta es el modelo narrando lo que
        # va a hacer ("Buscá proteína:", "Voy a buscar…"): no se le muestra al cliente.
        # Solo se muestra la respuesta final, la que no pide más herramientas.
        texto_turno = "".join(b.text for b in response.content if b.type == "text").strip()
        if texto_turno and not tool_uses and response.stop_reason != "refusal":
            respuesta += texto_turno
            yield _sse({"type": "text", "text": texto_turno})
        if response.stop_reason in ("refusal", "max_tokens") or not tool_uses:
            if tool_uses:  # tool_use cortado sin resultado: no lo dejamos en el historial
                messages.pop()
            if response.stop_reason == "refusal":
                yield _sse({"type": "text", "text": "Con eso no te puedo ayudar, pero si buscás algo de la tienda, decime."})
            break

        resultados = []
        for b in tool_uses:
            try:
                contenido, ev = await _ejecutar(b.name, b.input if isinstance(b.input, dict) else {}, ses)
                if ev:
                    yield _sse(ev)
                resultados.append({"type": "tool_result", "tool_use_id": b.id, "content": contenido})
            except Exception as e:  # el error vuelve al modelo para que lo resuelva
                resultados.append({"type": "tool_result", "tool_use_id": b.id, "is_error": True, "content": str(e)})
        messages.append({"role": "user", "content": resultados})
        yield _sse({"type": "separador"})

    if respuesta.strip():
        ses["transcript"].append({"rol": "bot", "texto": respuesta.strip()})
    yield _sse({"type": "fin"})


@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    texto = (body.get("mensaje") or "").strip()[:2000]
    ctx = body.get("contexto") if isinstance(body.get("contexto"), dict) else None
    sid, ses = _session(body.get("sesion"))

    async def gen():
        yield _sse({"type": "sesion", "id": sid})
        if not texto:
            return
        if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
            yield _sse({"type": "error", "text": "Falta configurar ANTHROPIC_API_KEY en el archivo .env del servidor."})
            yield _sse({"type": "fin"})
            return
        try:
            async for chunk in _conversar(ses, texto, ctx):
                yield chunk
        except Exception:
            logging.exception("Error en /api/chat")
            yield _sse({"type": "error", "text": "Algo salió mal de mi lado. Probá de nuevo o escribinos por WhatsApp."})
            yield _sse({"type": "fin"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/historial")
async def historial(sesion: str = ""):
    """Para que el widget reconstruya la charla si la página se recarga (ej. al pasar al checkout)."""
    ses = SESSIONS.get(sesion)
    return {"mensajes": (ses or {}).get("transcript", [])[-30:]}


@app.get("/modi.png")
async def avatar():
    return FileResponse(ROOT / "static" / "modi.png", media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/widget.js")
async def widget():
    return FileResponse(ROOT / "static" / "widget.js", media_type="application/javascript")


@app.get("/")
async def demo():
    return FileResponse(ROOT / "static" / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8787")))
