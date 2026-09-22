# Modi: bot vendedor de Ecomodico

Chat vendedor y de preguntas frecuentes para ecomodico.com. Busca en el catálogo real (precio, descuento y stock en vivo), muestra tarjetas de producto y vende con el método de `metodo_venta.md` (Value Equation y money models de Hormozi, con escasez solo si es real).

## Arrancar

1. `pip install -r requirements.txt`
2. Copiá `.env.example` como `.env` y pegá tu `ANTHROPIC_API_KEY`
3. Doble clic en `iniciar.bat` (o `python server.py`) y abrí http://localhost:8787

`http://localhost:8787/#chat` abre el chat directo.

## Archivos

| Archivo | Qué es |
|---|---|
| `server.py` | API (FastAPI) + loop del agente con Claude y herramientas |
| `catalogo.py` | Lee productos de ecomodico.com (el `__SERVER_DATA__` que trae cada página), con caché de 5 min |
| `conocimiento.md` | FAQ, envíos, pagos, devoluciones. **Editalo para cambiar lo que sabe** |
| `metodo_venta.md` | Cómo vende. **Editalo para cambiar el estilo de venta** |
| `static/widget.js` | Widget embebible (Shadow DOM, no rompe el CSS de la tienda) |
| `static/index.html` | Página demo que simula la tienda |

Si cambiás los `.md`, reiniciá el servidor.

## Meterlo en la web real

```html
<script src="https://TU-SERVIDOR/widget.js" defer></script>
```

Para eso el servidor tiene que estar publicado (Render, Railway, un VPS). Antes de producción conviene: guardar sesiones en Redis o una base (hoy viven en memoria), limitar el CORS al dominio de ecomodico.com y agregar rate limiting por IP.

## Configuración (.env)

- `ECOMODICO_MODEL`: por defecto `claude-haiku-4-5` (el más barato). Para más calidad: `claude-sonnet-5` u `claude-opus-5`.
- `ECOMODICO_EFFORT`: `low` por defecto. Solo aplica a Sonnet/Opus (Haiku 4.5 no lo acepta).
- Con Sonnet/Opus se activa el fallback del servidor (`fallbacks: "default"`): si el modelo rechaza un pedido, la API lo reintenta con otro modelo.

## Costos (medidos el 2026-09-22, conversación de 5 mensajes)

| Modelo | Por conversación | Cada 1.000 conversaciones |
|---|---|---|
| Haiku 4.5 (default) | US$ 0,016 | US$ 16 |
| Sonnet 5 | US$ 0,049 | US$ 49 |
| Opus 5 | US$ 0,134 | US$ 134 |

El gasto real queda anotado en `uso.jsonl` (una línea por llamada a la API).
