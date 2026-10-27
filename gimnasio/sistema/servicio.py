"""Estado del servicio. Es el módulo de ejemplo del patrón rutas → servicio (→ repositorio)."""


def estado_del_servicio(config):
    return {
        "estado": "ok",
        # El motor de reglas publica su versión cuando exista (ADR 0002).
        "version_reglas": None,
        "modo_demo": bool(config.get("MODO_DEMO")),
    }
