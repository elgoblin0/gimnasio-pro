# 0006. Controlar el acceso por rol y el tratamiento de salud por consentimiento

- Estado: provisional (el punto marcado se revisa en el cierre de la etapa 0)
- Fecha: 2026-10-26
- Decide: Opus

## Contexto
Hay cuatro tipos de usuario con necesidades distintas, y los datos de salud son sensibles según la Ley 7593/2025 (ADR 0010). La demo pública necesita "entrar como…" sin contraseñas.

## Decisión
- Roles: `socio`, `recepcion`, `entrenador` y `administracion`; un rol por usuario.
- La matriz de permisos vive en `gimnasio/permisos/matriz.py`, con una prueba por celda. Las rutas declaran `@requiere("permiso")`; no hay comprobaciones sueltas de rol.
- Alcance de los datos:
  - el socio ve solo lo suyo;
  - el entrenador ve solo a sus socios asignados;
  - recepción ve la tarjeta contextual, sin el detalle de salud;
  - administración configura, pero no ve el detalle de salud.
- La sesión usa la cookie firmada de Flask:
  - con `HttpOnly`, `SameSite=Lax` y `Secure` en producción (las pruebas y el e2e corren sobre `http://localhost`, donde el cliente de pruebas no envía cookies `Secure`);
  - las contraseñas se guardan con `werkzeug.security` (scrypt);
  - las rutas que cambian algo exigen el encabezado `X-Gimnasio: 1`, como defensa CSRF junto con `SameSite`;
  - los intentos de inicio de sesión se limitan por IP y por usuario.
- "Entrar como…" existe solo con `MODO_DEMO=1` y solo para usuarios marcados `es_demo`; lo prueba el CI.
- Los consentimientos se registran en `consentimientos(socio_id, tipo, version_texto, otorgado, registrado_por, registrado_en)`, que solo admite inserciones (ADR 0003). Otorgar y revocar agregan un registro, y vale el último por socio y tipo.
- **Provisional:** sin consentimiento de salud no se guardan restricciones ni dolores. El socio recibe su programa sin subas automáticas, porque los frenos no tendrían datos.
- Rutas sensibles: `permisos/` y `salud/`.

## Consecuencias
Los permisos se pueden probar como tabla y la demo es segura por construcción. Un socio sin consentimiento de salud tiene una experiencia reducida, y se le explica por qué.

## Alternativas descartadas
- Flask-Login u otras extensiones: no hacen falta para una sesión simple.
- JWT: agrega complejidad sin beneficio en una app del mismo origen.
