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
  .av { width: 40px; height: 40px; border-radius: 50%; flex-shrink: 0; display: block; object-fit: cover; box-shadow: 0 0 0 2px #fff; }
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
  .card a { color: inherit; text-decoration: none; }
  .card .cta { display: block; width: 100%; margin-top: auto; text-align: center; background: var(--azul); color: #fff; font-size: 13px; font-weight: 600; padding: 8px; border: 0; border-radius: 30px; cursor: pointer; }
  .card .cta:disabled { opacity: .4; cursor: not-allowed; }
  .card .cta.sec { background: #fff; color: var(--azul); border: 2px solid var(--azul); }
  .card .info > a:last-child { margin-top: auto; }
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
    '<button class="burbuja" aria-label="Abrir chat de ayuda"><img class="av" alt="" src="' + API + '/modi.png">¿Te ayudo?</button>' +
    '<div class="panel" role="dialog" aria-label="Chat con Modi">' +
      '<div class="cab"><img class="av" alt="" src="' + API + '/modi.png"><div class="t"><b>Modi · Ecomodico</b><span>En línea</span></div>' +
      '<button class="cerrar" aria-label="Cerrar">✕</button></div>' +
      '<div class="msgs" aria-live="polite"></div>' +
      '<div class="pie"><textarea rows="1" placeholder="Escribí tu consulta…" aria-label="Mensaje"></textarea><button class="enviar">Enviar</button></div>' +
      '<div class="legal">Asistente automático · ¿Preferís una persona? <a href="' + WHATSAPP + '" target="_blank" rel="noopener">WhatsApp</a></div>' +
    "</div>";

  var $ = function (s) { return root.querySelector(s); };
  var burbuja = $(".burbuja"), panel = $(".panel"), msgs = $(".msgs"), input = $("textarea"), btn = $(".enviar");
  var ocupado = false, iniciado = false;

  function saludo() {
    burbujaBot("¡Hola! 👋 Soy Modi, de Ecomodico. Te ayudo a encontrar productos, ofertas o con dudas de envíos y pagos.");
    var ch = document.createElement("div"); ch.className = "chips";
    SUGERENCIAS.forEach(function (s) {
      var b = document.createElement("button"); b.className = "chip"; b.textContent = s;
      b.onclick = function () { ch.remove(); enviar(s); };
      ch.appendChild(b);
    });
    msgs.appendChild(ch);
  }

  // Si la página se recargó (ej. al pasar al checkout), reconstruimos la charla.
  async function cargarHistorial() {
    if (!sesion) return 0;
    try {
      var r = await fetch(API + "/api/historial?sesion=" + encodeURIComponent(sesion));
      var d = await r.json();
      (d.mensajes || []).forEach(function (m) {
        if (m.rol === "yo") { var y = document.createElement("div"); y.className = "m yo"; y.textContent = m.texto; msgs.appendChild(y); }
        else burbujaBot(m.texto);
      });
      return (d.mensajes || []).length;
    } catch (e) { return 0; }
  }

  async function abrir() {
    panel.classList.add("abierto"); burbuja.style.display = "none"; input.focus();
    store.set("ecomodico_chat_abierto", "1");
    if (!iniciado) {
      iniciado = true;
      if (!(await cargarHistorial())) saludo();
      avisarPaso(pasoActual(), true);
    }
  }
  function cerrar() { panel.classList.remove("abierto"); burbuja.style.display = ""; store.set("ecomodico_chat_abierto", ""); }
  burbuja.onclick = abrir;
  $(".cerrar").onclick = cerrar;

  function esc(s) { return s.replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  // Solo links reales: fichas /p/<nombre>/<id>, páginas conocidas de la tienda y WhatsApp.
  // Si el modelo inventa una URL, se muestra el texto sin link.
  var LINK_OK = /^https:\/\/(ecomodico\.com\/(p\/[^\/\s]+\/[0-9a-f-]{36}|faq|ofertas|shop|contacto-y-reclamos|arrepentimiento-de-compra|politicas-de-envio-y-devolucion|terminos-y-condiciones|mayoristas)\/?$|wa\.me\/\d+$|share\.google\/)/;
  function md(s) {
    return esc(s)
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, function (_, txt, url) {
        return LINK_OK.test(url) ? '<a href="' + url + '" target="_blank" rel="noopener">' + txt + "</a>" : "<strong>" + txt + "</strong>";
      })
      .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, function (_, pre, url) {
        return LINK_OK.test(url) ? pre + '<a href="' + url + '" target="_blank" rel="noopener">' + url + "</a>" : pre + url;
      })
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
  }
  function scroll() { msgs.scrollTop = msgs.scrollHeight; }
  function burbujaBot(texto) {
    var d = document.createElement("div"); d.className = "m bot"; d.innerHTML = md(texto); msgs.appendChild(d); scroll(); return d;
  }
  function pesos(n) { return "$" + Math.round(n).toLocaleString("es-AR"); }

  // La tienda (Drubbit, Vue 2) expone $shop.addToCart en su instancia raíz.
  // Solo existe cuando el widget corre dentro de ecomodico.com.
  function tiendaShop() {
    var els = [document.getElementById("app"), document.querySelector("[data-app]")].concat([].slice.call(document.body.children));
    for (var i = 0; i < els.length; i++) {
      var vm = els[i] && els[i].__vue__;
      if (vm) {
        var sh = vm.$shop || (vm.$root && (vm.$root.$shop || vm.$root.$options.shop));
        if (sh && typeof sh.addToCart === "function") return sh;
      }
    }
    return null;
  }

  async function agregarAlCarrito(items) {
    var shop = tiendaShop();
    if (!shop) {
      // Fuera de ecomodico.com (ej. localhost): abrimos la ficha para comprar desde ahí.
      var aviso = burbujaBot("🛒 Desde acá no puedo tocar tu carrito. Te abro " + (items.length > 1 ? "los productos" : "el producto") + " para que lo agregues:\n" +
        items.map(function (x) { return "[" + x.nombre + "](" + x.url + ")"; }).join("\n"));
      if (items.length === 1) window.open(items[0].url, "_blank", "noopener");
      return aviso;
    }
    var ok = [], mal = [];
    for (var i = 0; i < items.length; i++) {
      var x = items[i];
      try {
        await shop.addToCart({ productId: x.productId, variantId: x.variantId, qty: x.qty, sum: true,
          showUpsells: false, showCart: i === items.length - 1 });
        ok.push(x);
      } catch (e) { mal.push(x); }
    }
    if (ok.length) burbujaBot("✅ Agregué al carrito: " + ok.map(function (x) { return x.qty + " × " + x.nombre; }).join(", ") + ".");
    if (mal.length) { var e = burbujaBot("❌ No pude agregar: " + mal.map(function (x) { return "[" + x.nombre + "](" + x.url + ")"; }).join(", ")); e.className = "m error"; }
  }

  function tiendaVm() {
    var els = [document.getElementById("app")].concat([].slice.call(document.body.children));
    for (var i = 0; i < els.length; i++) if (els[i] && els[i].__vue__) return els[i].__vue__;
    return null;
  }
  function ordenActual() {
    try { var vm = tiendaVm(); return vm && vm.$store && vm.$store.get ? vm.$store.get("cart/order") : null; } catch (e) { return null; }
  }
  function pasoActual() {
    var m = location.pathname.match(/^\/checkout\/[^/]+\/([^/?#]+)/);
    return m ? m[1] : (location.pathname.indexOf("/checkout") === 0 ? "init" : "");
  }

  // Lo que el bot "ve" de la página: dónde está el cliente y qué tiene en el carrito.
  // Nunca se leen campos de formularios (datos personales, tarjeta, etc.).
  // Regla de envío gratis tal como la publica la tienda en cada página (colección + meta).
  function reglaEnvioGratis() {
    try {
      var c = (window.__SERVER_DATA__ || {}).orderTotalGoalProgressConfig || {};
      return { coleccion: String(c.collectionId || "57"), meta: Number(c.orderTotalGoal || 75000) };
    } catch (e) { return { coleccion: "57", meta: 75000 }; }
  }
  function contexto() {
    var ctx = { pagina: location.pathname, paso: pasoActual(), en_tienda: !!tiendaShop() };
    var mp = location.pathname.match(/^\/p\/[^/]+\/[0-9a-f-]{36}/);
    if (mp) ctx.producto_actual = location.origin + mp[0];
    var o = ordenActual(), regla = reglaEnvioGratis();
    if (o && o.items) {
      ctx.carrito = o.items.map(function (it) {
        var cd = it.cartData || {};
        var cols = (cd.collectionsIds || []).map(String);
        return { producto_id: cd.productId, nombre: it.name, cantidad: it.qty, precio: it.finalPrice, total: it.finalTotal,
                 envio_gratis: cols.indexOf(regla.coleccion) !== -1,
                 url: cd.urlName && cd.productId ? location.origin + "/p/" + cd.urlName + "/" + cd.productId : null };
      });
      ctx.total = o.total;
      ctx.envio_gratis_meta = regla.meta;
    }
    return ctx;
  }

  async function actualizarCarrito(cambios) {
    var shop = tiendaShop(), o = ordenActual();
    if (!shop || !o) { var e = burbujaBot("Desde acá no puedo modificar tu carrito; hacelo desde el carrito de ecomodico.com."); e.className = "m error"; return; }
    var hechos = [], mal = [];
    for (var i = 0; i < cambios.length; i++) {
      var c = cambios[i];
      var it = (o.items || []).filter(function (x) { return x.cartData && x.cartData.productId === c.productId; })[0];
      if (!it) { mal.push(c); continue; }
      try {
        if (c.qty === 0) await shop.deleteCartItem({ cartItemId: it.cartItemId });
        else await shop.updateCartItem({ cartItemId: it.cartItemId, qty: c.qty });
        hechos.push(c.qty === 0 ? "quité " + it.name : it.name + " → " + c.qty);
      } catch (err) { mal.push(c); }
    }
    if (hechos.length) burbujaBot("✅ Listo: " + hechos.join(", ") + ".");
    if (mal.length) { var e2 = burbujaBot("❌ No pude cambiar: " + mal.map(function (x) { return x.nombre; }).join(", ")); e2.className = "m error"; }
  }

  function irAPagar() {
    var shop = tiendaShop();
    if (!shop || typeof shop.goCheckout !== "function") {
      var e = burbujaBot("Desde acá no puedo abrir el checkout. Entrá a tu carrito en ecomodico.com y tocá \"Finalizar compra\"."); e.className = "m error"; return;
    }
    burbujaBot("💳 Te llevo a finalizar la compra. Sigo acá por si tenés dudas en cada paso.");
    store.set("ecomodico_chat_abierto", "1");
    shop.goCheckout(true); // navegación interna de la tienda: el chat no se cierra
  }

  // Ayuda fija por paso del checkout (no gasta API). El bot también recibe el paso en cada mensaje.
  var AYUDA_PASO = {
    signin: "ℹ️ Podés **seguir como invitado**, no hace falta crear cuenta.",
    contact: "ℹ️ Completá nombre, email y teléfono. Al email te llega el seguimiento del envío.",
    delivery: "🚚 Elegí **envío a domicilio** o **retiro gratis** en Av. del Campo 1500, Villa Urquiza (L a V 9-18, sáb 9-13).",
    payment: "💳 Pagás con **Mercado Pago** (tarjetas, débito o dinero en cuenta). Si tenés cupón, cargalo en el resumen. Nunca te voy a pedir datos de tarjeta por acá.",
  };
  var ultimoPaso = null;
  function avisarPaso(paso, forzar) {
    if (paso === ultimoPaso && !forzar) return;
    ultimoPaso = paso;
    burbuja.lastChild.nodeValue = paso ? "¿Dudas con la compra?" : "¿Te ayudo?";
    if (paso && AYUDA_PASO[paso] && panel.classList.contains("abierto")) burbujaBot(AYUDA_PASO[paso]);
  }
  setInterval(function () { avisarPaso(pasoActual(), false); }, 1000);

  function tarjetas(items) {
    var c = document.createElement("div"); c.className = "cards";
    items.forEach(function (p) {
      var d = document.createElement("div"); d.className = "card";
      var st = !p.disponible ? '<span class="stock no">Sin stock</span>'
        : p.stock != null && p.stock > 0 && p.stock <= 5 ? '<span class="stock poco">⚠️ Últimas ' + p.stock + (p.stock === 1 ? " unidad" : " unidades") + "</span>"
        : '<span class="stock">✅ En stock</span>';
      var link = '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">';
      d.innerHTML =
        (p.descuento_pct ? '<span class="badge">−' + p.descuento_pct + "%</span>" : "") +
        link + '<div class="img">' + (p.imagen ? '<img loading="lazy" alt="" src="' + esc(p.imagen) + '">' : "🛒") + "</div></a>" +
        '<div class="info">' + (p.marca ? '<span class="marca">' + esc(p.marca) + "</span>" : "") +
        link + '<span class="nom">' + esc(p.nombre) + "</span></a>" +
        (p.precio_anterior ? '<span class="prev">' + pesos(p.precio_anterior) + "</span>" : "") +
        '<span class="precio">' + pesos(p.precio) + "</span>" + st +
        (p.disponible ? '<button class="cta">🛒 Agregar</button>' : link + '<span class="cta sec">Ver producto</span></a>') + "</div>";
      var b = d.querySelector("button.cta");
      if (b) b.onclick = async function () {
        b.disabled = true; b.textContent = "Agregando…";
        await agregarAlCarrito([{ productId: p.id, variantId: p.variante_id, qty: 1, nombre: p.nombre, url: p.url }]);
        b.disabled = false; b.textContent = "🛒 Agregar otro";
      };
      c.appendChild(d);
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
    var actual = null, buffer = "", pendienteCheckout = false;

    function texto_(t) {
      if (indicador) { indicador.remove(); indicador = null; }
      if (!actual) { buffer = ""; actual = burbujaBot(""); }
      buffer += t; actual.innerHTML = md(buffer); scroll();
    }

    try {
      var r = await fetch(API + "/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje: texto, sesion: sesion, contexto: contexto() }),
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
          else if (ev.type === "carrito") { if (indicador) { indicador.remove(); indicador = null; } agregarAlCarrito(ev.items); actual = null; }
          else if (ev.type === "carrito_actualizar") { if (indicador) { indicador.remove(); indicador = null; } actualizarCarrito(ev.items); actual = null; }
          else if (ev.type === "checkout") { if (indicador) { indicador.remove(); indicador = null; } pendienteCheckout = true; actual = null; }
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
      if (pendienteCheckout) setTimeout(irAPagar, 800); // primero que lea la respuesta
    }
  }

  // Reabrir el chat si estaba abierto antes de recargar la página (ej. al pasar al checkout).
  if (location.hash === "#chat" || store.get("ecomodico_chat_abierto") === "1") abrir();

  btn.onclick = function () { enviar(input.value); };
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(input.value); }
  });
  input.addEventListener("input", function () { input.style.height = ""; input.style.height = Math.min(input.scrollHeight, 100) + "px"; });
})();
