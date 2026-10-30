const direccion = document.body.dataset.escena;
const lienzo = document.querySelector('canvas');
const contenedor = document.querySelector('#personas');
const reducido = matchMedia('(prefers-reduced-motion: reduce)');
const nombres = ['Musculación', 'Peso libre', 'Cardio', 'Funcional', 'En la sede'];
const zonas = [[12, 12, 34, 30], [54, 12, 34, 30], [12, 48, 34, 30], [54, 48, 34, 30], [12, 84, 76, 12]];
const datos = await (await fetch('../personas.json')).json();
let personas = datos.personas.map(p => ({...p}));
let secuencia = 0;
let siguiente = 41;
let seleccion = null;
let dibujar3d;
const color = nombre => getComputedStyle(document.body).getPropertyValue(nombre).trim();
const puerta = {x:50,y:97};
function destino(persona) {
  const indice = nombres.indexOf(persona.zona);
  const [x,y,ancho,alto] = zonas[indice];
  const usados = new Set(personas.filter(p => p !== persona && p.zona === persona.zona && !p.saliendo && p.lugar !== undefined).map(p => p.lugar));
  let lugar = 0;
  while (usados.has(lugar)) lugar++;
  persona.lugar = lugar;
  const columnas = indice === 4 ? Math.max(10, lugar+1, ...[...usados].map(l => l+1)) : 4;
  return {x:x+4+(lugar%columnas)*(ancho-8)/(columnas-1), y:indice === 4 ? y+7 : y+11+Math.floor(lugar/columnas)*(alto-15)/2};
}
function rotulo() {
  const persona = personas.find(p => p.id === seleccion);
  document.querySelector('#rotulo').textContent = persona
    ? `Visita ${persona.id} · ${persona.zona} · ${persona.minutos} min${persona.simulada ? ' · Visita simulada' : ''}${persona.saliendo ? ' · Salida' : ''}`
    : 'Seleccioná un punto con ratón o Tab y Enter. Cuadrado terracota: visita simulada.';
}
function actualizar() {
  // La franja comparte una fila: redistribuirla al ocupar o liberar lugares.
  for (const persona of personas.filter(p => p.zona === nombres[4] && !p.saliendo)) {
    const hasta = destino(persona);
    const anterior = persona.hasta || persona.posicion;
    if (anterior.x !== hasta.x || anterior.y !== hasta.y) mover(persona, hasta);
  }
  document.querySelector('#total').textContent = `${personas.filter(p => !p.saliendo).length} de ${datos.aforo_maximo}`;
  document.querySelector('#zonas').textContent = nombres.map(z => `${z}: ${personas.filter(p => p.zona === z && !p.saliendo).length}`).join(' · ');
  for (const persona of personas) {
    if (persona.boton) continue;
    const boton = document.createElement('button');
    boton.className = `persona${persona.simulada ? ' simulada' : ''}`;
    boton.setAttribute('aria-label', `Visita ${persona.id}${persona.simulada ? ', simulada' : ''}`);
    boton.setAttribute('aria-pressed', 'false');
    boton.addEventListener('click', () => {
      seleccion = persona.id;
      for (const p of personas) p.boton.setAttribute('aria-pressed', String(p.id === seleccion));
      rotulo();
    });
    persona.boton = boton;
    contenedor.append(boton);
  }
  rotulo();
}
function mover(persona, hasta) {
  persona.desde = {...persona.posicion};
  persona.hasta = hasta;
  persona.inicio = performance.now();
}
function avanzar() {
  const tipo = secuencia++ % 3;
  if (tipo === 0) {
    const persona = {id:siguiente++,zona:nombres[secuencia%5],simulada:true,minutos:0,posicion:{...puerta}};
    personas.push(persona);
    mover(persona,destino(persona));
    document.querySelector('#evento').textContent = `Entrada · visita ${persona.id}`;
  } else {
    const persona = personas.filter(p => !p.saliendo)[secuencia % personas.filter(p => !p.saliendo).length];
    if (tipo === 1) {
      persona.zona = nombres[(nombres.indexOf(persona.zona)+1)%5];
      mover(persona,destino(persona));
      document.querySelector('#evento').textContent = `Cambio de zona de la sede · visita ${persona.id} → ${persona.zona}`;
    } else {
      persona.saliendo = true;
      mover(persona,puerta);
      document.querySelector('#evento').textContent = `Salida · visita ${persona.id}`;
    }
  }
  actualizar();
}
let proyectar = p => p;
if (direccion === 'a') {
  const T = await import('three');
  const escena = new T.Scene();
  const camara = new T.OrthographicCamera(-76,76,65,-65,.1,500);
  camara.position.set(110,150,130);camara.lookAt(0,0,0);
  const dibujante = new T.WebGLRenderer({canvas:lienzo,antialias:true,alpha:true});
  dibujante.setPixelRatio(Math.min(devicePixelRatio,2));
  escena.add(new T.AmbientLight(0xffffff,2));
  const luz = new T.DirectionalLight(0xffffff,3);luz.position.set(30,100,40);escena.add(luz);
  zonas.forEach(([x,y,ancho,alto],i) => {
    const pieza = new T.Mesh(new T.BoxGeometry(ancho,3,alto),new T.MeshStandardMaterial({color:color(i%2 ? '--borde' : '--superficie'),roughness:.7}));
    pieza.position.set(x+ancho/2-50,-2,y+alto/2-50);escena.add(pieza);
    const borde = new T.LineSegments(new T.EdgesGeometry(pieza.geometry),new T.LineBasicMaterial({color:color('--texto-suave')}));pieza.add(borde);
  });
  proyectar = p => {const v = new T.Vector3(p.x-50,1,p.y-50).project(camara);return {x:(v.x+1)*50,y:(1-v.y)*50};};
  dibujar3d = () => {
    const proporcion = lienzo.clientWidth/lienzo.clientHeight;
    const mitad = Math.max(65,76/proporcion);
    camara.left = -mitad*proporcion;camara.right = mitad*proporcion;
    camara.top = mitad;camara.bottom = -mitad;camara.updateProjectionMatrix();
    dibujante.setSize(lienzo.clientWidth,lienzo.clientHeight,false);dibujante.render(escena,camara);
  };
  camara.updateMatrixWorld();
} else {
  const contexto = lienzo.getContext('2d');
  dibujar3d = () => {
    lienzo.width = lienzo.clientWidth*devicePixelRatio;lienzo.height = lienzo.clientHeight*devicePixelRatio;
    contexto.scale(lienzo.width/100,lienzo.height/100);
    zonas.forEach(([x,y,ancho,alto],i) => {
      contexto.shadowColor = '#1e1b1640';contexto.shadowBlur = 18;contexto.shadowOffsetY = 8;
      const luz = contexto.createLinearGradient(x,y,x+ancho,y+alto);
      luz.addColorStop(0,color('--superficie-elevada'));luz.addColorStop(1,color('--borde'));
      contexto.fillStyle = luz;contexto.fillRect(x,y,ancho,alto);
      contexto.shadowBlur = 0;contexto.shadowOffsetY = 0;
      contexto.strokeStyle = color('--borde');contexto.lineWidth = .25;contexto.strokeRect(x,y,ancho,alto);
      contexto.fillStyle = color('--texto-suave');contexto.font = '2.5px Segoe UI';contexto.fillText(nombres[i],x+2,y+5);
    });
  };
}
// Ambos planos usan botones superpuestos: la misma selección con teclado, ratón y toque.
function etiquetas() {
  contenedor.querySelectorAll('.etiqueta').forEach(e => e.remove());
  if (direccion === 'a') zonas.forEach(([x,y],i) => {
    const etiqueta = document.createElement('span');const p = proyectar({x:x+12,y:y+2});
    etiqueta.className = 'etiqueta';
    etiqueta.textContent = nombres[i];etiqueta.style.cssText = `position:absolute;left:${p.x}%;top:${p.y}%;font-size:11px;pointer-events:none`;
    contenedor.append(etiqueta);
  });
  const entrada = document.createElement('span');const p = proyectar(puerta);
  entrada.className = 'etiqueta';entrada.textContent = 'Puerta';
  entrada.style.cssText = `position:absolute;left:${p.x}%;top:${p.y}%;font-size:11px;pointer-events:none`;
  contenedor.append(entrada);
}
personas.forEach(p => {p.posicion=destino(p);});
actualizar();etiquetas();
let cuadros = [];
let anterior;
let ultimaMedicion = 0;
const inicio = performance.now();
window.prototipo = {avanzar, get personas(){return personas;}, get fps(){return medicion;}, listo:true};
let medicion = {};
function cuadro(ahora) {
  if (anterior && !document.hidden) cuadros.push({tiempo:ahora,intervalo:ahora-anterior});
  anterior = ahora;
  cuadros = cuadros.filter(c => c.tiempo >= ahora-10000);
  for (const persona of [...personas]) {
    if (persona.hasta) {
      const progreso = reducido.matches ? 1 : Math.min(1,(ahora-persona.inicio)/1400);
      persona.posicion = {x:persona.desde.x+(persona.hasta.x-persona.desde.x)*progreso,y:persona.desde.y+(persona.hasta.y-persona.desde.y)*progreso};
      if (progreso === 1) {
        persona.hasta = null;
        if (persona.saliendo) {persona.boton.remove();personas = personas.filter(p => p !== persona);rotulo();continue;}
      }
    }
    const p = proyectar(persona.posicion);
    persona.boton.style.left = `${p.x}%`;persona.boton.style.top = `${p.y}%`;
  }
  if (ahora-ultimaMedicion>500) {
    const fps = cuadros.map(c => 1000/c.intervalo).sort((a,b)=>a-b);
    medicion = {promedio:cuadros.length ? 1000*cuadros.length/cuadros.reduce((n,c)=>n+c.intervalo,0) : 0,percentil_5:fps[Math.floor(fps.length*.05)] || 0,segundos:Math.min(10,(ahora-inicio)/1000)};
    document.querySelector('#fps').textContent = `${medicion.promedio.toFixed(1)} fps promedio · ${medicion.percentil_5.toFixed(1)} p5 · últimos ${medicion.segundos.toFixed(0)} s`;
    ultimaMedicion = ahora;
  }
  requestAnimationFrame(cuadro);
}
document.addEventListener('visibilitychange',()=>{anterior=null;cuadros=[];});
new ResizeObserver(() => {dibujar3d();etiquetas();}).observe(lienzo);
dibujar3d();etiquetas();requestAnimationFrame(cuadro);setInterval(avanzar,2000);
