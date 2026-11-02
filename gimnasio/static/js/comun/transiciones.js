// Transiciones entre páginas (estilos/base.css). Si una navegación nueva interrumpe la anterior, el
// navegador la aborta y rechaza sus promesas; sin estos manejadores el rechazo queda como error de la página.
// pageswap lo dispara la página que se va; pagereveal, la que llega.
function ignorarAborto(evento) {
  const transicion = evento.viewTransition;
  if (!transicion) return;
  for (const promesa of [transicion.ready, transicion.finished, transicion.updateCallbackDone]) promesa?.catch(() => {});
}

addEventListener("pageswap", ignorarAborto);
addEventListener("pagereveal", ignorarAborto);
