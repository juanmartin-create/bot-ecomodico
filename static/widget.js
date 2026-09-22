/* Widget de chat de Ecomodico (Modi).
 * Uso: <script src="http://localhost:8787/widget.js" defer></script>
 * Opcional: data-api="https://tu-servidor" si la API vive en otro origen.
 * Todo vive dentro de un Shadow DOM para no chocar con el CSS de la tienda.
 */
(function () {
  if (window.__ecomodicoChat) return;
  window.__ecomodicoChat = true;

  var script = document.currentScript;
  var API = (script && script.dataset.api) || (script ? new URL(script.src).origin : "");
  var WHATSAPP = "https://wa.me/5491161848244";
  var SUGERENCIAS = ["¿Qué ofertas hay hoy?", "¿Cuánto sale el envío?", "Busco pañales", "¿Dónde puedo retirar?"];

  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  };
  var sesion = store.get("ecomodico_chat_sesion");

  var css = `
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap');
  :host { all: initial; }
  * { box-sizing: border-box; font-family: 'Outfit', system-ui, sans-serif; }
  :host {
    --azul: #2274A5; --azul-osc: #1a5e8a; --azul-claro: #EBF4FB; --naranja: #D65A31; --ambar: #FDB916;
    --verde: #18B81D; --texto: #222; --texto-2: #666; --borde: #E0E0E0; --fondo: #FAFAFA; --blanco: #fff;
  }
  .burbuja {
    position: fixed; right: 20px; bottom: 20px; z-index: 2147483000;
    height: 56px; padding: 0 20px 0 8px; border-radius: 30px; border: 0; cursor: pointer;
    background: var(--azul); color: #fff; display: flex; align-items: center; gap: 10px;
    font-size: 15px; font-weight: 600; box-shadow: 0 2px 8px rgba(34,116,165,.25);
    transition: transform .15s, box-shadow .15s, background .15s;
  }
  .burbuja:hover { transform: translateY(-1px); background: var(--azul-osc); box-shadow: 0 6px 20px rgba(34,116,165,.3); }
  .av { width: 40px; height: 40px; border-radius: 50%; background: #fff; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
  .panel {
    position: fixed; right: 20px; bottom: 20px; z-index: 2147483001;
    width: 380px; height: min(640px, calc(100vh - 40px)); background: var(--fondo);
    border-radius: 16px; box-shadow: 0 12px 40px rgba(0,0,0,.25); display: none; flex-direction: column; overflow: hidden;
  }
  .panel.abierto { display: flex; }
  @media (max-width: 600px) {
    .panel { inset: 0; width: auto; height: auto; border-radius: 0; }
  }
  .cab { background: var(--azul); color: #fff; padding: 12px 16px; display: flex; align-items: center; gap: 12px; }
  .cab .t { flex: 1; line-height: 1.3; }
  .cab .t b { font-size: 16px; font-weight: 600; display: block; }
  .cab .t span { font-size: 12px; opacity: .85; }
  .cab .t span::before { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #7CFC7C; margin-right: 6px; }
  .cab button { background: none; border: 0; color: #fff; font-size: 20px; cursor: pointer; width: 36px; height: 36px; border-radius: 50%; }
  .cab button:hover { background: rgba(255,255,255,.15); }
  .msgs { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
  .m { max-width: 85%; padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.5; color: var(--texto); word-wrap: break-word; }
  .m.bot { background: var(--blanco); border: 1px solid var(--borde); align-self: flex-start; border-bottom-left-radius: 4px; }
  .m.yo { background: var(--azul); color: #fff; align-self: flex-end; border-bottom-right-radius: 4px; }
  .m a { color: var(--azul); font-weight: 500; }
  .m.yo a { color: #fff; }
  .m.error { background: #FFF0F0; border: 1px solid #F5C2C2; color: #A00; align-self: stretch; max-width: 100%; }
  .estado { align-self: flex-start; font-size: 12px; color: var(--texto-2); padding: 0 4px; }
  .puntos { display: inline-flex; gap: 4px; }
  .puntos i { width: 6px; height: 6px; border-radius: 50%; background: #9BBBD1; animation: p 1s infinite; }
  .puntos i:nth-child(2) { animation-delay: .15s; } .puntos i:nth-child(3) { animation-delay: .3s; }
  @keyframes p { 0%,60%,100% { opacity: .3; } 30% { opacity: 1; } }
  .cards { display: flex; gap: 10px; overflow-x: auto; padding: 2px 2px 8px; align-self: stretch; scroll-snap-type: x mandatory; }
  .card {
    flex: 0 0 160px; background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.08);
    display: flex; flex-direction: column; overflow: hidden; scroll-snap-align: start; text-decoration: none; color: inherit;
    transition: transform .15s, box-shadow .15s; position: relative;
  }
  .card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(34,116,165,.15); }
  .card .img { background: var(--fondo); height: 120px; display: flex; align-items: center; justify-content: center; padding: 8px; }
  .card .img img { max-width: 100%; max-height: 100%; object-fit: contain; }
  .card .badge { position: absolute; top: 8px; left: 8px; background: var(--naranja); color: #fff; font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; letter-spacing: .04em; }
  .card .info { padding: 10px; display: flex; flex-direction: column; gap: 4px; flex: 1; }
  .card .marca { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--texto-2); }
  .card .nom { font-size: 13px; font-weight: 500; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .card .prev { font-size: 12px; color: #999; text-decoration: line-through; }
  .card .precio { font-size: 18px; font-weight: 700; color: var(--azul); }
  .card .stock { font-size: 11px; color: var(--verde); }
  .card .stock.poco { color: var(--naranja); }
  .card .stock.no { color: #999; }
  .card .cta { margin-top: auto; text-align: center; background: var(--azul); color: #fff; font-size: 13px; font-weight: 600; padding: 8px; border-radius: 30px; }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip { background: #fff; border: 2px solid var(--azul); color: var(--azul); font-size: 13px; font-weight: 500; padding: 6px 12px; border-radius: 30px; cursor: pointer; transition: background .15s; }
  .chip:hover { background: var(--azul-claro); }
  .pie { border-top: 1px solid var(--borde); background: #fff; padding: 10px 12px; display: flex; gap: 8px; align-items: flex-end; }
  .pie textarea {
    flex: 1; resize: none; border: 1px solid var(--borde); border-radius: 8px; padding: 10px 12px; font-size: 14px;
    max-height: 100px; outline: none; color: var(--texto); line-height: 1.4;
  }
  .pie textarea:focus { border-color: var(--azul); box-shadow: 0 0 0 3px rgba(34,116,165,.15); }
  .pie button { height: 42px; padding: 0 16px; border: 0; border-radius: 30px; background: var(--azul); color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; }
  .pie button:disabled { opacity: .4; cursor: not-allowed; }
  .legal { font-size: 11px; color: #999; text-align: center; padding: 0 12px 8px; background: #fff; }
  .legal a { color: var(--texto-2); }
  `;

  var host = document.createElement("div");
  host.id = "ecomodico-chat";
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });
  root.innerHTML =
    "<style>" + css + "</style>" +
    '<button class="burbuja" aria-label="Abrir chat de ayuda"><span class="av" aria-hidden="true">🛒</span>¿Te ayudo?</button>' +
    '<div class="panel" role="dialog" aria-label="Chat con Modi">' +
      '<div class="cab"><span class="av" aria-hidden="true">🛒</span><div class="t"><b>Modi · Ecomodico</b><span>En línea</span></div>' +
      '<button class="cerrar" aria-label="Cerrar">✕</button></div>' +
      '<div class="msgs" aria-live="polite"></div>' +
      '<div class="pie"><textarea rows="1" placeholder="Escribí tu consulta…" aria-label="Mensaje"></textarea><button class="enviar">Enviar</button></div>' +
      '<div class="legal">Asistente automático · ¿Preferís una persona? <a href="' + WHATSAPP + '" target="_blank" rel="noopener">WhatsApp</a></div>' +
    "</div>";

  var $ = function (s) { return root.querySelector(s); };
  var burbuja = $(".burbuja"), panel = $(".panel"), msgs = $(".msgs"), input = $("textarea"), btn = $(".enviar");
  var ocupado = false, iniciado = false;

  function abrir() {
    panel.classList.add("abierto"); burbuja.style.display = "none"; input.focus();
    if (!iniciado) {
      iniciado = true;
      burbujaBot("¡Hola! 👋 Soy Modi, de Ecomodico. Te ayudo a encontrar productos, ofertas o con dudas de envíos y pagos.");
      var ch = document.createElement("div"); ch.className = "chips";
      SUGERENCIAS.forEach(function (s) {
        var b = document.createElement("button"); b.className = "chip"; b.textContent = s;
        b.onclick = function () { ch.remove(); enviar(s); };
        ch.appendChild(b);
      });
      msgs.appendChild(ch);
    }
  }
  function cerrar() { panel.classList.remove("abierto"); burbuja.style.display = ""; }
  burbuja.onclick = abrir;
  if (location.hash === "#chat") abrir();
  $(".cerrar").onclick = cerrar;

  function esc(s) { return s.replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function md(s) {
    return esc(s)
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
  }
  function scroll() { msgs.scrollTop = msgs.scrollHeight; }
  function burbujaBot(texto) {
    var d = document.createElement("div"); d.className = "m bot"; d.innerHTML = md(texto); msgs.appendChild(d); scroll(); return d;
  }
  function pesos(n) { return "$" + Math.round(n).toLocaleString("es-AR"); }

  function tarjetas(items) {
    var c = document.createElement("div"); c.className = "cards";
    items.forEach(function (p) {
      var a = document.createElement("a"); a.className = "card"; a.href = p.url; a.target = "_blank"; a.rel = "noopener";
      var st = !p.disponible ? '<span class="stock no">Sin stock</span>'
        : p.stock != null && p.stock <= 5 ? '<span class="stock poco">⚠️ Últimas ' + p.stock + " unidades</span>"
        : '<span class="stock">✅ En stock</span>';
      a.innerHTML =
        (p.descuento_pct ? '<span class="badge">−' + p.descuento_pct + "%</span>" : "") +
        '<div class="img">' + (p.imagen ? '<img loading="lazy" alt="" src="' + esc(p.imagen) + '">' : "🛒") + "</div>" +
        '<div class="info">' + (p.marca ? '<span class="marca">' + esc(p.marca) + "</span>" : "") +
        '<span class="nom">' + esc(p.nombre) + "</span>" +
        (p.precio_anterior ? '<span class="prev">' + pesos(p.precio_anterior) + "</span>" : "") +
        '<span class="precio">' + pesos(p.precio) + "</span>" + st +
        '<span class="cta">🛒 Comprar</span></div>';
      c.appendChild(a);
    });
    msgs.appendChild(c); scroll();
  }

  function cargando() {
    var d = document.createElement("div"); d.className = "estado"; d.innerHTML = '<span class="puntos"><i></i><i></i><i></i></span>';
    msgs.appendChild(d); scroll(); return d;
  }

  async function enviar(texto) {
    texto = (texto || "").trim();
    if (!texto || ocupado) return;
    ocupado = true; btn.disabled = true;
    var chips = root.querySelector(".chips"); if (chips) chips.remove();
    var yo = document.createElement("div"); yo.className = "m yo"; yo.textContent = texto; msgs.appendChild(yo);
    input.value = ""; input.style.height = "";
    var indicador = cargando();
    var actual = null, buffer = "";

    function texto_(t) {
      if (indicador) { indicador.remove(); indicador = null; }
      if (!actual) { buffer = ""; actual = burbujaBot(""); }
      buffer += t; actual.innerHTML = md(buffer); scroll();
    }

    try {
      var r = await fetch(API + "/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje: texto, sesion: sesion }),
      });
      if (!r.ok || !r.body) throw new Error("HTTP " + r.status);
      var reader = r.body.getReader(), dec = new TextDecoder(), resto = "";
      while (true) {
        var chunk = await reader.read();
        if (chunk.done) break;
        resto += dec.decode(chunk.value, { stream: true });
        var partes = resto.split("\n\n"); resto = partes.pop();
        partes.forEach(function (linea) {
          if (linea.indexOf("data: ") !== 0) return;
          var ev = JSON.parse(linea.slice(6));
          if (ev.type === "sesion") { sesion = ev.id; store.set("ecomodico_chat_sesion", ev.id); }
          else if (ev.type === "text") texto_(ev.text);
          else if (ev.type === "productos") { if (indicador) { indicador.remove(); indicador = null; } tarjetas(ev.items); actual = null; }
          else if (ev.type === "separador") { actual = null; if (!indicador) indicador = cargando(); }
          else if (ev.type === "error") { var e = burbujaBot(ev.text); e.className = "m error"; }
        });
      }
    } catch (err) {
      var e = burbujaBot("❌ No me pude conectar con el servidor. Probá de nuevo o escribinos por WhatsApp: " + WHATSAPP);
      e.className = "m error";
    } finally {
      if (indicador) indicador.remove();
      ocupado = false; btn.disabled = false; input.focus();
    }
  }

  btn.onclick = function () { enviar(input.value); };
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(input.value); }
  });
  input.addEventListener("input", function () { input.style.height = ""; input.style.height = Math.min(input.scrollHeight, 100) + "px"; });
})();
