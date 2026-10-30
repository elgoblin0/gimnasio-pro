# Gimnasio Pro

Aplicación Flask modular con MySQL 8 y PWA sin build, en español y con dirección visual B. El recorrido de etapa 1 permite a recepción registrar entradas y salidas, consultar visitas abiertas y ocupación; el socio recibe la primera sesión planificada pendiente y registra sus series. Se respeta el programa del entrenador sin ajustes automáticos ni reinicio semanal.

La membresía se verifica por vigencia, sin cupo de entradas. El aforo cuenta socios con visita abierta; una entrada que lo excede responde 409. Cerrar la sesión de usuario no registra una salida.

## Estado y referencias

Los recorridos integrados se prueban con MySQL y Chromium aislados en escritorio y celular. Los niveles de cada capacidad están en [el mapa](docs/MAPA-CAPACIDADES.md); los ajustes automáticos y la sesión en vivo completa pertenecen a etapa 2. La validación y el cierre del dueño corresponden a #52.

- [VISION.md](VISION.md), [GLOSSARY.md](GLOSSARY.md) y [ADR](docs/adr/): alcance, términos y decisiones.
- [INDICADORES.md](INDICADORES.md): evidencias académicas del código vigente.
- [Demo pública](https://gimnasio-pro-demo.onrender.com): Render + Aiven, datos ficticios y reinicio diario. [Configuración y verificación](docs/demo-publica.md).
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

La semilla ofrece accesos por rol en la pantalla inicial. El socio principal tiene un programa, membresía vigente y ninguna visita ni serie realizada. Otro socio tiene entrenamiento parcial y hay una membresía vencida para verificar el rechazo de entrada.

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
  comun/                 base de datos, reloj, UUIDv7, errores e idempotencia
  permisos/              sesión de usuario y autorización
  visitas/               rutas → servicio → repositorio
  entrenamiento/         propuesta y registro de sesiones y series
  programas/             programas versionados del entrenador
  reglas/                motor puro, sin SQL ni reloj
  demo/                  semilla ficticia y límites
  static/                HTML, JS, estilos, vendor y service worker
migraciones/             NNNN_descripcion.sql, hacia adelante
pruebas/                 pytest y e2e Playwright
wsgi.py                  entrada de producción y Flask CLI
app.py                   entrada local mínima
```

## API del recorrido

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/estado` | Estado del servicio |
| GET, POST, DELETE | `/api/sesion` | Consultar, iniciar o cerrar sesión de usuario |
| PUT | `/api/sesion/figura-cuerpo` | Cada usuario elige la figura de su cuerpo 3D |
| POST | `/api/entradas`, `/api/salidas` | Recepción registra hechos |
| GET | `/api/visitas?abiertas=1`, `/api/ocupacion`, `/api/visitas/socios` | Recepción consulta visitas, aforo y socios |
| GET | `/api/entrenamiento/propuesta` | Propuesta del propio socio |
| GET | `/api/entrenamiento/socios/<id>/propuesta` | Propuesta de socio asignado al entrenador |
| POST | `/api/entrenamiento/sesiones` | Iniciar sesión realizada |
| POST | `/api/entrenamiento/sesiones/<id>/series` | Registrar serie realizada |
| GET | `/api/entrenamiento/sesiones/<id>` | Recuperar registro propio |

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
- Respuesta 429: esperar el plazo `Retry-After`; la demo admite 240 solicitudes por IP por minuto, incluidos los estáticos.
