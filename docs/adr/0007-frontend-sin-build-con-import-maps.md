# 0007. Construir el frontend sin build, con módulos ES e import maps

- Estado: aceptado
- Fecha: 2026-10-26
- Decide: Opus

## Contexto
La demo quiere mostrar lo que da JavaScript moderno sin framework. La app se instala como PWA en escritorio, y el repo debe correr sin `npm install`.

## Decisión
- `gimnasio/static/` contiene:
  - `js/`: módulos ES por pantalla y una carpeta `comun/`;
  - `estilos/`: tokens y componentes;
  - `vendor/`: librerías de terceros.
- Las librerías se copian a `static/vendor/<nombre>@<version>/` con su licencia.
  - `static/vendor/VERSIONES.md` registra la versión, la URL de origen y el SHA-256.
  - Candidatas: Three.js, una librería de animación y una de gráficos. Cada una se elige en su primer uso, con un ADR corto.
- Cada página HTML declara un `<script type="importmap">`. No se usan CDN en tiempo de ejecución: la demo no depende de terceros.
- `static/manifest.webmanifest` y un service worker mínimo, `static/sw.js`, habilitan la instalación y cachean los recursos estáticos con una lista versionada. No hay registro sin conexión (VISION, 2026-10-27).
- Los módulos puros de JS (formatos, ids, reloj) se prueban con `node --test`, sin dependencias.
- Los estilos usan propiedades personalizadas de CSS (tokens) y capas `@layer`. Toda animación respeta `prefers-reduced-motion`.

## Consecuencias
No hay `node_modules` ni build, y Flask sirve todo. A cambio, las librerías se actualizan a mano y no hay minificación; el service worker lo compensa en las visitas siguientes.

## Alternativas descartadas
- React, Vue o Svelte: contradicen el objetivo de la demo.
- Vite u otro bundler: agregan el paso de build que se decidió evitar.
