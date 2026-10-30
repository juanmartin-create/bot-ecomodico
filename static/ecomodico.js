/* Todo lo de Ecomodico en una sola línea: carga el chat de Modi y el buscador.
 * Uso: <script src="https://tu-servidor/ecomodico.js" defer></script>
 * Opcional: data-api="https://tu-servidor" si la API vive en otro origen.
 */
(function () {
  var script = document.currentScript;
  if (!script) return;
  var url = new URL(script.src), base = url.origin;
  var api = script.dataset.api;
  ["widget.js", "buscador.js"].forEach(function (f) {
    var s = document.createElement("script");
    s.src = base + "/" + f + url.search;  // "?123" del favorito o la consola: trae siempre la versión nueva

    s.defer = true;
    if (api) s.dataset.api = api;
    document.body.appendChild(s);
  });
})();
