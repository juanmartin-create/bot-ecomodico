/* Buscador de Ecomodico: reemplaza el desplegable de la barra de búsqueda de la tienda
 * por resultados del índice propio (tolera errores de tipeo, sinónimos, palabras pegadas
 * y frases como "algo para el desayuno").
 * Uso: <script src="http://localhost:8787/buscador.js" defer></script>
 * Opcional: data-api="https://tu-servidor" si la API vive en otro origen.
 * El panel vive en un Shadow DOM para no chocar con el CSS de la tienda.
 */
(function () {
  if (window.__ecomodicoBuscador) return;
  window.__ecomodicoBuscador = true;

  var script = document.currentScript;
  var API = (script && script.dataset.api) || (script ? new URL(script.src).origin : "");
  var SEL = "form.ac-search-field input[name=search], input[name=search][type=search], input[data-buscador-ecomodico]";

  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  };
  var sesion = store.get("ecomodico_buscador_sesion");
  if (!sesion) {
    sesion = (window.crypto && crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()).replace(/[^a-z0-9]/gi, "");
    store.set("ecomodico_buscador_sesion", sesion);
  }
  function registrar(accion, datos) {
    try {
      fetch(API + "/api/buscar/evento", { method: "POST", headers: { "Content-Type": "application/json" }, keepalive: true,
        body: JSON.stringify({ sesion: sesion, accion: accion, datos: datos || {} }) }).catch(function () {});
    } catch (e) {}
  }

  // Escondemos el desplegable original de Drubbit; la barra de búsqueda sigue siendo la suya.
  var global = document.createElement("style");
  global.textContent = "form.ac-search-field .quick-search{display:none!important}";
  document.head.appendChild(global);

  var css = `
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap');
  :host { all: initial; }
  * { box-sizing: border-box; font-family: 'Outfit', system-ui, sans-serif; }
  :host {
    --azul: #2274A5; --azul-osc: #1a5e8a; --azul-claro: #EBF4FB; --naranja: #D65A31; --ambar: #FDB916;
    --verde: #18B81D; --texto: #222; --texto-2: #666; --borde: #E0E0E0; --fondo: #FAFAFA; --blanco: #fff;
  }
  .panel {
    position: fixed; z-index: 2147482000; display: none; flex-direction: column;
    background: var(--blanco); border-radius: 12px; overflow: hidden;
    box-shadow: 0 12px 40px rgba(0,0,0,.18), 0 0 0 1px rgba(0,0,0,.04);
    max-height: min(680px, calc(100vh - 120px)); color: var(--texto);
  }
  .panel.abierto { display: flex; }
  .cab { padding: 12px 16px 8px; font-size: 13px; color: var(--texto-2); line-height: 1.4; }
  .cab b { color: var(--texto); font-weight: 600; }
  .cab .corr { color: var(--azul); }
  .chips { display: flex; gap: 6px; padding: 0 16px 10px; overflow-x: auto; scrollbar-width: none; }
  .chips::-webkit-scrollbar { display: none; }
  .chip {
    flex-shrink: 0; border: 1px solid var(--borde); background: var(--blanco); color: var(--texto);
    border-radius: 20px; padding: 5px 12px; font-size: 13px; cursor: pointer; white-space: nowrap; transition: all .15s;
  }
  .chip:hover { border-color: var(--azul); color: var(--azul); }
  .chip.on { background: var(--azul); border-color: var(--azul); color: #fff; }
  .chip small { opacity: .7; margin-left: 2px; }
  .lista { overflow-y: auto; flex: 1; border-top: 1px solid #F0F0F0; }
  .fila {
    display: grid; grid-template-columns: 56px 1fr auto; gap: 12px; align-items: center;
    padding: 10px 16px; cursor: pointer; text-decoration: none; color: inherit; border-bottom: 1px solid #F5F5F5;
  }
  .fila:hover, .fila.sel { background: var(--azul-claro); }
  .fila img { width: 56px; height: 56px; object-fit: contain; border-radius: 8px; background: #fff; }
  .nom { font-size: 14px; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .nom mark { background: none; color: inherit; font-weight: 700; }
  .precio { margin-top: 4px; display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; }
  .precio .ya { font-size: 16px; font-weight: 700; color: var(--azul); }
  .precio s { font-size: 12px; color: #999; }
  .off { font-size: 11px; font-weight: 700; color: #fff; background: var(--naranja); border-radius: 4px; padding: 1px 5px; }
  .gratis { font-size: 11px; font-weight: 600; color: var(--verde); }
  .agotado { font-size: 12px; color: #999; }
  .add {
    border: 0; background: var(--azul); color: #fff; font-weight: 600; font-size: 13px;
    border-radius: 20px; padding: 8px 14px; cursor: pointer; white-space: nowrap; transition: background .15s, transform .1s;
  }
  .add:hover { background: var(--azul-osc); }
  .add:active { transform: scale(.96); }
  .add.ok { background: var(--verde); }
  .add[disabled] { background: #ccc; cursor: default; }
  .vacio { padding: 20px 16px; font-size: 14px; color: var(--texto-2); }
  .ia { padding: 10px 16px; font-size: 13px; color: var(--texto-2); display: flex; align-items: center; gap: 8px; border-top: 1px solid #F0F0F0; }
  .ia .punto { width: 8px; height: 8px; border-radius: 50%; background: var(--ambar); animation: lat 1s infinite ease-in-out; }
  @keyframes lat { 50% { opacity: .3; transform: scale(.7); } }
  .pie { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 16px; border-top: 1px solid #F0F0F0; background: var(--fondo); }
  .pie a, .pie button { font-size: 13px; font-weight: 600; color: var(--azul); text-decoration: none; background: none; border: 0; cursor: pointer; padding: 4px 0; }
  .pie a:hover, .pie button:hover { text-decoration: underline; }
  .pie .modi { display: flex; align-items: center; gap: 6px; color: var(--texto); font-weight: 500; }
  .pie .modi img { width: 22px; height: 22px; border-radius: 50%; }
  .esq { height: 76px; margin: 0 16px; border-bottom: 1px solid #F5F5F5; background: linear-gradient(90deg, #F5F5F5 25%, #FAFAFA 50%, #F5F5F5 75%); background-size: 200% 100%; animation: brillo 1.2s infinite; }
  @keyframes brillo { to { background-position: -200% 0; } }
  @media (max-width: 600px) {
    .fila { grid-template-columns: 48px 1fr auto; gap: 10px; padding: 10px 12px; }
    .fila img { width: 48px; height: 48px; }
    .add { padding: 8px 12px; }
  }
  `;

  var host = document.createElement("div");
  host.id = "ecomodico-buscador";
  var root = host.attachShadow({ mode: "open" });
  root.innerHTML = "<style>" + css + "</style><div class='panel' role='listbox'></div>";
  document.body.appendChild(host);
  var panel = root.querySelector(".panel");

  var campo = null;          // input de búsqueda activo
  var ultimo = null;         // última respuesta mostrada
  var categoria = null;      // chip elegido
  var sel = -1;              // fila elegida con el teclado
  var pedido = 0;            // para descartar respuestas viejas
  var timerBusqueda = null, timerIA = null, timerRegistro = null;
  var cache = {};

  function pesos(n) { return "$" + Math.round(n).toLocaleString("es-AR"); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function sinTildes(s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }

  // Resalta en el nombre las palabras buscadas (sin importar tildes ni mayúsculas).
  function resaltar(nombre, q) {
    var palabras = sinTildes(q).split(/[^a-z0-9]+/).filter(function (w) { return w.length > 2; });
    if (!palabras.length) return esc(nombre);
    var plano = sinTildes(nombre), out = "", i = 0;
    var re = new RegExp("(" + palabras.map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("|") + ")", "g");
    var m;
    while ((m = re.exec(plano))) {
      out += esc(nombre.slice(i, m.index)) + "<mark>" + esc(nombre.slice(m.index, m.index + m[0].length)) + "</mark>";
      i = m.index + m[0].length;
    }
    return out + esc(nombre.slice(i));
  }

  function ubicar() {
    if (!campo) return;
    var r = campo.getBoundingClientRect();
    var movil = window.innerWidth < 640;
    var ancho = movil ? window.innerWidth - 16 : Math.max(r.width, 520);
    var izq = movil ? 8 : Math.min(r.left, window.innerWidth - ancho - 12);
    panel.style.left = Math.max(8, izq) + "px";
    panel.style.top = (r.bottom + 8) + "px";
    panel.style.width = ancho + "px";
    panel.style.maxHeight = "min(680px, " + (window.innerHeight - r.bottom - 20) + "px)";
  }
  // En el celular la burbuja de Modi tapa el pie del panel: la escondemos mientras está abierto.
  function burbuja(ver) {
    var chat = document.getElementById("ecomodico-chat");
    if (chat) chat.style.visibility = ver || window.innerWidth >= 640 ? "" : "hidden";
  }
  function abrir() { ubicar(); panel.classList.add("abierto"); burbuja(false); }
  function cerrar() { panel.classList.remove("abierto"); sel = -1; clearTimeout(timerIA); burbuja(true); }

  function urlTodos(r) {
    return "/shop?search=" + encodeURIComponent(((r && r.consulta) || (campo && campo.value) || "").trim());
  }


  function render(r, estado) {
    ultimo = r;
    var q = r.consulta;
    var h = "";
    if (r.via === "ia") {
      h += "<div class='cab'>Ideas para <b>“" + esc(q) + "”</b></div>";
      if (r.terminos && r.terminos.length) {
        h += "<div class='chips'>" + r.terminos.map(function (t) { return "<button class='chip' data-termino='" + esc(t) + "'>" + esc(t) + "</button>"; }).join("") + "</div>";
      }
    } else if (r.titulo) {
      // "supermercado online", "bebidas", "coto": no es un producto, mostramos lo más vendido.
      h += "<div class='cab'><b>" + esc(r.titulo) + "</b></div>";
    } else if (r.corregida) {
      h += "<div class='cab'>Mostrando resultados de <b class='corr'>“" + esc(r.corregida) + "”</b></div>";
    } else if (r.total) {
      h += "<div class='cab'>" + r.total + " resultado" + (r.total === 1 ? "" : "s") + " para <b>“" + esc(q) + "”</b></div>";
    }
    if (r.categorias && r.categorias.length > 1) {
      h += "<div class='chips'><button class='chip" + (categoria ? "" : " on") + "' data-cat=''>Todo</button>" +
        r.categorias.map(function (c) {
          return "<button class='chip" + (categoria === c.nombre ? " on" : "") + "' data-cat='" + esc(c.nombre) + "'>" + esc(c.nombre) + " <small>" + c.cantidad + "</small></button>";
        }).join("") + "</div>";
    }
    h += "<div class='lista'>";
    if (!r.productos.length && estado !== "ia") {
      h += "<div class='vacio'>No encontramos “" + esc(q) + "”. Probá con otra palabra o preguntale a Modi.</div>";
    }
    r.productos.forEach(function (p, i) {
      var precio = "<span class='ya'>" + pesos(p.precio) + "</span>" +
        (p.precio_anterior ? "<s>" + pesos(p.precio_anterior) + "</s>" : "") +
        (p.descuento_pct ? "<span class='off'>-" + p.descuento_pct + "%</span>" : "") +
        (p.envio_gratis ? "<span class='gratis'>Envío gratis</span>" : "");
      var boton = p.disponible
        ? "<button class='add' data-i='" + i + "'>Agregar</button>"
        : "<span class='agotado'>Sin stock</span>";
      h += "<a class='fila' href='" + esc(p.url) + "' data-i='" + i + "'>" +
        (p.imagen ? "<img loading='lazy' alt='' src='" + esc(p.imagen) + "'>" : "<span></span>") +
        "<div><div class='nom'>" + (r.titulo ? esc(p.nombre) : resaltar(p.nombre, r.corregida || q)) + "</div><div class='precio'>" + precio + "</div></div>" + boton + "</a>";
    });
    if (estado === "ia") h += "<div class='esq'></div><div class='esq'></div><div class='esq'></div>";
    h += "</div>";
    if (estado === "ia") h += "<div class='ia'><span class='punto'></span>Buscando ideas para “" + esc(q) + "”…</div>";
    h += "<div class='pie'>" +
      (r.via !== "ia" && r.total ? "<a class='todos' href='" + esc(urlTodos(r)) + "'>Ver todos (" + r.total + ")</a>" : "<span></span>") +
      (window.Modi ? "<button class='modi'><img alt='' src='" + API + "/modi.png'>¿No es lo que buscás? Preguntale a Modi</button>" : "") +
      "</div>";
    panel.innerHTML = h;
    sel = -1;
    abrir();
  }

  async function pedir(params) {
    var clave = JSON.stringify(params);
    if (cache[clave]) return cache[clave];
    var u = API + "/api/buscar?" + Object.keys(params).map(function (k) { return k + "=" + encodeURIComponent(params[k]); }).join("&");
    var r = await (await fetch(u)).json();
    cache[clave] = r;
    return r;
  }

  async function buscar(q) {
    var n = ++pedido;
    clearTimeout(timerIA); clearTimeout(timerRegistro);
    if (!q.trim()) { cerrar(); return; }
    var params = { q: q, limite: 8, parcial: 1 };
    if (categoria) params.categoria = categoria;
    var r;
    try { r = await pedir(params); } catch (e) { return; }
    if (n !== pedido) return;
    var conIA = r.sugerir_ia && !categoria;
    render(r, conIA && !r.productos.length ? "ia" : "");
    // Registramos la búsqueda cuando el cliente deja de escribir (no cada letra).
    timerRegistro = setTimeout(function () {
      registrar("busqueda", { consulta: q, corregida: r.corregida, via: r.via, total: r.total });
    }, 1500);
    // Frases ("algo para el desayuno") o cero resultados: que Claude lo interprete, si deja de escribir.
    if (conIA) timerIA = setTimeout(function () { buscarIA(q, n); }, r.productos.length ? 900 : 500);
  }

  async function buscarIA(q, n) {
    if (n !== pedido) return;
    if (ultimo && ultimo.productos.length) render(ultimo, "ia");
    var r;
    try { r = await pedir({ q: q, limite: 8, ia: 1 }); } catch (e) { return; }
    if (n !== pedido) return;
    if (r.productos.length) {
      render(r);
      registrar("busqueda", { consulta: q, via: "ia", total: r.total });
    } else if (ultimo) render(ultimo);
  }

  // ---- carrito: misma vía que Modi (Drubbit, Vue 2, expone $shop.addToCart en la instancia raíz) ----
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
  async function agregar(p, boton, pos, consulta) {
    registrar("agregar", { consulta: consulta || (ultimo && ultimo.consulta), producto: p.nombre, posicion: pos });
    var shop = tiendaShop();
    if (!shop) { window.open(p.url, "_blank", "noopener"); return; }
    boton.disabled = true; boton.textContent = "…";
    try {
      await shop.addToCart({ productId: p.id, variantId: p.variante_id, qty: 1, sum: true, showUpsells: false, showCart: false });
      boton.disabled = false; boton.classList.add("ok"); boton.textContent = "✓ Agregado";
      setTimeout(function () { boton.classList.remove("ok"); boton.textContent = "Agregar otro"; }, 2200);
    } catch (e) {
      boton.disabled = false; boton.textContent = "Reintentar";
    }
  }

  // ---- eventos del panel ----
  panel.addEventListener("mousedown", function (e) { e.preventDefault(); }); // que el input no pierda el foco
  panel.addEventListener("click", function (e) {
    var t = e.target.closest("button, a");
    if (!t || !ultimo) return;
    if (t.classList.contains("add")) {
      e.preventDefault(); e.stopPropagation();
      var i = +t.dataset.i; agregar(ultimo.productos[i], t, i);
    } else if (t.dataset.cat !== undefined) {
      categoria = t.dataset.cat || null; buscar(campo.value);
    } else if (t.dataset.termino) {
      campo.value = t.dataset.termino; campo.dispatchEvent(new Event("input", { bubbles: true }));
    } else if (t.classList.contains("modi")) {
      registrar("modi", { consulta: ultimo.consulta, total: ultimo.total });
      cerrar(); campo.blur(); window.Modi.preguntar("Busco " + ultimo.consulta);
    } else if (t.classList.contains("todos")) {
      e.preventDefault();
      registrar("ver_todos", { consulta: ultimo.consulta, corregida: ultimo.corregida, total: ultimo.total });
      irAResultados(ultimo.consulta);
    } else if (t.classList.contains("fila")) {
      var i2 = +t.dataset.i;
      registrar("click", { consulta: ultimo.consulta, producto: ultimo.productos[i2].nombre, posicion: i2 });
    }
  });

  function marcar(i) {
    var filas = panel.querySelectorAll(".fila");
    if (!filas.length) return;
    sel = (i + filas.length) % filas.length;
    filas.forEach(function (f, k) { f.classList.toggle("sel", k === sel); });
    filas[sel].scrollIntoView({ block: "nearest" });
  }

  // ---- enganche con la barra de búsqueda de la tienda (delegado: sobrevive a re-renders de Vue) ----
  document.addEventListener("input", function (e) {
    if (!e.target.matches || !e.target.matches(SEL)) return;
    campo = e.target; categoria = null;
    clearTimeout(timerBusqueda);
    var q = campo.value;
    timerBusqueda = setTimeout(function () { buscar(q); }, 120);
  }, true);

  document.addEventListener("focusin", function (e) {
    if (e.target.matches && e.target.matches(SEL) && e.target.value.trim()) {
      campo = e.target;
      // En la página de resultados de esa misma búsqueda no tapamos la grilla con el desplegable.
      if (busquedaDeLaUrl() === campo.value.trim()) return;
      if (ultimo && ultimo.consulta === campo.value) abrir(); else buscar(campo.value);
    }
  }, true);

  document.addEventListener("keydown", function (e) {
    if (!e.target.matches || !e.target.matches(SEL)) return;
    campo = e.target;
    var abierto = panel.classList.contains("abierto");
    if (e.key === "Enter") {
      // Siempre lo resolvemos nosotros: si no, Drubbit busca la palabra tal cual ("cocacola" -> 0 resultados).
      e.preventDefault(); e.stopImmediatePropagation();
      if (abierto && sel >= 0 && ultimo && ultimo.productos[sel]) {
        registrar("click", { consulta: ultimo.consulta, producto: ultimo.productos[sel].nombre, posicion: sel });
        location.href = ultimo.productos[sel].url;
      } else if (campo.value.trim()) {
        registrar("ver_todos", { consulta: campo.value.trim() });
        irAResultados(campo.value.trim());
      }
      return;
    }
    if (!abierto) return;
    if (e.key === "ArrowDown") { e.preventDefault(); marcar(sel + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); marcar(sel - 1); }
    else if (e.key === "Escape") { cerrar(); }
  }, true);

  // Que Enter en la barra no dispare la búsqueda vieja de la tienda mientras el panel está abierto.
  document.addEventListener("keyup", function (e) {
    if (e.key === "Enter" && campo && e.target === campo) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, true);
  document.addEventListener("submit", function (e) {
    var inp = e.target.querySelector && e.target.querySelector(SEL);
    if (!inp) return;
    e.preventDefault(); e.stopImmediatePropagation();
    if (inp.value.trim()) irAResultados(inp.value.trim());
  }, true);

  document.addEventListener("mousedown", function (e) {
    if (e.target === campo || e.composedPath().indexOf(host) >= 0) return;
    cerrar();
  }, true);
  window.addEventListener("resize", ubicar);
  window.addEventListener("scroll", ubicar, true);

  // ---- página de resultados (/shop?search=...): nuestra grilla con los filtros de la tienda ----
  // Ofertas, Categoría, Marca, Ordenar por y páginas, todo con el mouse. El resto de la página es la de la tienda.
  var POR_PAGINA = 24;
  var FILA = ".container.pt-6 > .row";
  var cssPagina = `
  .res { display: grid; grid-template-columns: 220px 1fr; gap: 28px; padding: 8px 0 48px; color: var(--texto); }
  .filtros { font-size: 14px; }
  .filtros .q { font-size: 20px; font-weight: 600; word-break: break-word; }
  .filtros .n { color: var(--texto-2); margin: 2px 0 12px; }
  .activos { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
  .activo { display: inline-flex; align-items: center; gap: 6px; background: #EEE; border: 0; border-radius: 16px; padding: 5px 10px; font-size: 13px; cursor: pointer; color: var(--texto); }
  .activo:hover { background: #E2E2E2; }
  .activo .x { width: 16px; height: 16px; border-radius: 50%; background: #666; color: #fff; font-size: 11px; line-height: 16px; text-align: center; }
  .toggle-oferta { width: 100%; display: flex; justify-content: space-between; border: 0; background: var(--azul); color: #fff; font-weight: 600; font-size: 14px; border-radius: 4px; padding: 10px 10px; cursor: pointer; margin-bottom: 18px; box-shadow: 0 2px 4px rgba(0,0,0,.15); }
  .toggle-oferta:hover { background: var(--azul-osc); }
  .toggle-oferta.on { background: var(--azul-osc); box-shadow: inset 0 2px 4px rgba(0,0,0,.25); }
  .toggle-oferta small { font-weight: 400; opacity: .8; font-size: 13px; }
  .filtros h3 { font-size: 17px; font-weight: 600; margin: 8px 0 8px; }
  .item { width: 100%; display: flex; justify-content: space-between; gap: 8px; text-align: left; border: 0; background: none; padding: 7px 4px; font-size: 13.5px; letter-spacing: .02em; color: var(--texto); cursor: pointer; border-radius: 4px; }
  .item:hover { background: var(--azul-claro); }
  .item.on { color: var(--azul); font-weight: 600; }
  .item small { color: #999; font-size: 12.5px; flex-shrink: 0; }
  .item .caja { display: inline-block; width: 14px; height: 14px; border: 1.5px solid #999; border-radius: 3px; margin-right: 8px; vertical-align: -2px; }
  .item.on .caja { background: var(--azul); border-color: var(--azul); }
  .vermas { border: 0; background: none; color: var(--azul); font-size: 13px; font-weight: 600; cursor: pointer; padding: 6px 4px 14px; }
  .sep { border: 0; border-top: 1px solid #EEE; margin: 12px 0; }
  .plegar { width: 100%; display: flex; justify-content: space-between; align-items: center; border: 0; background: none; padding: 0; cursor: pointer; color: var(--texto); }
  .plegar h3 { margin: 8px 0; }
  .plegar .flecha { width: 9px; height: 9px; border-right: 2px solid #666; border-bottom: 2px solid #666; transform: rotate(45deg); margin: 0 8px 4px 0; transition: transform .15s; }
  .plegar.abierta .flecha { transform: rotate(-135deg); margin-bottom: -2px; }
  .banners { margin-top: 18px; display: flex; flex-direction: column; gap: 16px; }
  .banners a { display: block; border-radius: 12px; overflow: hidden; }
  .banners img { display: block; width: 100%; height: auto; }
  .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; }
  .top h1 { margin: 0; font-size: 22px; font-weight: 600; }
  .top .cab { padding: 2px 0 0; font-size: 14px; }
  .orden { border: 1px solid #BDBDBD; border-radius: 4px; padding: 9px 10px; font-size: 14px; background: #fff; color: var(--texto); cursor: pointer; min-width: 220px; }
  .grilla { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; }
  .card { background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,.08); padding: 14px; display: flex; flex-direction: column; gap: 8px; text-decoration: none; color: inherit; transition: box-shadow .15s; }
  .card:hover { box-shadow: 0 6px 20px rgba(0,0,0,.12); }
  .card .img { height: 170px; display: flex; align-items: center; justify-content: center; }
  .card img { max-width: 100%; max-height: 170px; object-fit: contain; }
  .card .nom { font-size: 15px; font-weight: 500; -webkit-line-clamp: 3; min-height: 3.9em; }
  .card .antes { display: flex; align-items: center; gap: 6px; min-height: 20px; }
  .card .antes s { font-size: 13px; color: #999; }
  .card .ya { font-size: 26px; font-weight: 500; color: var(--azul); line-height: 1.1; }
  .card .gratis { min-height: 16px; }
  .card .add { margin-top: auto; width: 100%; padding: 12px; font-size: 16px; }
  .card .agotado { margin-top: auto; text-align: center; padding: 12px; }
  .paginas { display: flex; justify-content: center; gap: 6px; margin-top: 32px; flex-wrap: wrap; }
  .paginas button { min-width: 38px; height: 38px; border: 1px solid #DDD; background: #fff; border-radius: 6px; font-size: 14px; cursor: pointer; color: var(--texto); }
  .paginas button:hover { border-color: var(--azul); color: var(--azul); }
  .paginas button.on { background: var(--azul); border-color: var(--azul); color: #fff; }
  .paginas button[disabled] { opacity: .4; cursor: default; }
  .paginas span { line-height: 38px; color: #999; }
  .vacio { padding: 30px 0; font-size: 16px; }
  .grilla .esq { height: 340px; margin: 0; border-radius: 12px; }
  .abrir-filtros, .cerrar-filtros, .ver-res { display: none; }
  @media (max-width: 900px) {
    .res { grid-template-columns: 1fr; gap: 0; }
    .banners { display: none; }
    .filtros { display: none; position: fixed; inset: 0; z-index: 2147483100; background: #fff; overflow-y: auto; padding: 20px 20px 90px; }
    .res.filtrando .filtros { display: block; }
    .abrir-filtros { display: block; width: 100%; border: 1px solid var(--azul); background: #fff; color: var(--azul); font-weight: 600; font-size: 15px; border-radius: 6px; padding: 11px; cursor: pointer; margin-bottom: 14px; }
    .cerrar-filtros { display: block; position: absolute; top: 14px; right: 16px; border: 0; background: none; font-size: 26px; cursor: pointer; color: var(--texto); }
    .ver-res { display: block; position: fixed; left: 16px; right: 16px; bottom: 16px; border: 0; background: var(--azul); color: #fff; font-weight: 600; font-size: 16px; border-radius: 24px; padding: 14px; cursor: pointer; }
    .top { flex-direction: column; gap: 10px; }
    .orden { width: 100%; }
    .grilla { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .card { padding: 10px; } .card .img { height: 130px; } .card img { max-height: 130px; }
    .card .nom { font-size: 13px; } .card .ya { font-size: 20px; } .card .add { font-size: 14px; padding: 10px; }
    .top h1 { font-size: 20px; }
  }`;
  global.textContent += "html.eco-res " + FILA + " > :not(#ecomodico-resultados){display:none!important}" +
    "html.eco-res .shop-sort-select{display:none!important}";
  var resHost = document.createElement("div");
  resHost.id = "ecomodico-resultados";
  resHost.style.cssText = "flex:0 0 100%;max-width:100%;padding:0 12px;box-sizing:border-box";
  var resRoot = resHost.attachShadow({ mode: "open" });
  resRoot.innerHTML = "<style>" + css + cssPagina + "</style><div class='res'></div>";
  var res = resRoot.querySelector(".res");
  var pag = null;  // { q, categoria, marcas, ofertas, orden, pagina, r, verCats, verMarcas, filtrando }
  var pedidoPagina = 0;

  function router() {
    var app = document.getElementById("app"), vm = app && app.__vue__;
    return vm && (vm.$router || (vm.$root && vm.$root.$router));
  }
  function ir(url) {
    var r = router();
    if (r) {
      // Navegación de la propia tienda (sin recargar): el buscador sigue cargado.
      try { var p = r.push(url); if (p && p.catch) p.catch(function () {}); return; } catch (e) {}
    }
    location.href = url;
  }
  function irAResultados(q) {
    clearTimeout(timerBusqueda); pedido++;  // que una búsqueda en curso no reabra el desplegable
    cerrar(); if (campo) campo.blur();
    ir("/shop?search=" + encodeURIComponent(q));
  }
  function busquedaDeLaUrl() {
    if (location.pathname.replace(/\/$/, "") !== "/shop") return null;
    var q = new URLSearchParams(location.search).get("search");
    return q && q.trim() ? q.trim() : null;
  }

  function bannersDeLaTienda() {
    var col = document.querySelector(FILA + " > .col-md-2");
    if (!col) return [];
    return [].slice.call(col.querySelectorAll("img")).map(function (i) {
      var a = i.closest("a"); return { img: i.currentSrc || i.src, href: a ? a.href : "" };
    }).filter(function (b) { return b.img && b.href; });
  }

  function tarjeta(p, i) {
    var antes = p.precio_anterior ? "<s>" + pesos(p.precio_anterior) + "</s>" + (p.descuento_pct ? "<span class='off'>" + p.descuento_pct + "% OFF</span>" : "") : "";
    return "<a class='card' href='" + esc(p.url) + "' data-i='" + i + "'>" +
      "<div class='img'>" + (p.imagen ? "<img loading='lazy' alt='' src='" + esc(p.imagen) + "'>" : "") + "</div>" +
      "<div class='nom'>" + esc(p.nombre) + "</div>" +
      "<div class='antes'>" + antes + "</div>" +
      "<div class='ya'>" + pesos(p.precio) + "</div>" +
      "<div class='gratis'>" + (p.envio_gratis ? "Envío gratis" : "") + "</div>" +
      (p.disponible ? "<button class='add' data-i='" + i + "'>Agregar</button>" : "<span class='agotado'>Sin stock</span>") + "</a>";
  }

  function lista(items, tipo, activos, todos) {
    var max = todos ? items.length : 8, h = "";
    items.slice(0, max).forEach(function (c) {
      var on = activos(c.nombre);
      h += "<button class='item" + (on ? " on" : "") + "' data-" + tipo + "='" + esc(c.nombre) + "'><span>" +
        (tipo === "marca" ? "<span class='caja'></span>" : "") + esc(c.nombre) + "</span><small>(" + c.cantidad + ")</small></button>";
    });
    if (items.length > 8) h += "<button class='vermas' data-vermas='" + tipo + "'>" + (todos ? "Ver menos" : "Ver más (" + (items.length - 8) + ")") + "</button>";
    return h;
  }

  function paginas(total) {
    var n = Math.ceil(total / POR_PAGINA), a = pag.pagina, h = "";
    if (n <= 1) return "";
    var ver = [1, n, a - 1, a, a + 1].filter(function (x, i, l) { return x >= 1 && x <= n && l.indexOf(x) === i; }).sort(function (x, y) { return x - y; });
    h += "<button data-pag='" + (a - 1) + "'" + (a === 1 ? " disabled" : "") + ">‹</button>";
    ver.forEach(function (x, i) {
      if (i && x - ver[i - 1] > 1) h += "<span>…</span>";
      h += "<button data-pag='" + x + "'" + (x === a ? " class='on'" : "") + ">" + x + "</button>";
    });
    h += "<button data-pag='" + (a + 1) + "'" + (a === n ? " disabled" : "") + ">›</button>";
    return "<nav class='paginas'>" + h + "</nav>";
  }

  function pintarPagina() {
    var r = pag.r, q = pag.q, h = "";
    // columna de filtros (como la de la tienda)
    h += "<aside class='filtros'><button class='cerrar-filtros' aria-label='Cerrar'>×</button>";
    h += "<div class='q'>" + esc(q) + "</div><div class='n'>" + (r ? r.total + " resultado/s" : "Buscando…") + "</div>";
    h += "<div class='activos'><button class='activo' data-quitar='busqueda'>Búsqueda: " + esc(q) + " <span class='x'>×</span></button>";
    if (pag.categoria) h += "<button class='activo' data-quitar='categoria'>" + esc(pag.categoria) + " <span class='x'>×</span></button>";
    pag.marcas.forEach(function (m) { h += "<button class='activo' data-quitar-marca='" + esc(m) + "'>" + esc(m) + " <span class='x'>×</span></button>"; });
    if (pag.ofertas) h += "<button class='activo' data-quitar='ofertas'>Ofertas <span class='x'>×</span></button>";
    h += "</div>";
    if (r) {
      h += "<button class='toggle-oferta" + (pag.ofertas ? " on" : "") + "'>Ofertas <small>(" + r.ofertas + ")</small></button>";
      if (r.categorias.length) h += "<h3>Categoría</h3>" + lista(r.categorias, "cat", function (n) { return pag.categoria === n; }, pag.verCats);
      if (r.marcas.length) {
        var abierta = pag.marcaAbierta || pag.marcas.length;
        h += "<button class='plegar" + (abierta ? " abierta" : "") + "'><h3>Marca</h3><span class='flecha'></span></button>" +
          (abierta ? lista(r.marcas, "marca", function (n) { return pag.marcas.indexOf(n) >= 0; }, pag.verMarcas) : "") + "<hr class='sep'>";
      }
    }
    var bs = bannersDeLaTienda();
    pag.nBanners = bs.length;
    if (bs.length) h += "<div class='banners'>" + bs.map(function (b) { return "<a href='" + esc(b.href) + "' class='banner'><img alt='' src='" + esc(b.img) + "'></a>"; }).join("") + "</div>";
    h += "<button class='ver-res'>Ver " + (r ? r.total + " " : "") + "resultados</button></aside>";
    // resultados
    h += "<main><button class='abrir-filtros'>Filtrar</button><div class='top'><div>";
    if (r && r.titulo) h += "<h1>" + esc(r.titulo) + "</h1>";
    else if (r && r.corregida) h += "<h1>“" + esc(r.corregida) + "”</h1><div class='cab'>Mostrando resultados de <b class='corr'>“" + esc(r.corregida) + "”</b> en vez de “" + esc(q) + "”</div>";
    else h += "<h1>“" + esc(q) + "”</h1>";
    h += "</div><select class='orden' aria-label='Ordenar por'>" +
      [["relevancia", "Más relevantes"], ["precio_asc", "Menor precio"], ["precio_desc", "Mayor precio"], ["descuento", "Mayor descuento"], ["nombre", "Nombre A-Z"]]
        .map(function (o) { return "<option value='" + o[0] + "'" + (pag.orden === o[0] ? " selected" : "") + ">Ordenar por: " + o[1] + "</option>"; }).join("") +
      "</select></div>";
    if (!r) h += "<div class='grilla'>" + "<div class='esq'></div>".repeat(8) + "</div>";
    else if (!r.productos.length) {
      h += "<div class='vacio'>No encontramos “" + esc(q) + "”" + (pag.categoria || pag.marcas.length || pag.ofertas ? " con esos filtros" : "") + ". Probá con otra palabra" +
        (window.Modi ? " o <button class='activo modi'>preguntale a Modi</button>" : ".") + "</div>";
    } else {
      h += "<div class='grilla'>" + r.productos.map(tarjeta).join("") + "</div>" + paginas(r.total);
    }
    h += "</main>";
    res.innerHTML = h;
    res.classList.toggle("filtrando", !!pag.filtrando);
  }

  async function cargarPagina() {
    var n = ++pedidoPagina;
    pag.r = pag.r && pag.r.consulta === pag.q ? pag.r : null;
    pintarPagina();
    var params = { q: pag.q, limite: POR_PAGINA, desde: (pag.pagina - 1) * POR_PAGINA, completo: 1, orden: pag.orden };
    if (pag.categoria) params.categoria = pag.categoria;
    if (pag.marcas.length) params.marca = pag.marcas.join("|");
    if (pag.ofertas) params.ofertas = 1;
    var r;
    try { r = await pedir(params); } catch (e) { return; }
    if (n !== pedidoPagina) return;
    pag.r = r;
    registrar("busqueda", { consulta: pag.q, corregida: r.corregida, via: r.via, total: r.total });
    pintarPagina();
  }
  function cambiar(f) {  // aplica un cambio de filtro y vuelve a la página 1
    f(); pag.pagina = 1; cargarPagina();
    var top = resHost.getBoundingClientRect().top + window.scrollY - 140;
    if (window.scrollY > top) window.scrollTo({ top: top, behavior: "smooth" });
  }

  res.addEventListener("change", function (e) {
    if (e.target.classList.contains("orden")) { var v = e.target.value; cambiar(function () { pag.orden = v; }); }
  });
  res.addEventListener("click", function (e) {
    var t = e.target.closest("button, a");
    if (!t || !pag) return;
    var d = t.dataset;
    if (t.classList.contains("add")) {
      e.preventDefault(); e.stopPropagation();
      var i = +d.i; agregar(pag.r.productos[i], t, (pag.pagina - 1) * POR_PAGINA + i, pag.q);
    } else if (t.classList.contains("card")) {
      registrar("click", { consulta: pag.q, producto: pag.r.productos[+d.i].nombre, posicion: (pag.pagina - 1) * POR_PAGINA + +d.i });
    } else if (d.cat !== undefined) {
      cambiar(function () { pag.categoria = pag.categoria === d.cat ? null : d.cat; pag.marcas = []; });
    } else if (d.marca !== undefined) {
      cambiar(function () { var k = pag.marcas.indexOf(d.marca); if (k >= 0) pag.marcas.splice(k, 1); else pag.marcas.push(d.marca); });
    } else if (t.classList.contains("plegar")) {
      pag.marcaAbierta = !(pag.marcaAbierta || pag.marcas.length); pintarPagina();
    } else if (t.classList.contains("banner")) {
      var u = new URL(t.href);
      if (u.origin === location.origin) { e.preventDefault(); ir(u.pathname + u.search); }
    } else if (t.classList.contains("toggle-oferta")) {
      cambiar(function () { pag.ofertas = !pag.ofertas; });
    } else if (d.quitar === "busqueda") {
      ir("/shop");
    } else if (d.quitar) {
      cambiar(function () { if (d.quitar === "categoria") { pag.categoria = null; pag.marcas = []; } else pag.ofertas = false; });
    } else if (d.quitarMarca !== undefined) {
      cambiar(function () { pag.marcas = pag.marcas.filter(function (m) { return m !== d.quitarMarca; }); });
    } else if (d.vermas) {
      if (d.vermas === "cat") pag.verCats = !pag.verCats; else pag.verMarcas = !pag.verMarcas;
      pintarPagina();
    } else if (d.pag) {
      pag.pagina = +d.pag; cargarPagina();
      window.scrollTo({ top: Math.max(0, resHost.getBoundingClientRect().top + window.scrollY - 140), behavior: "smooth" });
    } else if (t.classList.contains("abrir-filtros")) {
      pag.filtrando = true; res.classList.add("filtrando"); burbuja(false);
    } else if (t.classList.contains("cerrar-filtros") || t.classList.contains("ver-res")) {
      pag.filtrando = false; res.classList.remove("filtrando"); burbuja(true);
    } else if (t.classList.contains("modi")) {
      registrar("modi", { consulta: pag.q, total: 0 });
      window.Modi.preguntar("Busco " + pag.q);
    }
  });

  // La tienda es una SPA (Vue): miramos la URL y volvemos a poner la grilla si Vue la re-dibuja.
  var urlVista = null;
  function revisarPagina() {
    var q = busquedaDeLaUrl();
    document.documentElement.classList.toggle("eco-res", !!q);
    if (!q) { if (resHost.isConnected) resHost.remove(); urlVista = null; return; }
    var fila = document.querySelector(FILA);
    if (fila && resHost.parentElement !== fila) fila.insertBefore(resHost, fila.firstChild);
    if (pag && pag.r && bannersDeLaTienda().length !== pag.nBanners) pintarPagina();
    if (location.href !== urlVista) {
      urlVista = location.href;
      pag = { q: q, categoria: null, marcas: [], ofertas: false, orden: "relevancia", pagina: 1, r: null };
      cargarPagina();
      window.scrollTo(0, 0);
    }
  }
  setInterval(revisarPagina, 250);
  revisarPagina();
})();
