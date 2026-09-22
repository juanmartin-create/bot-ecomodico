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

MODEL = os.getenv("ECOMODICO_MODEL", "claude-haiku-4-5")  # el más barato; alcanza para un chat de venta
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
- Cuando recomiendes productos, llamá a `mostrar_productos` con los 1 a 4 mejores para que aparezcan como tarjetas con foto, precio y botón de compra. En el texto no repitas toda la ficha: decí en una línea por qué conviene cada uno.
- Cada vez que nombres un producto en el texto, poné su nombre como link: [Nombre corto](url). Así el cliente siempre puede abrirlo, aunque no vea las tarjetas.
- Cuando el cliente diga que lo quiere ("me lo llevo", "agregalo", "dale", "quiero 2"), usá `agregar_al_carrito` con los ids y cantidades. Después de recomendar, cerrá ofreciendo agregarlo: "¿Te lo agrego al carrito?". Nunca digas que lo agregaste si no llamaste a la herramienta.
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
        "description": "Muestra al cliente tarjetas de producto (foto, precio, botón de compra) en el chat. Pasá los ids de 1 a 4 productos que ya aparecieron en buscar_productos o ver_producto, en orden de recomendación.",
        "input_schema": {
            "type": "object",
            "properties": {"ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4}},
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
        items = [ses["vistos"][i] for i in ids[:4] if i in ses["vistos"]]
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
            if p.get("stock") is not None:
                qty = min(qty, p["stock"])
            pedido.append({"productId": p["id"], "variantId": p["variante_id"], "qty": qty,
                           "nombre": p["nombre"], "url": p["url"], "precio": p["precio"]})
        if not pedido:
            raise ValueError(f"Nada para agregar. Revisá ids/stock: {faltan}")
        total = sum(x["precio"] * x["qty"] for x in pedido)
        msg = f"Enviado al carrito del cliente: {[(x['nombre'], x['qty']) for x in pedido]}. Subtotal de lo agregado: ${total:,.0f}".replace(",", ".")
        if faltan:
            msg += f". No se agregaron: {faltan}"
        return msg, {"type": "carrito", "items": pedido}
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


async def _conversar(ses: dict, texto: str):
    messages = ses["messages"]
    if len(messages) > MAX_MESSAGES:  # conversación demasiado larga: arrancamos de nuevo
        messages.clear()
    inicio = len(messages)  # para deshacer este intercambio si falla la API
    messages.append({"role": "user", "content": texto})

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
                async for event in stream:
                    if event.type == "text":
                        yield _sse({"type": "text", "text": event.text})
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

    yield _sse({"type": "fin"})


@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    texto = (body.get("mensaje") or "").strip()[:2000]
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
            async for chunk in _conversar(ses, texto):
                yield chunk
        except Exception:
            logging.exception("Error en /api/chat")
            yield _sse({"type": "error", "text": "Algo salió mal de mi lado. Probá de nuevo o escribinos por WhatsApp."})
            yield _sse({"type": "fin"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/widget.js")
async def widget():
    return FileResponse(ROOT / "static" / "widget.js", media_type="application/javascript")


@app.get("/")
async def demo():
    return FileResponse(ROOT / "static" / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8787")))
