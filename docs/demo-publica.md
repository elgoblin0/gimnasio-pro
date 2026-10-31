# Demo pública en Render y Aiven

La configuración del issue #10 está preparada para el ADR 0009. El usuario crea las cuentas,
carga los secretos y verifica el despliegue real; los agentes no crean cuentas.

## Base de la demo

Crear una base MySQL gratuita en Aiven, dedicada exclusivamente a datos ficticios. El reinicio
borra los datos de esa base y vuelve a cargar la semilla; conserva `migraciones_aplicadas`.
Descargar el certificado CA de Aiven. No subir credenciales ni certificados al repositorio.

Se usan las variables existentes `GIMNASIO_BD_*`, como fija el ADR 0009. No se usa `DEMO_DB_URL`.

| Nombre | GitHub Actions: secretos del repositorio | Render |
|---|---|---|
| `GIMNASIO_BD_HOST` | Host de Aiven | Variable de entorno |
| `GIMNASIO_BD_PUERTO` | Puerto de Aiven | Variable de entorno |
| `GIMNASIO_BD_USUARIO` | Usuario de Aiven | Variable de entorno |
| `GIMNASIO_BD_CLAVE` | Clave de Aiven | Variable de entorno |
| `GIMNASIO_BD_NOMBRE` | Nombre de la base de la demo | Variable de entorno |
| `GIMNASIO_BD_CA_PEM` | Contenido completo del certificado CA | No se usa como variable |
| `GIMNASIO_BD_CA` | El workflow exporta la ruta temporal | `/etc/secrets/aiven-ca.pem` |

## Render

1. Crear un Blueprint desde este repositorio y su `render.yaml`.
2. Cargar las variables solicitadas, sin guardar valores en el YAML.
3. Agregar el certificado como **Secret File**, con nombre `aiven-ca.pem`.
4. Verificar que `GIMNASIO_BD_CA` tenga el valor `/etc/secrets/aiven-ca.pem` y desplegar.

El servicio usa Python 3.13, `plan: free`, `MODO_DEMO=1` y `GIMNASIO_ENTORNO=produccion`.
Render genera `GIMNASIO_CLAVE_SECRETA` para las sesiones. La instalación usa
`pip install -r requirements.txt`. El arranque aplica las migraciones y, solo si terminan bien,
ejecuta `gunicorn wsgi:app`, escuchando en `0.0.0.0:$PORT`.
Las migraciones van en el arranque porque
[`preDeployCommand` requiere un servicio pago](https://render.com/docs/deploys#pre-deploy-command).
Así el certificado se lee desde el archivo secreto del servicio.

El servicio corre en Virginia porque la base está en DigitalOcean `nyc`. En Oregón, la bandeja del
entrenador tardaba unos 10 s con 100 consultas; en local, una fracción de segundo. Si la base cambia
de región, hay que acercar también el servicio. Render fija la región al crear el servicio: para
cambiarla hay que crearlo de nuevo con los pasos de arriba. La base y sus datos no se tocan.

## Reinicio diario

`.github/workflows/reiniciar-demo.yml` corre cada día a las 07:00 UTC (04:00 en Asunción).
También permite **Run workflow** para cargar la semilla inicial o repetir el reinicio.
Debe estar disponible en la rama predeterminada de GitHub para ejecutar el cron.

El workflow verifica que estén los seis secretos, escribe el certificado en un archivo temporal
con permisos restringidos, exporta `GIMNASIO_BD_CA`, aplica las migraciones y ejecuta
`python -m gimnasio.demo.semilla --reiniciar`. Elimina el archivo incluso si falla un paso.
No reinicia si las migraciones fallan. Las ejecuciones del workflow no se superponen.

## Límites de uso

Solo en modo demo:

- 240 solicitudes por IP en una ventana móvil de un minuto, incluyendo archivos y rutas inexistentes.
  Al superar el límite responde 429 con `Retry-After`.
- Cuerpo máximo de 1 MB (1.000.000 bytes). Al superar el límite responde 413, incluso en rutas
  que no leen el cuerpo y en transferencias sin `Content-Length` con fin de flujo indicado por WSGI.

El contador vive en memoria y descarta las IP inactivas al pasar un minuto. Gunicorn usa un solo
proceso y cuatro hilos para compartir el contador; reiniciar el proceso reinicia los contadores.
No aumentar los procesos o las instancias sin implementar primero un contador compartido.

En Render (`RENDER=true`) se usa `CF-Connecting-IP`, validada y normalizada, para identificar
la IP del cliente. Esta elección se basa en que
[Render recibe el tráfico público a través de Cloudflare](https://render.com/articles/how-render-handles-ddos-attacks)
y [Cloudflare recomienda ese encabezado para obtener la IP](https://developers.cloudflare.com/fundamentals/reference/http-headers/#cf-connecting-ip).
Fuera de Render, o si falta un valor válido, se usa la dirección de la conexión.
`X-Forwarded-For` no cambia el contador, porque puede contener valores enviados por el cliente.

## Verificación del usuario

`python scripts/verificar_demo.py <URL de Render>` comprueba los pasos 2, 4 (el 429 con `Retry-After`)
y 5. Los demás pasos son manuales.

1. Ejecutar **Reiniciar demo** manualmente y comprobar que migraciones y semilla terminan bien.
2. Abrir la URL HTTPS de Render y `/api/estado`; debe responder `modo_demo: true`.
3. Comprobar el aviso de datos ficticios y los accesos rápidos por rol.
4. Verificar desde dos IP distintas que cada una tiene su cupo, incluso si se envía un
   `X-Forwarded-For` arbitrario. Comprobar 429 después de 240 solicitudes en menos de un minuto,
   esperar el plazo de `Retry-After` y volver a entrar.
5. Enviar un cuerpo de más de 1.000.000 bytes desde una IP con cupo y comprobar 413.
6. Confirmar al día siguiente la ejecución programada y la restauración de la semilla ficticia.

La URL pública, la conexión TLS real y la ejecución programada quedan pendientes de esta
verificación con las cuentas y secretos del usuario.
