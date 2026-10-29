import * as THREE from "three";
import { ZONAS_CUERPO } from "./zonas.js";

export async function crearCuerpo(contenedor, svg, seleccionable) {
  const documento = contenedor.ownerDocument;
  const ventana = documento.defaultView;
  const lienzo = documento.createElement("canvas");
  lienzo.style.cssText = "width:100%;height:400px;display:block;touch-action:pan-y";
  lienzo.setAttribute("aria-label", "Cuerpo 3D muscular. Arrastrá para girar; elegí zonas en la lista inferior.");
  const dibujante = new THREE.WebGLRenderer({canvas: lienzo, antialias: true, alpha: true});
  dibujante.setPixelRatio(Math.min(ventana.devicePixelRatio, 2));
  const escena = new THREE.Scene();
  const cuerpo = new THREE.Group(); escena.add(cuerpo);
  const camara = new THREE.PerspectiveCamera(36, 1, .01, 30);
  camara.position.set(0, 1, 3.8); camara.lookAt(0, .9, 0);
  escena.add(new THREE.HemisphereLight(0xffffff, 0x5c554a, 2.8));
  const luz = new THREE.DirectionalLight(0xffffff, 3);
  luz.position.set(2, 3, 4); escena.add(luz);
  const materiales = ZONAS_CUERPO.map(() => new THREE.MeshStandardMaterial({roughness: .8, side: THREE.DoubleSide}));
  const neutro = new THREE.MeshStandardMaterial({color: "#c9bfae", roughness: .8});
  const superficies = [];
  function zonaDelPunto(x, y, z) {
    const lateral = Math.abs(x);
    if (y > 1.6) return -1;
    if (y > 1.48 && lateral < 0.12) return 13;
    if (lateral > 0.23 && y > 1.25) {
      if (lateral < 0.36) return 3;
      if (lateral < 0.64) return z >= -0.08 ? 4 : 5;
      return -1;
    }
    if (y > 1.28) return z >= 0 ? 0 : 1;
    if (y > 1.05) return z >= 0 ? 6 : (lateral > 0.11 ? 2 : 11);
    if (y > 0.83) return z >= 0 ? 6 : 7;
    if (y > 0.57) return z >= 0 ? 8 : 9;
    if (y > 0.43) return 12;
    return 10;
  }
  async function cargarModelo() {
    const {GLTFLoader} = await import('../../vendor/three@0.186.0/loaders/GLTFLoader.js');
    const gltf = await new GLTFLoader().loadAsync(new URL("../../vendor/cuerpo@1/cuerpo.glb", import.meta.url).href);
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse(objeto => {
      if (!objeto.isMesh) return;
      const geometria = objeto.geometry.index ? objeto.geometry.toNonIndexed() : objeto.geometry.clone();
      geometria.applyMatrix4(objeto.matrixWorld);
      const posiciones = geometria.attributes.position;
      geometria.clearGroups();
      for (let i = 0; i < posiciones.count; i += 3) {
        const centro = new THREE.Vector3();
        for (let j = 0; j < 3; j++) centro.add(new THREE.Vector3().fromBufferAttribute(posiciones, i + j));
        centro.divideScalar(3);
        const zona = zonaDelPunto(centro.x, centro.y, centro.z);
        geometria.addGroup(i, 3, zona < 0 ? 14 : zona);
      }
      // Ordenar índices por zona: como máximo quince llamadas por malla.
      const indices = Array.from({length: 15}, () => []);
      for (const grupo of geometria.groups) {
        indices[grupo.materialIndex].push(grupo.start, grupo.start + 1, grupo.start + 2);
      }
      geometria.clearGroups();
      const ordenados = [];
      indices.forEach((lista, zona) => {
        if (lista.length) geometria.addGroup(ordenados.length, lista.length, zona);
        ordenados.push(...lista);
      });
      geometria.setIndex(ordenados);
      const malla = new THREE.Mesh(geometria, [...materiales, neutro]);
      cuerpo.add(malla); superficies.push(malla);
    });
  }

  function liberar() {
    for (const malla of superficies) malla.geometry.dispose();
    for (const material of [...materiales, neutro]) material.dispose();
    dibujante.dispose();
  }
  try { await cargarModelo(); } catch (error) { liberar(); throw error; }
  if (!svg.isConnected || ventana.matchMedia("(prefers-reduced-motion: reduce)").matches) { liberar(); return; }
  const controles = [...svg.querySelectorAll("[data-zona]")];
  const indiceEnFoco = controles.indexOf(documento.activeElement);
  const lista = documento.createElement("div");
  lista.setAttribute("aria-label", "Zonas del cuerpo");
  const botones = controles.map(control => {
    const boton = documento.createElement(seleccionable ? "button" : "p");
    if (seleccionable) {
      boton.type = "button";
      boton.setAttribute("role", "checkbox");
      boton.addEventListener("click", () => control.dispatchEvent(new ventana.MouseEvent("click")));
    }
    boton.dataset.zona = control.dataset.zona;
    lista.append(boton);
    return boton;
  });
  function dibujar() {
    controles.forEach((control, indice) => {
      const dolor = control.getAttribute("aria-checked") === "true" || control.dataset.dolor === "true";
      materiales[indice].color.set(dolor ? "#b2452a" : control.dataset.trabajada === "true" ? "#1f5a43" : "#c9bfae");
      botones[indice].textContent = control.querySelector("text").textContent;
      if (seleccionable) {
        botones[indice].setAttribute("aria-checked", String(dolor));
        botones[indice].disabled = control.getAttribute("aria-disabled") === "true";
      }
    });
    const ancho = Math.max(contenedor.getBoundingClientRect().width, 1);
    dibujante.setSize(ancho, 400, false);
    camara.aspect = ancho / 400; camara.updateProjectionMatrix();
    dibujante.render(escena, camara);
  }
  let arrastre;
  lienzo.addEventListener("pointerdown", e => {
    arrastre = {x: e.clientX, inicio: e.clientX, y: e.clientY};
    lienzo.setPointerCapture(e.pointerId);
  });
  lienzo.addEventListener("pointermove", e => {
    if (!arrastre) return;
    cuerpo.rotation.y += (e.clientX - arrastre.x) * .012;
    arrastre.x = e.clientX; dibujar();
  });
  lienzo.addEventListener("pointerup", e => {
    if (seleccionable && arrastre && Math.hypot(e.clientX-arrastre.inicio, e.clientY-arrastre.y) < 5) {
      const rect = lienzo.getBoundingClientRect();
      const rayo = new THREE.Raycaster();
      rayo.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1, -(e.clientY-rect.top)/rect.height*2+1), camara);
      const impacto = rayo.intersectObjects(superficies)[0];
      if (impacto && impacto.face.materialIndex < controles.length) botones[impacto.face.materialIndex].click();
    }
    arrastre = null;
  });
  lienzo.addEventListener("pointercancel", () => { arrastre = null; });
  const preferencia = ventana.matchMedia("(prefers-reduced-motion: reduce)");
  const observador = new ventana.MutationObserver(dibujar);
  const ajuste = new ventana.ResizeObserver(dibujar);
  const presencia = new ventana.MutationObserver(() => {
    if (!lienzo.isConnected) restaurar();
  });
  function restaurar() {
    observador.disconnect(); ajuste.disconnect(); presencia.disconnect();
    preferencia.removeEventListener("change", restaurar);
    lienzo.remove(); lista.remove(); svg.removeAttribute("hidden"); svg.style.display = "";
    delete contenedor.dataset.cuerpo3d; liberar();
  }
  lienzo.addEventListener("webglcontextlost", e => { e.preventDefault(); restaurar(); }, {once: true});
  preferencia.addEventListener("change", restaurar, {once: true});
  contenedor.prepend(lienzo); contenedor.append(lista);
  svg.setAttribute("hidden", "");
  svg.style.display = "none";
  observador.observe(svg, {attributes: true, subtree: true});
  ajuste.observe(contenedor); dibujar();
  if (indiceEnFoco >= 0) botones[indiceEnFoco].focus();
  presencia.observe(documento.body, {childList: true, subtree: true});
  contenedor.dataset.cuerpo3d = "listo";
}
