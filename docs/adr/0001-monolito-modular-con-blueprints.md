# 0001. Organizar el backend como monolito modular con blueprints de Flask

- Estado: aceptado
- Fecha: 2026-10-26
- Decide: Opus

## Contexto
El `app.py` heredado concentra rutas, SQL y reglas en un archivo. Pro suma muchas capacidades que trabajarán agentes en paralelo; necesitan límites claros para no pisarse. Es una demo de una sola sede: microservicios no aportan nada.

## Decisión
- Un paquete `gimnasio/` con una fábrica `crear_app(config)`.
- Un subpaquete por módulo de dominio (`socios`, `visitas`, `entrenamiento`, `programas`, `clases`, `pagos`, `salud`, `permisos`, `sincronizacion`, `demo`), cada uno con:
  - `rutas.py`: blueprint; solo valida la entrada, llama al servicio y arma la respuesta;
  - `servicio.py`: casos de uso y transacciones;
  - `repositorio.py`: SQL parametrizado del módulo.
- `gimnasio/reglas/`: motor de reglas puro (ADR 0002).
- `gimnasio/comun/`: reloj, identificadores, base de datos, formatos y errores.
- Reglas de dependencia:
  1. `reglas/` solo importa la biblioteca estándar y `gimnasio.comun.tipos`.
  2. `comun/` no importa ningún módulo de dominio.
  3. Un módulo no importa el `repositorio` de otro; colabora a través de su `servicio`.
  4. `rutas.py` no ejecuta SQL.
- Las reglas se verifican con `pruebas/test_dependencias.py`, que analiza los `import` con `ast`, sin dependencias extra.
- El `app.py` heredado se conserva hasta la etapa 1, que lo reemplaza y actualiza `INDICADORES.md`.

## Consecuencias
Cada issue toca, por lo general, un solo módulo, y el despachador puede mantener un issue activo por módulo. Hay más archivos que en el original, a cambio de límites comprobables.

## Alternativas descartadas
- Mantener un solo `app.py`: no escala con agentes en paralelo.
- Servicios separados: costo operativo sin beneficio en una sede y en hosting gratuito.
