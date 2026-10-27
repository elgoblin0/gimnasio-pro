# 0009. Publicar la demo en Render con MySQL en Aiven, ambos gratuitos

- Estado: provisional (requiere que el usuario cree las cuentas)
- Fecha: 2026-10-26
- Decide: Opus

## Contexto
La demo pública debe ser gratuita y tener Python, MySQL y HTTPS. Las condiciones se verificaron el 2026-10-26 en las páginas oficiales.

| Opción | Python | MySQL gratis | HTTPS | Límites relevantes |
|---|---|---|---|---|
| Render, servicio web gratuito | Sí | No: solo Postgres, que vence a los 30 días | Sí, certificado administrado | Se duerme tras 15 min sin tráfico y tarda ~1 min en despertar; 750 h/mes por espacio de trabajo |
| Aiven, MySQL gratuito | — | Sí, MySQL real | TLS | 1 GB de disco y 1 GB de RAM, un nodo, sin tarjeta; se apaga tras un período de inactividad, con aviso previo |
| PythonAnywhere, plan Beginner | Sí | No en la cuenta gratuita | Sí | 100 s de CPU por día en consolas y tareas, salida a internet restringida, sin tareas programadas |
| TiDB Cloud Starter | — | Compatible con MySQL, pero no es MySQL | TLS | 5 GiB y 50 M de unidades de solicitud por mes; rechaza conexiones al agotar la cuota |

## Decisión
- La app corre en el **servicio web gratuito de Render**, con `gunicorn` y HTTPS administrado.
- La base es **MySQL en el plan gratuito de Aiven**, con conexión TLS.
- Un workflow programado de GitHub Actions reinicia la demo cada día a las 04:00 de Asunción:
  - aplica las migraciones, borra los datos y carga la semilla;
  - de paso, mantiene activa la base de Aiven.
- Las credenciales viven solo en los secretos de Render y de GitHub (`DEMO_DB_URL`), nunca en el repo.
- El modo demo muestra siempre el aviso "datos ficticios, se reinician cada día".

## Consecuencias
- El primer acceso después de un rato sin uso tarda cerca de un minuto; el recorrido guiado lo disimula con una pantalla de carga.
- Las cuentas las crea el usuario: los agentes no crean cuentas. Hasta entonces, el issue de despliegue queda `bloqueado`.

## Alternativas descartadas
- PythonAnywhere: su cuenta gratuita no incluye MySQL.
- TiDB: compatible, pero no es MySQL. Queda como reemplazo si Aiven dejara de ser viable.
- Postgres gratuito de Render: no es MySQL y vence a los 30 días.

Fuentes: render.com/docs/free, aiven.io/free-mysql-database, pythonanywhere.com/pricing, docs.pingcap.com/tidbcloud/serverless-limitations.
