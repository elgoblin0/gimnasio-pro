# 0005. Inyectar el reloj, guardar en UTC y calcular en la zona de la sede

- Estado: aceptado
- Fecha: 2026-10-26
- Decide: Opus

## Contexto
Las semanas de entrenamiento, los vencimientos, los mejores horarios y la demo que se reinicia dependen del tiempo, y las pruebas necesitan fijarlo. Paraguay usa UTC−3 permanente desde octubre de 2024 (Ley 7115/2024).

## Decisión
- `gimnasio/comun/reloj.py` define `Reloj`, cuyo método `ahora()` devuelve un `datetime` aware en UTC, y dos implementaciones:
  - `RelojSistema`: el reloj real;
  - `RelojFijo`: se puede mover; se usa en pruebas y en el modo demo.
- La app recibe el reloj en `crear_app` y lo guarda en `app.extensions["reloj"]`. Los servicios lo obtienen con `reloj_actual()`. El motor de reglas recibe la fecha por parámetro.
- Queda prohibido llamar a `datetime.now()`, `datetime.utcnow()`, `date.today()` o `time.time()` fuera de `reloj.py`; lo verifica una prueba del CI. En JS, el reloj llega por el módulo `reloj.js`.
- MySQL guarda `DATETIME(6)` en UTC; la conexión fija `time_zone = '+00:00'`.
- La zona de la sede es `America/Asuncion` y sale de la configuración de la sede. Se convierte solo para mostrar y para calcular el día y la semana (lunes a domingo).
- Se instala el paquete `tzdata` para que `zoneinfo` funcione igual en Windows.

## Consecuencias
Las pruebas son deterministas y la demo puede simular "una semana después". A cambio, hay que pasar el reloj explícitamente.

## Alternativas descartadas
- Guardar la hora local: se rompe ante cambios de huso como el de 2024.
- Parchear `datetime` en las pruebas: es frágil y oculta dependencias.
