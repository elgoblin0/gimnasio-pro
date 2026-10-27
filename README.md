# Sistema de gimnasio Pro

Proyecto de la facultad: gestión de socios de un gimnasio. Permite dar de alta socios, registrar sus entradas (check-in), renovar planes y seguir su peso, IMC y rutina.

**Stack:** XAMPP (MySQL/MariaDB) + Python Flask (backend) + JavaScript (frontend).

**Meta visual de Pro:** convertirse en una demo cutting edge, con impacto «wow» inmediato, que explore el techo visual e interactivo de la tecnología disponible. La próxima entrega será un prototipo visual de alta ambición; la interfaz actual todavía corresponde a la base original. La dirección y los criterios de calidad están en `ROADMAP.md`.

## Dos versiones del proyecto

- **Estándar:** https://github.com/elgoblin0/gimnasio — mantiene Flask, MySQL y JavaScript, con mejoras pequeñas y explicables.
- **Pro:** https://github.com/elgoblin0/gimnasio-pro — desarrollo independiente para explorar una experiencia de producto completa.
- La etiqueta `base-original` conserva el punto de partida compartido.
- Cada repositorio tiene su propia rama `main`. No se sincronizan automáticamente: los arreglos compartidos se trasladan de forma selectiva.
- Ver `ROADMAP.md` para el alcance y las próximas etapas de esta versión.

## Estado de esta versión

Esta es la base inicial de Pro: conserva las funciones y el stack originales. Las funciones avanzadas del roadmap todavía no están implementadas. Su desarrollo es independiente del proyecto académico.

## Ejecutar ambas versiones

La preparación y verificación de la demo pública en Render y Aiven está en
[docs/demo-publica.md](docs/demo-publica.md).

La estándar utiliza la base `gimnasio` y el puerto 5001. Pro utiliza la base `gimnasio_pro` y el puerto 5002. Cada repositorio incluye su propio SQL: importar el de Pro solo reinicia `gimnasio_pro`.

No compartir una misma base entre ambas versiones. Las futuras migraciones de Pro pertenecen exclusivamente a su base.


## Qué hace falta instalar

- [XAMPP](https://www.apachefriends.org/es/index.html): trae MySQL y phpMyAdmin.
- [Python 3](https://www.python.org/downloads/). En Windows, marcar **"Add Python to PATH"** al instalarlo.
- [Git](https://git-scm.com/downloads).

## Cómo ponerlo en marcha

1. Descargar el proyecto (solo la primera vez):
   ```
   git clone https://github.com/elgoblin0/gimnasio-pro.git
   cd gimnasio-pro
   ```
2. Abrir el panel de XAMPP y arrancar **MySQL** y **Apache** (Apache solo hace falta para phpMyAdmin).
3. Abrir `http://localhost/phpmyadmin`, ir a la pestaña **Importar** y subir `base_datos.sql`.
   (Ojo: borra la base de datos `gimnasio_pro` y la vuelve a crear con los datos de ejemplo.)
4. Instalar las librerías de Python:
   ```
   pip3 install -r requirements.txt
   ```
5. Arrancar el servidor:
   ```
   python3 app.py
   ```
6. Abrir `http://localhost:5002` en el navegador.

> En Windows puede que los comandos sean `pip` y `python` en vez de `pip3` y `python3`.

Para parar el servidor: `Ctrl + C` en la terminal.

## Archivos

```
gimnasio/
├── base_datos.sql     ← tablas y datos de ejemplo
├── app.py             ← backend Flask: reglas + API
├── requirements.txt   ← librerías de Python
└── static/
    ├── index.html     ← lista de socios, check-in y alta
    ├── socio.html     ← ficha: IMC, rutina, progreso, renovar
    ├── app.js         ← llamadas a la API (fetch)
    └── estilos.css
```

## Base de datos

| Tabla | Qué guarda |
|---|---|
| `planes` | Nombre, duración en días y cuántos días por semana se puede entrar (7 = libre). |
| `rutinas` | Una rutina por cada combinación de objetivo + nivel. |
| `socios` | Datos del socio, su plan y la fecha de vencimiento. |
| `asistencias` | Una fila por cada entrada al gimnasio. |
| `registros_peso` | Historial de peso para ver el progreso. |

## Reglas del gimnasio (la lógica que se evalúa)

Todas están en `app.py`.

| # | Regla |
|---|---|
| 1 | Al dar de alta o renovar se calcula el vencimiento. Si sigue activo, se suma a lo que le queda; si no, desde hoy. |
| 2 | Estado del socio: Vencido / Por vencer (7 días o menos) / Activo. |
| 3 | Check-in: se rechaza si el plan está vencido, si ya entró hoy o si ya usó sus días por semana (últimos 7 días). |
| 4 | IMC = peso / altura², con su categoría. |
| 5 | Rutina asignada según objetivo + nivel. |
| 6 | Progreso: primer peso vs último según el objetivo (mantenerse = 2 kg o menos de diferencia). |

## Cómo probar las reglas con los datos de ejemplo

Las fechas de ejemplo se calculan a partir del día en que se importa el `.sql`, así que siempre hay un socio en cada estado.

| Socio | Qué se puede probar |
|---|---|
| Ana Lopez | Activa. El check-in funciona. Va bien bajando de peso (72 → 68 kg). |
| Carlos Ruiz | Por vencer (5 días). Plan de 3 días/semana y ya entró 2 veces: el primer check-in funciona, el segundo dice "Ya entró hoy". |
| Maria Gomez | Vencida. El check-in se rechaza. Al renovar, el plan cuenta desde hoy. |
| Luis Fernandez | Activo (plan anual). Quiere bajar peso pero subió (88 → 90 kg): "No va bien". |
| Diego Pereira | Activo. Quiere mantenerse y se movió 1 kg (80 → 81): "Va bien". IMC en Sobrepeso. |
| Lucia Rodriguez | Por vencer (2 días). Bajó de 95 a 91 kg: "Va bien". IMC en Obesidad. |
| Valentina Diaz | Vencida. Quiere mantenerse pero subió 4 kg (48 → 52): "No va bien". IMC en Bajo peso. |
| Javier Gomez | Plan de 3 días/semana y ya entró 3 veces en los últimos 7 días: el check-in dice "Ya usó sus 3 días de los últimos 7". |

Si los datos quedan desordenados de tanto probar, se vuelve a importar `base_datos.sql` y listo.

### Migraciones

Si ya tenías la base creada y no quieres perder los datos, en vez de reimportar `base_datos.sql` importa (en phpMyAdmin, pestaña **Importar**) el archivo de `migraciones/` que corresponda:

| Archivo | Qué hace |
|---|---|
| `migraciones/001_dni_a_ci.sql` | Renombra la columna `socios.dni` a `ci` conservando los datos. Se puede repetir sin problema. |

## API (lo que llama `app.js`)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/planes` | Lista de planes |
| GET | `/api/socios` | Lista de socios con su estado |
| POST | `/api/socios` | Alta de socio |
| GET | `/api/socios/<id>` | Ficha completa (IMC, rutina, progreso, historial) |
| PUT | `/api/socios/<id>` | Editar nombre, CI, teléfono, altura, objetivo y nivel |
| DELETE | `/api/socios/<id>` | Eliminar socio |
| POST | `/api/socios/<id>/checkin` | Registrar una entrada |
| POST | `/api/socios/<id>/renovar` | Renovar o cambiar de plan |
| POST | `/api/socios/<id>/peso` | Registrar un peso nuevo |

## Problemas frecuentes

- **`Can't connect to MySQL server`**: MySQL no está arrancado en XAMPP.
- **`Unknown database 'gimnasio_pro'`**: falta importar `base_datos.sql` en phpMyAdmin.
- **`Access denied for user 'root'`**: tu MySQL tiene contraseña. Ponla en `password=""` dentro de `conectar()` en `app.py`, pero **no la subas a GitHub**.
- **`ModuleNotFoundError: No module named 'flask'`**: falta el paso 4 (`pip3 install -r requirements.txt`).
- **`Address already in use`**: el servidor ya está abierto en otra terminal. Ciérralo con `Ctrl + C`.

## Comandos básicos de git

```
git pull                      # traer los cambios de los compañeros (¡siempre antes de empezar!)
git add .                     # preparar mis cambios
git commit -m "qué he hecho"  # guardarlos con un mensaje
git push                      # subirlos a GitHub
```

Si `git push` da error porque alguien subió cambios antes, haz `git pull` y vuelve a hacer `git push`.
