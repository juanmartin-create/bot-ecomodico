"""Registro de conversaciones en SQLite (datos.db): cada mensaje, cada acción del bot,
cada evento del widget (chat abierto, agregado al carrito, checkout, compra) y su costo.

Es la base para medir cómo le va al bot (KPIs en /reporte) y para mejorar el prompt
leyendo conversaciones reales. Se guarda solo lo que pasa por el chat: nunca datos de
formularios, tarjetas ni direcciones.
"""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

DB = Path(__file__).parent / "datos.db"
_lock = threading.Lock()

# Precio de lista por millón de tokens: (entrada, salida, lectura de caché). Escritura de caché = 1,25 × entrada.
PRECIOS = {
    "haiku-5-5": (0.10, 0.50, 0.01),  # mismo precio que usa CADENCE (prompts de hasta 100k tokens)
    "haiku": (1.0, 5.0, 0.10),
    "sonnet": (2.0, 10.0, 0.20),
    "opus-5-5": (4.0, 20.0, 0.20),
    "opus": (5.0, 25.0, 0.50),
    "fable": (10.0, 50.0, 0.25),
}


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def iniciar() -> None:
    with _lock, _con() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS conversaciones (
            sesion TEXT PRIMARY KEY,
            inicio TEXT NOT NULL,
            ultimo TEXT NOT NULL,
            modelo TEXT,
            pagina_inicio TEXT,
            logueado INTEGER,
            mensajes INTEGER DEFAULT 0,
            costo_usd REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion TEXT NOT NULL,
            ts TEXT NOT NULL,
            rol TEXT NOT NULL,            -- 'cliente' | 'bot'
            texto TEXT,
            herramientas TEXT,            -- JSON: [{nombre, args, error}]
            pagina TEXT,
            paso TEXT,
            carrito_total REAL,
            llamadas INTEGER DEFAULT 0,
            tokens_in INTEGER DEFAULT 0,
            tokens_out INTEGER DEFAULT 0,
            costo_usd REAL DEFAULT 0,
            error TEXT
        );
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion TEXT NOT NULL,
            ts TEXT NOT NULL,
            tipo TEXT NOT NULL,           -- chat_abierto | tarjeta_click | agregar_carrito | actualizar_carrito | checkout | compra | feedback | error
            datos TEXT                    -- JSON
        );
        CREATE TABLE IF NOT EXISTS busquedas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion TEXT,
            ts TEXT NOT NULL,
            accion TEXT NOT NULL,         -- busqueda | click | agregar | modi | ver_todos
            consulta TEXT,
            corregida TEXT,
            via TEXT,                     -- indice | parcial | ia | ofertas
            total INTEGER,
            producto TEXT,
            posicion INTEGER
        );
        CREATE INDEX IF NOT EXISTS ix_msg_sesion ON mensajes(sesion);
        CREATE INDEX IF NOT EXISTS ix_ev_sesion ON eventos(sesion);
        CREATE UNIQUE INDEX IF NOT EXISTS ix_compra_unica ON eventos(tipo, json_extract(datos, '$.pedido')) WHERE tipo = 'compra';
        """)


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def costo_llamada(modelo: str, usage) -> float:
    clave = next((k for k in ("opus-5-5", "haiku-5-5", "haiku", "sonnet", "opus", "fable") if k in (modelo or "")), "sonnet")
    e, s, c = PRECIOS[clave]
    return ((usage.input_tokens or 0) * e + (usage.cache_creation_input_tokens or 0) * e * 1.25
            + (usage.cache_read_input_tokens or 0) * c + (usage.output_tokens or 0) * s) / 1e6


def asegurar_conversacion(sesion: str, modelo: str, ctx: dict | None) -> None:
    ctx = ctx or {}
    with _lock, _con() as con:
        con.execute(
            "INSERT INTO conversaciones (sesion, inicio, ultimo, modelo, pagina_inicio, logueado) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(sesion) DO UPDATE SET ultimo = excluded.ultimo",
            (sesion, _ahora(), _ahora(), modelo, str(ctx.get("pagina") or "")[:200], 1 if ctx.get("logueado") else 0),
        )


def mensaje_cliente(sesion: str, texto: str, ctx: dict | None) -> None:
    ctx = ctx or {}
    with _lock, _con() as con:
        con.execute(
            "INSERT INTO mensajes (sesion, ts, rol, texto, pagina, paso, carrito_total) VALUES (?,?,?,?,?,?,?)",
            (sesion, _ahora(), "cliente", texto[:4000], str(ctx.get("pagina") or "")[:200], str(ctx.get("paso") or "")[:40],
             float(ctx.get("total") or 0) if str(ctx.get("total") or "").replace(".", "", 1).isdigit() else None),
        )
        con.execute("UPDATE conversaciones SET mensajes = mensajes + 1, ultimo = ? WHERE sesion = ?", (_ahora(), sesion))


def mensaje_bot(sesion: str, texto: str, herramientas: list, llamadas: int, tokens_in: int, tokens_out: int,
                costo: float, error: str | None = None) -> None:
    with _lock, _con() as con:
        con.execute(
            "INSERT INTO mensajes (sesion, ts, rol, texto, herramientas, llamadas, tokens_in, tokens_out, costo_usd, error) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (sesion, _ahora(), "bot", (texto or "")[:8000], json.dumps(herramientas, ensure_ascii=False), llamadas,
             tokens_in, tokens_out, costo, error),
        )
        con.execute("UPDATE conversaciones SET costo_usd = costo_usd + ?, ultimo = ? WHERE sesion = ?", (costo, _ahora(), sesion))


def evento(sesion: str, tipo: str, datos: dict | None = None) -> bool:
    """Devuelve False si el evento ya existía (ej. la misma compra registrada dos veces)."""
    with _lock, _con() as con:
        con.execute("INSERT OR IGNORE INTO conversaciones (sesion, inicio, ultimo) VALUES (?,?,?)", (sesion, _ahora(), _ahora()))
        try:
            con.execute("INSERT INTO eventos (sesion, ts, tipo, datos) VALUES (?,?,?,?)",
                        (sesion, _ahora(), tipo[:40], json.dumps(datos or {}, ensure_ascii=False)[:4000]))
        except sqlite3.IntegrityError:
            return False
    return True


def busqueda(sesion: str, accion: str, d: dict) -> None:
    """Lo que pasa en el buscador: qué se busca, qué da cero, dónde hacen clic. No toca las métricas del chat."""
    with _lock, _con() as con:
        con.execute("INSERT INTO busquedas (sesion, ts, accion, consulta, corregida, via, total, producto, posicion) VALUES (?,?,?,?,?,?,?,?,?)",
                    (sesion[:64], _ahora(), accion[:20], str(d.get("consulta") or "")[:120], (d.get("corregida") or None),
                     str(d.get("via") or "")[:20] or None, d.get("total") if isinstance(d.get("total"), int) else None,
                     str(d.get("producto") or "")[:200] or None, d.get("posicion") if isinstance(d.get("posicion"), int) else None))


def resumen_busquedas(dias: int = 30) -> dict:
    with _lock, _con() as con:
        desde = f"-{int(dias)} days"
        q = lambda sql: [dict(r) for r in con.execute(sql, (desde,)).fetchall()]
        return {
            "top": q("""SELECT lower(consulta) AS consulta, count(*) AS veces, max(total) AS resultados FROM busquedas
                       WHERE accion='busqueda' AND ts >= datetime('now', ?) GROUP BY 1 ORDER BY 2 DESC LIMIT 50"""),
            "sin_resultados": q("""SELECT lower(consulta) AS consulta, count(*) AS veces FROM busquedas
                       WHERE accion='busqueda' AND total=0 AND ts >= datetime('now', ?) GROUP BY 1 ORDER BY 2 DESC LIMIT 50"""),
            "acciones": q("""SELECT accion, count(*) AS veces FROM busquedas WHERE ts >= datetime('now', ?) GROUP BY 1"""),
        }


def resumen(dias: int = 30) -> dict:
    """KPIs del período: embudo (abrió el chat → escribió → agregó → checkout → compró), calidad y costo."""
    desde = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    desde = desde.fromordinal(desde.toordinal() - dias + 1).isoformat()
    with _lock, _con() as con:
        q = lambda sql, *a: con.execute(sql, a).fetchone()[0]  # noqa: E731
        conv = q("SELECT COUNT(*) FROM conversaciones WHERE mensajes > 0 AND inicio >= ?", desde)
        abiertos = q("SELECT COUNT(DISTINCT sesion) FROM eventos WHERE tipo='chat_abierto' AND ts >= ?", desde)
        con_evento = lambda t: q("SELECT COUNT(DISTINCT e.sesion) FROM eventos e JOIN conversaciones c USING(sesion) "  # noqa: E731
                                 "WHERE e.tipo=? AND c.mensajes > 0 AND c.inicio >= ?", t, desde)
        agregaron = con_evento("agregar_carrito")
        checkout = con_evento("checkout")
        compraron = con_evento("compra")
        ventas = q("SELECT COALESCE(SUM(json_extract(datos,'$.total')),0) FROM eventos WHERE tipo='compra' AND ts >= ?", desde)
        msgs = q("SELECT COUNT(*) FROM mensajes WHERE rol='cliente' AND ts >= ?", desde)
        costo = q("SELECT COALESCE(SUM(costo_usd),0) FROM mensajes WHERE ts >= ?", desde)
        errores = q("SELECT COUNT(*) FROM mensajes WHERE error IS NOT NULL AND ts >= ?", desde)
        up = q("SELECT COUNT(*) FROM eventos WHERE tipo='feedback' AND json_extract(datos,'$.valor')='up' AND ts >= ?", desde)
        down = q("SELECT COUNT(*) FROM eventos WHERE tipo='feedback' AND json_extract(datos,'$.valor')='down' AND ts >= ?", desde)
        derivaciones = q("SELECT COUNT(*) FROM mensajes WHERE rol='bot' AND texto LIKE '%wa.me%' AND ts >= ?", desde)
        herramientas = con.execute(
            "SELECT h.value ->> 'nombre' AS nombre, COUNT(*) AS n FROM mensajes m, json_each(m.herramientas) h "
            "WHERE m.rol='bot' AND m.ts >= ? GROUP BY nombre ORDER BY n DESC", (desde,)).fetchall()
        ultimas = con.execute(
            "SELECT sesion, inicio, mensajes, costo_usd, pagina_inicio FROM conversaciones WHERE mensajes > 0 "
            "ORDER BY ultimo DESC LIMIT 20").fetchall()
    pct = lambda a, b: round(100 * a / b, 1) if b else 0.0  # noqa: E731
    return {
        "dias": dias,
        "embudo": {
            "abrieron_chat": abiertos, "conversaciones": conv,
            "agregaron_carrito": agregaron, "pct_agregaron": pct(agregaron, conv),
            "llegaron_checkout": checkout, "pct_checkout": pct(checkout, conv),
            "compraron": compraron, "pct_compraron": pct(compraron, conv),
            "ventas_ars": ventas,
        },
        "calidad": {
            "mensajes_cliente": msgs, "mensajes_por_conversacion": round(msgs / conv, 1) if conv else 0,
            "feedback_positivo": up, "feedback_negativo": down, "errores": errores, "derivaciones_whatsapp": derivaciones,
            "herramientas": [dict(r) for r in herramientas],
        },
        "costo": {"total_usd": round(costo, 4), "por_conversacion_usd": round(costo / conv, 4) if conv else 0,
                  "por_venta_usd": round(costo / compraron, 4) if compraron else None},
        "ultimas": [dict(r) for r in ultimas],
    }


def transcripcion(sesion: str) -> dict:
    with _lock, _con() as con:
        c = con.execute("SELECT * FROM conversaciones WHERE sesion = ?", (sesion,)).fetchone()
        m = con.execute("SELECT ts, rol, texto, herramientas, pagina, paso, costo_usd, error FROM mensajes WHERE sesion = ? ORDER BY id", (sesion,)).fetchall()
        e = con.execute("SELECT ts, tipo, datos FROM eventos WHERE sesion = ? ORDER BY id", (sesion,)).fetchall()
    return {"conversacion": dict(c) if c else None, "mensajes": [dict(r) for r in m], "eventos": [dict(r) for r in e]}
