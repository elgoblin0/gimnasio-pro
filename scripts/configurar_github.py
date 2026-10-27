"""Crea o actualiza las etiquetas y los milestones del protocolo de docs/protocolo-agentes.md. Es idempotente.

Uso: python scripts/configurar_github.py
"""

import json
import subprocess

REPO = "elgoblin0/gimnasio-pro"

ETIQUETAS = {
    "estado:listo": ("0e8a16", "Especificado y disponible"),
    "estado:en-curso": ("fbca04", "Un agente lo tiene"),
    "estado:revision": ("1d76db", "PR abierto: CI y revisión cruzada"),
    "ejecutor:opus": ("5319e7", "Lo hace Opus: decisiones, patrones, rutas sensibles"),
    "ejecutor:codex": ("0052cc", "Lo hace Codex: trabajo especificado"),
    "agente:opus": ("d4c5f9", "Candado: Opus trabajando"),
    "agente:codex": ("c5def5", "Candado: Codex trabajando"),
    "correccion-pendiente": ("e99695", "El CI o la revisión pidió cambios"),
    "revisado:codex": ("bfdadc", "PR aprobado por la revisión de Codex"),
    "revisado:opus": ("bfdadc", "PR aprobado por la revisión de Opus"),
    "necesita-criterio": ("d93f0b", "Ambigüedad de producto: decide Opus"),
    "bloqueado": ("b60205", "Depende de algo externo o agotó intentos"),
    "tipo:patron": ("5319e7", "Primera instancia de un patrón: siempre Opus"),
    "tipo:funcion": ("a2eeef", "Capacidad nueva"),
    "tipo:error": ("d73a4a", "Algo no funciona"),
    "tipo:mantenimiento": ("cfd3d7", "Infraestructura, CI, dependencias"),
    "tipo:docs": ("0075ca", "Documentación"),
    "tipo:prototipo": ("f9d0c4", "Exploración descartable"),
    "tipo:cierre": ("000000", "Cierre de etapa"),
}
MODULOS = [
    "comun",
    "formatos",
    "reglas",
    "migraciones",
    "permisos",
    "salud",
    "sincronizacion",
    "socios",
    "visitas",
    "entrenamiento",
    "programas",
    "clases",
    "pagos",
    "demo",
    "frontend",
    "diseno",
    "e2e",
    "infra",
]
ETAPAS = [
    "Fundaciones",
    "Esqueleto andante",
    "Socio + cuerpo 3D",
    "Recepción + escena de ocupación",
    "Entrenador",
    "Operación",
    "Acompañamiento",
    "Pulido y recorrido guiado",
]


def gh(*argumentos):
    return subprocess.run(["gh", *argumentos], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def main():
    for modulo in MODULOS:
        ETIQUETAS[f"modulo:{modulo}"] = ("ededed", f"Módulo {modulo}")
    for nombre, (color, descripcion) in ETIQUETAS.items():
        gh("label", "create", nombre, "--repo", REPO, "--color", color, "--description", descripcion, "--force")
    existentes = {m["title"] for m in json.loads(gh("api", f"repos/{REPO}/milestones?state=all&per_page=100"))}
    for numero, nombre in enumerate(ETAPAS):
        titulo = f"Etapa {numero}: {nombre}"
        if titulo not in existentes:
            gh("api", f"repos/{REPO}/milestones", "-f", f"title={titulo}")
    print(f"{len(ETIQUETAS)} etiquetas y {len(ETAPAS)} milestones al día en {REPO}")


if __name__ == "__main__":
    main()
