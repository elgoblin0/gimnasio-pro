"""ADR 0003: detectar modificaciones de hechos en el SQL del código Python."""

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
HECHOS = {
    "restricciones_salud",
    "dolores_reportados",
    "chequeos_dia",
    "avisos_entrenador",
    "prescripciones_efectivas",
    "consentimientos",
    "entradas",
    "salidas",
    "sesiones_realizadas",
    "series_realizadas",
    "sustituciones",
}
EXCEPCION = "gimnasio/demo/repositorio.py"
DINAMICA = "__tabla_dinamica__"
COMENTARIOS_Y_VALORES = re.compile(r"--[^\n]*|\#[^\n]*|/\*.*?\*/|'(?:''|\\.|[^'])*'|\"(?:\"\"|\\.|[^\"])*\"", re.S)
TOKENS = re.compile(r"`(?:``|[^`])+`|[a-zA-Z_][a-zA-Z_0-9]*|[.,=;()]")
RESERVADAS = {
    "join",
    "inner",
    "left",
    "right",
    "cross",
    "on",
    "where",
    "using",
    "set",
    "limit",
    "order",
    "straight_join",
}


def nombre_tabla(tokens, posicion):
    if posicion >= len(tokens) or not tokens[posicion].isidentifier():
        return None, posicion
    nombre = tokens[posicion]
    posicion += 1
    while posicion + 1 < len(tokens) and tokens[posicion] == "." and tokens[posicion + 1].isidentifier():
        nombre = tokens[posicion + 1]
        posicion += 2
    return nombre, posicion


def declaraciones(tokens):
    """Relaciona los alias SQL con sus tablas, sin confundir un JOIN de lectura con escritura."""
    aliases = {}
    primera = None
    posiciones = [0]
    profundidad = 0
    for i, token in enumerate(tokens):
        if token == "(":
            profundidad += 1
        elif token == ")":
            profundidad -= 1
        elif profundidad == 0 and token in {"join", ","}:
            posiciones.append(i + 1)
    for posicion in posiciones:
        nombre, siguiente = nombre_tabla(tokens, posicion)
        if nombre is None:
            continue
        primera = primera or nombre
        aliases[nombre] = nombre
        if siguiente < len(tokens) and tokens[siguiente] == "as":
            siguiente += 1
        if siguiente < len(tokens) and tokens[siguiente].isidentifier() and tokens[siguiente] not in RESERVADAS:
            aliases[tokens[siguiente]] = nombre
    return primera, aliases


def tablas_modificadas(sql):
    limpio = COMENTARIOS_Y_VALORES.sub(" ", sql)
    tokens = [token.strip("`").lower() for token in TOKENS.findall(limpio)]
    resultado = set()
    for indice, token in enumerate(tokens):
        fin = tokens.index(";", indice) if ";" in tokens[indice:] else len(tokens)
        cuerpo = tokens[indice + 1 : fin]
        if token == "insert" and "into" in cuerpo:
            tabla, _ = nombre_tabla(cuerpo, cuerpo.index("into") + 1)
            if tabla and any(cuerpo[i : i + 4] == ["on", "duplicate", "key", "update"] for i in range(len(cuerpo))):
                resultado.add(tabla)
        if token == "update" and tokens[max(0, indice - 3) : indice] == ["on", "duplicate", "key"]:
            continue
        if token not in {"update", "delete"} or (indice and tokens[indice - 1] == "for"):
            continue
        while cuerpo and cuerpo[0] in {"low_priority", "ignore", "quick"}:
            cuerpo = cuerpo[1:]
        if token == "update":
            corte = cuerpo.index("set") if "set" in cuerpo else len(cuerpo)
            primera, aliases = declaraciones(cuerpo[:corte])
            asignaciones = cuerpo[corte + 1 :]
            destinos = []
            for i, parte in enumerate(asignaciones):
                if parte == "=":
                    if i >= 3 and asignaciones[i - 2] == ".":
                        destinos.append(aliases.get(asignaciones[i - 3]))
                    else:
                        # Sin calificador no se puede excluir ninguna tabla del UPDATE múltiple.
                        destinos.extend(aliases.values())
            resultado.update(destino for destino in destinos or [primera] if destino)
        elif "from" in cuerpo:
            corte = cuerpo.index("from")
            if corte == 0 and "using" not in cuerpo:
                nombre, _ = nombre_tabla(cuerpo, 1)
                if nombre:
                    resultado.add(nombre)
            else:
                inicio = cuerpo.index("using") + 1 if "using" in cuerpo else corte + 1
                _, aliases = declaraciones(cuerpo[inicio:])
                destinos = cuerpo[1 : cuerpo.index("using")] if corte == 0 else cuerpo[:corte]
                resultado.update(aliases.get(destino, destino) for destino in destinos if destino.isidentifier())
    return resultado


def texto_sql(nodo):
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        return "".join(valor.value if isinstance(valor, ast.Constant) else DINAMICA for valor in nodo.values)
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add):
        izquierda, derecha = texto_sql(nodo.left), texto_sql(nodo.right)
        if izquierda is not None or derecha is not None:
            return (izquierda if izquierda is not None else DINAMICA) + (derecha if derecha is not None else DINAMICA)
    if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "format":
        formato = texto_sql(nodo.func.value)
        if formato is not None:
            return re.sub(r"\{[^}]*\}", DINAMICA, formato)
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Mod):
        formato = texto_sql(nodo.left)
        if formato is not None:
            return re.sub(r"%(?:\([^)]+\))?[srd]", DINAMICA, formato)
    return None


def violaciones_historial(raiz):
    encontradas = set()
    for archivo in sorted((raiz / "gimnasio").rglob("*.py")):
        relativo = archivo.relative_to(raiz).as_posix()
        if relativo == EXCEPCION:
            continue
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        for nodo in ast.walk(arbol):
            sql = texto_sql(nodo)
            if sql is None:
                continue
            # Una tabla dinámica no permite demostrar que el catálogo de hechos queda excluido.
            for tabla in tablas_modificadas(sql) & (HECHOS | {DINAMICA}):
                encontradas.add(f"{relativo}:{nodo.lineno}: {tabla} solo admite INSERT")
    return sorted(encontradas)


@pytest.mark.parametrize("tabla", sorted(HECHOS))
@pytest.mark.parametrize("operacion", ["UPDATE {tabla} SET anulada=1", "DELETE FROM {tabla} WHERE id=%s"])
def test_cada_tabla_de_hechos_rechaza_update_y_delete(tabla, operacion):
    assert tablas_modificadas(operacion.format(tabla=tabla)) & HECHOS == {tabla}


@pytest.mark.parametrize(
    "sql,esperadas",
    [
        ("uPdAtE\n `gimnasio`.`ENTRADAS`\nSET anulada=1", {"entradas"}),
        ("DELETE s FROM series_realizadas AS s WHERE s.id=%s", {"series_realizadas"}),
        ("delete from e using entradas e where e.id=%s", {"entradas"}),
        ("UPDATE usuarios u JOIN entradas e ON e.socio_id=u.id SET e.anulada=1", {"entradas"}),
        ("UPDATE usuarios u JOIN entradas e ON e.socio_id=u.id SET u.activo=0", {"usuarios"}),
        (
            "UPDATE usuarios u JOIN series_realizadas s ON s.autor_id=u.id SET carga=1",
            {"usuarios", "series_realizadas"},
        ),
        ("DELETE LOW_PRIORITY QUICK IGNORE FROM entradas WHERE id=%s", {"entradas"}),
        ("DELETE e,s FROM entradas e JOIN salidas s ON s.entrada_id=e.id", {"entradas", "salidas"}),
        ("INSERT INTO entradas (id) VALUES (%s) ON DUPLICATE KEY UPDATE id=VALUES(id)", {"entradas"}),
        ("SELECT 1; DELETE FROM consentimientos WHERE id=%s", {"consentimientos"}),
        ("-- solo inserciones\nINSERT INTO entradas (id) VALUES (%s)", set()),
        ("SELECT * FROM entradas FOR UPDATE", set()),
        ("INSERT INTO mensajes (texto) VALUES ('DELETE FROM entradas')", set()),
        ("/* DELETE FROM entradas */ SELECT 1", set()),
        ("DELETE FROM solicitudes_idempotentes WHERE creada_en < %s", {"solicitudes_idempotentes"}),
        ("DELETE FROM intentos_de_ingreso WHERE creado_en < %s", {"intentos_de_ingreso"}),
    ],
)
def test_sql_multilinea_aliases_y_purgas_operativas(sql, esperadas):
    assert tablas_modificadas(sql) == esperadas


def escribir(raiz, ruta, contenido):
    archivo = raiz / ruta
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(contenido, encoding="utf-8")


def test_excepcion_solo_en_repositorio_demo_y_no_en_otro_modulo(tmp_path):
    escribir(tmp_path, EXCEPCION, 'sql = "DELETE FROM entradas"')
    assert violaciones_historial(tmp_path) == []
    escribir(tmp_path, "gimnasio/demo/servicio.py", 'sql = "DELETE FROM entradas"')
    escribir(tmp_path, "gimnasio/visitas/repositorio.py", 'sql = "UPDATE salidas SET anulada=1"')
    resultado = violaciones_historial(tmp_path)
    assert len(resultado) == 2
    assert any("gimnasio/demo/servicio.py" in mensaje for mensaje in resultado)
    assert any("gimnasio/visitas/repositorio.py" in mensaje for mensaje in resultado)


@pytest.mark.parametrize(
    "dinamico",
    [
        'sql = f"DELETE FROM {tabla} WHERE id=%s"',
        'sql = "DELETE FROM " + tabla',
        'sql = "DELETE FROM {}".format(tabla)',
        'sql = "DELETE FROM %s" % tabla',
    ],
)
def test_ast_detecta_concatenacion_y_tabla_dinamica_sin_excepcion_generica(tmp_path, dinamico):
    escribir(tmp_path, "gimnasio/entrenamiento/repositorio.py", 'sql = "UPDATE " + "series_realizadas SET carga=%s"')
    escribir(tmp_path, "gimnasio/visitas/repositorio.py", dinamico)
    assert len(violaciones_historial(tmp_path)) == 2


def test_insert_y_purgas_operativas_pasan_en_el_arbol(tmp_path):
    escribir(
        tmp_path, "gimnasio/comun/idempotencia.py", 'sql = "DELETE FROM solicitudes_idempotentes WHERE creada_en < %s"'
    )
    escribir(
        tmp_path, "gimnasio/permisos/repositorio.py", 'sql = "DELETE FROM intentos_de_ingreso WHERE creado_en < %s"'
    )
    escribir(tmp_path, "gimnasio/visitas/repositorio.py", 'sql = "INSERT INTO entradas (id) VALUES (%s)"')
    assert violaciones_historial(tmp_path) == []


def test_el_arbol_real_solo_inserta_hechos_fuera_del_reinicio_demo():
    assert violaciones_historial(RAIZ) == []
