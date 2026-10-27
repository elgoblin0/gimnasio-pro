# PWA en escritorio

Gimnasio Pro requiere conexión a Internet, también después de instalarla. El manifest
usa la paleta B. Los iconos PNG locales incluyen una variante `maskable` opaca, con
las iniciales dentro de la zona segura central.

El SW se sirve en `/sw.js` con alcance `/`. Solo guarda en Cache Storage los recursos
públicos de `RECURSOS_ESTATICOS`, bajo `gimnasio-estaticos-<VERSION>`. HTML, `/api/*`,
solicitudes con parámetros y toda escritura van a red, sin caché HTTP. No hay
IndexedDB, cola ni reenvío al recuperar la conexión. Si falla una navegación, responde
503 con un mensaje de conexión requerida; no sirve una pantalla de usuario guardada.

Una actualización muestra un aviso y espera a que se cierren todas las ventanas de
la app. No fuerza recargas ni descarta el formulario en curso. Al activarse elimina
las cachés anteriores de Gimnasio Pro.

## Incorporar pantallas

Cada issue de pantalla debe enlazar `/manifest.webmanifest`, registrar el SW mediante
`js/comun/pwa.js` e incluir el aviso `[data-actualizacion]` y el estado `[data-estado-pwa]`.
Debe agregar sus estáticos públicos a `RECURSOS_ESTATICOS` y cambiar `VERSION`, también
cuando modifica el contenido de un recurso ya listado. No se incluyen HTML, API,
datos de usuario, pruebas ni documentación. El e2e comprueba la lista de archivos
de ejecución existentes; el cierre debe revisar que siga completa.

## Evidencia pendiente del cierre

La instalación y la ventana independiente en Windows requieren validación del dueño.
No están validadas por este issue ni por las pruebas automatizadas. Registrar en el
issue de cierre fecha, versión de Windows, navegador y versión, URL y resultado:

- Instalar desde Edge o Chrome con conexión y abrir desde el acceso instalado.
- Comprobar que abre en una ventana independiente y permite el recorrido existente.
- Cortar la conexión: mostrar el mensaje correspondiente y comprobar que ninguna
  escritura se confirma ni se reenvía al recuperarla.
- Recibir una actualización con un formulario en curso, conservar lo escrito y
  comprobar que se aplica al cerrar todas las ventanas y abrir de nuevo.

La capacidad permanece en `pendiente` hasta ejecutar sus pruebas de aceptación;
`validada` exige la evidencia del dueño en el cierre.
