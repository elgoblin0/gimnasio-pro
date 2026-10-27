"""Los módulos públicos usados por las pantallas están en la lista versionada del SW."""

import json
import posixpath
import re
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "gimnasio" / "static"


class RecursosPagina(HTMLParser):
    def __init__(self, texto):
        super().__init__()
        self.recursos = set()
        self.importaciones = {}
        self.mapa = None
        self.feed(texto)

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        if tag == "script" and atributos.get("type") == "importmap":
            self.mapa = []
        ruta = atributos.get("src") if tag == "script" else atributos.get("href") if tag == "link" else None
        if ruta and ruta.startswith("/"):
            self.recursos.add(ruta)

    def handle_data(self, datos):
        if self.mapa is not None:
            self.mapa.append(datos)

    def handle_endtag(self, tag):
        if tag == "script" and self.mapa is not None:
            self.importaciones.update(json.loads("".join(self.mapa))["imports"])
            self.mapa = None


def recursos_de_pantalla(nombre):
    pagina = RecursosPagina((RAIZ / nombre).read_text(encoding="utf-8"))
    recursos = set(pagina.recursos)
    pendientes = [ruta for ruta in recursos if ruta.endswith(".js")]
    while pendientes:
        modulo = pendientes.pop()
        codigo = (RAIZ / modulo.lstrip("/")).read_text(encoding="utf-8")
        for dependencia in re.findall(r"(?:from\s+|import\s*)[\"']([^\"']+)[\"']", codigo):
            if dependencia.startswith("."):
                ruta = posixpath.normpath(posixpath.join(posixpath.dirname(modulo), dependencia))
            elif dependencia.startswith("/"):
                ruta = dependencia
            else:
                prefijo = next(p for p in pagina.importaciones if dependencia.startswith(p))
                ruta = pagina.importaciones[prefijo] + dependencia[len(prefijo) :]
            assert ruta.startswith("/"), "Los recursos del recorrido deben servirse desde la aplicación."
            if ruta not in recursos:
                recursos.add(ruta)
                if ruta.endswith(".js"):
                    pendientes.append(ruta)
    return recursos


def test_sw_incluye_todos_los_recursos_de_las_pantallas_sin_html_ni_api():
    codigo = (RAIZ / "sw.js").read_text(encoding="utf-8")
    lista = re.search(r"RECURSOS_ESTATICOS\s*=\s*(\[.*?\]);", codigo, re.S).group(1)
    declarados = set(json.loads(re.sub(r",\s*\]", "]", lista)))
    usados = set().union(*(recursos_de_pantalla(p) for p in ("index.html", "recepcion.html", "entrenamiento.html")))
    assert usados <= declarados, f"Faltan recursos en el SW: {sorted(usados - declarados)}"
    assert all((RAIZ / ruta.lstrip("/")).is_file() for ruta in declarados)
    assert all(not ruta.startswith("/api/") and not ruta.endswith(".html") for ruta in declarados)
