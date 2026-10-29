# Indicadores de evaluación → aplicación modular vigente

Guía para explicar el recorrido de etapa 1. Las referencias `archivo:línea` señalan el comienzo de la evidencia. El alcance verificado está en [el mapa de capacidades](docs/MAPA-CAPACIDADES.md); esta guía no declara terminada la etapa 2 ni reemplaza el cierre del dueño en #52.

## Base de datos (5 pts)

| Indicador | Evidencia vigente |
|---|---|
| Implementación | Sedes y personas: `migraciones/0001_sedes_y_personas.sql:2`. Usuarios y asignaciones: `migraciones/0002_usuarios_y_asignaciones.sql:2`. Membresías: `migraciones/0006_membresias.sql:2`. Programa versionado: `migraciones/0007_programas_entrenamiento.sql:11`. Entradas y salidas con claves foráneas: `migraciones/0008_entradas_y_salidas.sql:2`. Sesiones y series realizadas: `migraciones/0009_sesiones_y_series_realizadas.sql:2`. |
| C.R.U.D. | Creación y lectura del recorrido: `gimnasio/visitas/repositorio.py:72`, `gimnasio/visitas/repositorio.py:165`, `gimnasio/entrenamiento/repositorio.py:146`, `gimnasio/entrenamiento/repositorio.py:218`. Los hechos solo se insertan: no se presenta un CRUD destructivo sobre visitas o series. La interfaz de etapa 1 no ofrece edición o eliminación general de socios. |
| Conexión desde Python | Parámetros desde el entorno: `gimnasio/comun/bd.py:13`. Conexión UTC: `gimnasio/comun/bd.py:29`. Transacción: `gimnasio/comun/bd.py:49`. SQL parametrizado: `gimnasio/visitas/repositorio.py:78`. |
| Migraciones y datos ficticios | Aplicador con versiones y sumas: `gimnasio/comun/migrar.py:48`. Semilla demo: `gimnasio/demo/servicio.py:244`. El SQL heredado no forma parte de este esquema. |

## Python (10 pts)

| Indicador | Evidencia vigente |
|---|---|
| Manejo de rutas | Fábrica y blueprints: `gimnasio/__init__.py:25`. Entradas, salidas y consultas: `gimnasio/visitas/rutas.py:12`. Propuesta: `gimnasio/entrenamiento/rutas.py:23`. Inicio de sesión realizada y series: `gimnasio/entrenamiento/rutas.py:36`. |
| Conexión y paso de información con el cliente | Las rutas reciben JSON y responden JSON con códigos HTTP: `gimnasio/visitas/rutas.py:14`, `gimnasio/entrenamiento/rutas.py:38`. Errores JSON: `gimnasio/comun/errores.py:17`. La fábrica sirve los estáticos de `gimnasio/static/`. |
| Iteradores y condicionales | Selección de primera sesión pendiente y composición de doble progresión: `gimnasio/reglas/sesion.py:7`. Vigencia, visita abierta y aforo: `gimnasio/visitas/servicio.py:41`. Serialización de programa: `gimnasio/entrenamiento/servicio.py:124`. |
| Comportamiento comprobado | E2E integrado con MySQL real y ambos anchos: `pruebas/e2e/test_esqueleto_andante.py:110`. Comprobación de solo inserciones: `pruebas/test_historial_inserciones.py:1`. Los resultados concretos se verifican en los checks del PR; las pruebas omitidas no acreditan el recorrido. |

## JavaScript (5 pts)

| Indicador | Evidencia vigente |
|---|---|
| Iteradores y condicionales | Renderizado de visitas: `gimnasio/static/js/recepcion.js:22`. Formularios según medidas aplicables: `gimnasio/static/js/entrenamiento.js:57`. Explicación y ejercicios: `gimnasio/static/js/entrenamiento.js:125`. |
| Comunicación y errores | Cliente fetch común, encabezados de escritura y lectura JSON: `gimnasio/static/js/comun/api.js:17`. Actualización de recepción: `gimnasio/static/js/recepcion.js:47`. Actualización del entrenamiento: `gimnasio/static/js/entrenamiento.js:179`. |
| Persistencia y reintentos | Operaciones con cuerpo, identificador y clave conservados: `gimnasio/static/js/comun/operaciones.js:4`. Recuperación de sesión realizada desde la URL: `gimnasio/static/js/entrenamiento.js:179`. Cerrar sesión solo borra la sesión de usuario: `gimnasio/static/js/comun/operaciones.js:31`. |

## HTML (5 pts)

| Indicador | Evidencia vigente |
|---|---|
| Construcción y estructura | Inicio con idioma español, viewport y dirección B: `gimnasio/static/index.html:2`. Formulario de ingreso: `gimnasio/static/index.html:30`. Recepción y entrenamiento usan `main`, `header`, secciones y controles etiquetados: `gimnasio/static/recepcion.html:17`, `gimnasio/static/entrenamiento.html:17`. |
| Coordinación con el servidor | Formulario de entrada y selección de socio: `gimnasio/static/recepcion.html:38`, conectado por el módulo de recepción. Los formularios de series se crean según la respuesta real: `gimnasio/static/js/entrenamiento.js:57`. |
| Navegación | La pantalla inicial ofrece enlaces según rol; recepción y entrenamiento vuelven a inicio y permiten cerrar sesión: `gimnasio/static/recepcion.html:18`, `gimnasio/static/entrenamiento.html:18`. |

## Hojas de estilo y CSS (5 + 5 pts)

| Indicador | Evidencia vigente |
|---|---|
| Espacios y adaptación | Ancho máximo, espaciado y formulario grid: `gimnasio/static/estilos/base.css:17`. Grilla de recorrido: `gimnasio/static/estilos/recorrido.css:13`. Una columna en celular: `gimnasio/static/estilos/recorrido.css:22`. |
| Construcción visual | Tokens semánticos de B: `gimnasio/static/estilos/tokens.css:7`. Tema oscuro: `gimnasio/static/estilos/tokens.css:61`. Cifras, tarjetas y jerarquía: `gimnasio/static/estilos/recorrido.css:4`. |
| Importación y reutilización | Las tres pantallas comparten tokens y base: `gimnasio/static/index.html:10`. Recepción y entrenamiento comparten recorrido: `gimnasio/static/recepcion.html:10`, `gimnasio/static/entrenamiento.html:10`. |
| Selectores de etiquetas y estados | `body`, `main`, `section`, `form`, `label`, controles y foco visible: `gimnasio/static/estilos/base.css:10`. Estado deshabilitado: `gimnasio/static/estilos/recorrido.css:8`. Movimiento reducido: `gimnasio/static/estilos/base.css:43`. No se acredita un efecto `:hover` específico: el estilo vigente prioriza foco y estados de controles. |

## Funcionamiento y conocimiento del sistema (1 pt)

1. Recepción inicia sesión y registra una entrada. La ruta autoriza el rol y el servicio verifica vigencia, visita abierta y aforo dentro de una transacción.
2. El socio inicia sesión, recibe la primera sesión planificada pendiente y registra series con la prescripción propuesta y la explicación de cada ajuste.
3. La recarga recupera sus hechos. Recepción registra la salida y la ocupación vuelve al valor inicial. Cerrar sesión de usuario es una operación diferente.

El motor 2.0 agrega doble progresión con RIR y tope semanal (ADR 0012, 0015 y 0016), sin reiniciar la secuencia al cambiar de semana. Los vectores están en `pruebas/reglas/test_progresion.py:1`; el recorrido de la semilla, en `pruebas/e2e/test_progresion_demo.py:1`. El chequeo del día aplica el freno 4 y cada freno deja un aviso al entrenador (#88). El dolor reportado aplica el freno 1, sustituye o quita ejercicios y no sube la carga en la sesión actual ni en la siguiente (#89). Las restricciones quedan para el issue siguiente. El E2E comprueba además visita sin entrenamiento, sesión parcial, reingreso, aforo lleno y reintento sin duplicación.

## Modificación solicitada (5 pts): puntos de cambio

| Si piden… | Punto de cambio |
|---|---|
| Una regla de propuesta | Motor puro `gimnasio/reglas/sesion.py:7`, con issue explícito y revisión independiente. |
| Un cambio en entrada o salida | `gimnasio/visitas/rutas.py:12` → `gimnasio/visitas/servicio.py:41` → `gimnasio/visitas/repositorio.py:72`. |
| Un campo persistido | Nueva migración hacia adelante, servicio/repositorio del módulo y pruebas; conservar los hechos existentes. |
| Una acción de entrenamiento | `gimnasio/entrenamiento/rutas.py:36`, `gimnasio/static/js/entrenamiento.js:213` y pantalla correspondiente. |
| Un cambio visual | Tokens y estilos compartidos en `gimnasio/static/estilos/`, manteniendo la dirección B. |

## Límites y referencia histórica

La doble progresión y los frenos 1, 3 y 4 están implementados; el freno 2, la lectura de avisos al entrenador, el módulo de salud y un CRUD completo de socios en la interfaz siguen pendientes. La instalación PWA y el cierre de etapa requieren la validación reservada al dueño en #52. La caché del SW contiene estáticos públicos y no API ni HTML; sin conexión no se envían escrituras.

La etiqueta `base-original`, el archivo raíz `base_datos.sql`, la migración heredada de tres dígitos y la carpeta raíz `static/` conservan la referencia académica original. No se usan para ejecutar la aplicación vigente y no hay migración de esos datos.
