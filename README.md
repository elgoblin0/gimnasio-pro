# Gimnasio Pro

Demo y portfolio de un gimnasio de una sola sede en Paraguay, hecho con Flask, MySQL 8 y JavaScript moderno sin framework ni paso de build. Gestiona el entrenamiento personalizado y la operación diaria con una experiencia visual cuidada: cuaderno de entrenamiento (dirección B), cuerpo 3D muscular y escena de ocupación.

**Pro está terminado.** Las ocho etapas del [ROADMAP](ROADMAP.md) se cerraron con la aprobación del dueño, la última en #297. Lo que quedó afuera está en [ideas no hechas](docs/IDEAS-NO-HECHAS.md).

## Qué hace

- **Socio:** chequeo del día, sesión propuesta con su explicación, registro de series con descansos y carga anterior, «me duele» y «máquina ocupada» con alternativa, récords, progreso y cuerpo 3D, reservas de clases, pagos, ficha, consentimientos y resumen semanal.
- **Recepción:** entrada y salida con tarjeta contextual, aforo en vivo, mejores horarios, escena de ocupación, clases y reservas con lista de espera, y registro de pagos en guaraníes.
- **Entrenador:** bandeja priorizada (ajustes frenados, socios nuevos, riesgo de abandono), programas desde plantillas, equipos y alternativas, y revisión de la ficha de salud con consentimiento.
- **Administración:** sede y aforo, usuarios, tipos de membresía, clases y plantillas.

Las propuestas salen de un motor de reglas determinista y versionado (`gimnasio/reglas/`), con frenos de seguridad que no se pueden desactivar. El historial solo agrega registros. La app se instala como PWA, se adapta a celular y tiene un **modo sin efectos** con la misma información, sin escenas 3D ni animaciones decorativas.

## Demo pública

[elgoblin0.github.io/gimnasio-pro](https://elgoblin0.github.io/gimnasio-pro/): Render + Aiven, con datos ficticios que se reinician cada día. El botón **Ver recorrido** de la portada abre el **recorrido guiado**: unos dos minutos sobre la app real, pasando por los cuatro roles (ADR 0032). También se puede entrar directamente con «Entrar como…». El primer acceso después de un rato sin uso tarda cerca de un minuto, porque el servicio gratuito se duerme: esa portada lo despierta y abre la app sola. [Configuración y verificación](docs/demo-publica.md).

## Referencias

- [VISION.md](VISION.md), [GLOSSARY.md](GLOSSARY.md) y [ADR](docs/adr/): meta, términos y decisiones.
- [Mapa de capacidades](docs/MAPA-CAPACIDADES.md): el nivel de cada capacidad y la prueba que lo acredita.
- [INDICADORES.md](INDICADORES.md): evidencias académicas del código vigente.
- [Protocolo de agentes](docs/protocolo-agentes.md): cómo se construyó, con Opus planificando y Codex implementando.
- [Versión estándar](https://github.com/elgoblin0/gimnasio): proyecto independiente. No comparte base con Pro.

## Preparar un entorno local

Requiere Python 3.13 o posterior, MySQL 8 y Git. Node 24 y Chromium se usan para las pruebas. Ejecutar desde la raíz del repositorio:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

En Linux usar `.venv/bin/python`. Crear una base **vacía y exclusiva** para esta aplicación, con juego de caracteres `utf8mb4`. Configurar las variables en la terminal (los valores deben pertenecer al entorno local; no guardarlos en Git):

| Variable | Significado |
|---|---|
| `GIMNASIO_BD_HOST` | Servidor MySQL |
| `GIMNASIO_BD_PUERTO` | Puerto, por defecto 3306 |
| `GIMNASIO_BD_USUARIO` | Usuario con acceso a la base |
| `GIMNASIO_BD_CLAVE` | Clave del usuario |
| `GIMNASIO_BD_NOMBRE` | Nombre de la base exclusiva |
| `GIMNASIO_BD_CA` | Ruta del certificado CA cuando se requiere TLS |

Aplicar únicamente las migraciones versionadas vigentes:

```powershell
.venv/Scripts/python -m gimnasio.comun.migrar
```

Para una demo **local con datos descartables**, activar el modo demo y cargar la semilla ficticia. El comando vacía los datos de la base configurada; conserva el registro de migraciones. No usarlo sobre datos que se quieran conservar.

```powershell
$env:MODO_DEMO = "1"
.venv/Scripts/python -m gimnasio.demo.semilla --reiniciar
```

La semilla ofrece accesos por rol en la pantalla inicial y el recorrido guiado. Trae socios en distintas situaciones (recorrido sin empezar, entrenamiento parcial, membresía vencida, primeros 90 días, riesgo de abandono), un catálogo con equipos y alternativas, una semana de clases, pagos, fichas de salud y visitas simuladas.

## Arrancar

```powershell
.venv/Scripts/python -m flask --app wsgi run --port 5002
```

Abrir `http://localhost:5002`. También funciona `.venv/Scripts/python app.py`: ambos usan `gimnasio.crear_app`, la misma API y `gimnasio/static/`. Detener con `Ctrl+C`.

Render conserva su comando actual: primero `python -m gimnasio.comun.migrar` y luego `gunicorn wsgi:app` con un proceso y cuatro hilos. En producción se exige `GIMNASIO_CLAVE_SECRETA`; los secretos y el certificado se configuran fuera del repositorio.

## Estructura vigente

```text
gimnasio/
  __init__.py            crear_app y registro de blueprints
  comun/                 base de datos, reloj, UUIDv7, errores, idempotencia y migraciones
  reglas/                motor puro: propuesta, progresión, frenos, aforo, acompañamiento
  permisos/              sesión, roles, usuarios y matriz de permisos
  visitas/               entradas, salidas, aforo, tarjeta contextual y mejores horarios
  entrenamiento/         propuesta, sesiones, series, chequeo, dolores y progreso
  programas/             plantillas, programas, equipos y alternativas
  entrenador/            bandeja, socios asignados y revisión de avisos
  clases/                agenda, reservas, lista de espera y avisos al socio
  pagos/                 pagos en guaraníes y tipos de membresía
  socios/                alta, ficha y perfil de entrenamiento
  salud/                 ficha de salud, restricciones y consentimientos
  acompanamiento/        incorporación de 90 días y resumen semanal
  administracion/        sede y aforo
  sistema/               estado del servicio
  demo/                  semilla ficticia y límites de la demo
  static/                páginas HTML, JS, estilos, vendor y service worker
migraciones/             NNNN_descripcion.sql, hacia adelante
pruebas/                 pytest y e2e Playwright
scripts/                 mapa de capacidades, verificaciones del CI y de la demo
wsgi.py                  entrada de producción y Flask CLI
app.py                   entrada local mínima
```

Cada módulo sigue `rutas.py → servicio.py → repositorio.py`. Las reglas de dependencia del ADR 0001 las hace cumplir `pruebas/test_dependencias.py`.

## API

Toda la API vive bajo `/api`, agrupada por módulo: `/api/sesion`, `/api/yo/…` (lo del propio socio), `/api/entradas`, `/api/salidas`, `/api/ocupacion`, `/api/entrenamiento/…`, `/api/entrenador/…`, `/api/clases/…`, `/api/pagos`, `/api/socios/…`, `/api/programas/…`, `/api/administracion/…` y `/api/estado`. Cada ruta declara su permiso en `gimnasio/permisos/matriz.py`.

Las escrituras de dominio exigen sesión autorizada, `X-Gimnasio: 1`, identificadores UUIDv7 y `Idempotency-Key`. Los hechos se conservan: las correcciones agregan registros. La API no se guarda en la caché del service worker; se requiere conexión.

## Verificar

```powershell
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m pytest
node --test "gimnasio/static/**/*.test.js"
.venv/Scripts/python scripts/mapa_capacidades.py --verificar
```

Para E2E instalar Chromium con `.venv/Scripts/python -m playwright install chromium`. Las pruebas MySQL requieren las variables de conexión y permiso para crear bases aisladas. Si faltan se omiten: no equivalen a una verificación del recorrido. El CI requerido ejecuta MySQL, migraciones sobre base vacía, Chromium, calidad y secretos.

## Referencia heredada

La etiqueta `base-original` conserva el punto de partida académico. `base_datos.sql`, `migraciones/001_dni_a_ci.sql` y la carpeta raíz `static/` pertenecen a ese esquema heredado; se conservan como referencia histórica. No se importan para arrancar Pro ni se sirven desde el punto de entrada vigente. El aplicador solo acepta nombres de cuatro dígitos. No hay traslado automático de datos desde el esquema heredado ni desde la versión estándar.

## Problemas frecuentes

- Conexión rechazada: comprobar que MySQL 8 esté iniciado y revisar `GIMNASIO_BD_*`.
- Base inexistente: crear la base vacía indicada por `GIMNASIO_BD_NOMBRE` y aplicar migraciones.
- Acceso denegado: revisar el usuario y sus permisos; configurar la clave en el entorno.
- No aparecen accesos demo: comprobar `MODO_DEMO=1` y cargar la semilla solo en la base ficticia elegida.
- Respuesta 429: esperar el plazo `Retry-After`; la demo admite 240 solicitudes por IP por minuto, sin contar los archivos.
