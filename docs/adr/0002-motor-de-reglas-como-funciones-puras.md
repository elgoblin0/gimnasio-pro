# 0002. Escribir el motor de reglas como funciones puras

- Estado: aceptado
- Fecha: 2026-10-26
- Decide: Opus

## Contexto
Las propuestas de sesión, los ajustes de carga, los frenos, la bandeja del entrenador y el riesgo de abandono dependen de reglas. Sin IA en el producto, las explicaciones también salen de ahí. Deben ser deterministas, probables y auditables.

## Decisión
- `gimnasio/reglas/` contiene funciones puras: reciben `dataclass(frozen=True)` y devuelven resultados inmutables. Sin SQL, sin red, sin leer el reloj: la fecha llega como parámetro.
- Toda decisión devuelve también su **explicación**: una lista de `Razon(regla, version, datos)` legible para el socio.
- `VERSION_REGLAS` se guarda junto a cada propuesta y ajuste persistido.
- Los **frenos de seguridad** se aplican en una función final, `aplicar_frenos()`, que ninguna otra regla puede saltar. Cada freno tiene pruebas propias.
- Pruebas por tabla de casos en `pruebas/reglas/`; la cobertura de `reglas/` se exige en el CI desde que exista código.
- Ruta sensible: todo cambio en `reglas/` lo revisa Opus.

## Consecuencias
El motor se prueba sin base de datos y sin Flask. Los servicios cargan datos, llaman al motor y persisten el resultado. Cambiar una regla obliga a subir la versión.

## Alternativas descartadas
- Reglas en SQL o en las rutas: no se pueden probar aisladas.
- Un motor de reglas genérico de terceros: agrega una dependencia y un lenguaje nuevo sin necesidad.
