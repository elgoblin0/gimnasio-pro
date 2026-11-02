// Presentación común a todas las páginas: transiciones entre páginas (estilos/base.css) y modo sin efectos
// (comun/efectos.js). Es un script clásico del <head> para correr antes del primer pintado.

// La elección guardada del modo sin efectos se aplica antes de que la página anime; la detección completa
// llega después con el interruptor.
try {
  const eleccion = localStorage.getItem("gimnasio-sin-efectos");
  if (eleccion === "si" || eleccion === "no") document.documentElement.dataset.sinEfectos = eleccion;
} catch { /* Sin almacenamiento decide la detección. */ }

// Si una navegación nueva interrumpe la anterior, el navegador aborta la transición y rechaza sus promesas;
// sin estos manejadores el rechazo queda como error de la página. pageswap lo dispara la página que se va;
// pagereveal, la que llega. En el modo sin efectos la transición se saltea.
function prepararTransicion(evento) {
  const transicion = evento.viewTransition;
  if (!transicion) return;
  for (const promesa of [transicion.ready, transicion.finished, transicion.updateCallbackDone]) promesa?.catch(() => {});
  if (document.documentElement.dataset.sinEfectos === "si") transicion.skipTransition();
}
addEventListener("pageswap", prepararTransicion);
addEventListener("pagereveal", prepararTransicion);

// Un recorrido guiado en curso sigue en cada página que abre (ADR 0032), salvo dentro de un marco como el
// pago de la tarjeta contextual.
let recorridoEnCurso = false;
try { recorridoEnCurso = window.top === window && Boolean(sessionStorage.getItem("gimnasio-recorrido")); } catch { /* Sin almacenamiento no hay recorrido. */ }

addEventListener("DOMContentLoaded", () => {
  import("/js/comun/efectos.js").then((efectos) => efectos.montarInterruptorEfectos()).catch(() => {});
  if (recorridoEnCurso) import("/js/recorrido.js").catch(() => {});
});
