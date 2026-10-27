# 0010. Diseñar según la Ley 7593/2025 de protección de datos personales

- Estado: aceptado (verificar la reglamentación en cada cierre de etapa)
- Fecha: 2026-10-26
- Decide: Opus

## Contexto
- **Ley N.º 7593/2025**, "De Protección de Datos Personales en la República del Paraguay", promulgada el 27 de noviembre de 2025.
- Entra en vigor 24 meses después de su publicación, hacia noviembre de 2027.
- Crea la Agencia Nacional de Protección de Datos Personales dentro del MITIC.
- Al 2026-10-26 la reglamentación sigue pendiente.

Fuentes: el texto de la ley en bacn.gov.py (Leyes paraguayas, Ley 7593/2025) y análisis de estudios jurídicos locales. Este ADR no es asesoramiento legal.

## Decisión
La demo se diseña como si la ley ya rigiera:
- Los datos de salud son sensibles: requieren consentimiento expreso, versionado y revocable (ADR 0006), y su acceso es mínimo.
- Cada formulario que pide datos personales declara su finalidad.
- El socio puede ver y descargar sus datos y revocar sus consentimientos.
- La revocación detiene el tratamiento. Los datos de salud se borran por anonimización, para no romper el historial (ADR 0003).
- En la demo no hay datos reales: la semilla es ficticia y un aviso lo indica.
- Se registra quién accede a la ficha de salud (auditoría de lectura).

## Consecuencias
La ficha y los consentimientos (etapa 5) llevan más trabajo, a cambio de un diseño defendible. Cuando salga la reglamentación, un ADR nuevo ajusta los detalles.

## Alternativas descartadas
- Ignorar la ley hasta que entre en vigor: los datos de salud lo desaconsejan y el portfolio pierde valor.
