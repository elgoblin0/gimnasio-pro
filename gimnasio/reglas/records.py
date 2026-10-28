"""Récords del ejercicio hecho sobre series vigentes, versión 1.0.0."""

from gimnasio.comun.tipos import Razon, RecordPersonal


def detectar_records(serie, historial_vigente):
    """Un empate o el primer registro de una medida no constituye un récord."""
    if not serie.vigente or serie.carga is None:
        return ()
    ejercicio = serie.ejercicio_hecho_id or serie.ejercicio_id
    historial = tuple(
        anterior
        for anterior in historial_vigente
        if anterior.vigente
        and (anterior.ejercicio_hecho_id or anterior.ejercicio_id) == ejercicio
        and anterior.carga is not None
    )
    if not historial:
        return ()
    records = []

    def agregar(medida, marca, anterior):
        records.append(
            RecordPersonal(
                medida,
                marca,
                anterior,
                serie.carga,
                Razon(
                    medida,
                    "1.0.0",
                    (("ejercicio_hecho_id", ejercicio), ("marca_anterior", str(anterior)), ("marca", str(marca))),
                ),
            )
        )

    maxima = max(anterior.carga for anterior in historial)
    if serie.carga > maxima:
        agregar("carga_maxima", serie.carga, maxima)
    repeticiones = tuple(
        anterior.repeticiones
        for anterior in historial
        if anterior.carga >= serie.carga and anterior.repeticiones is not None
    )
    if repeticiones and serie.repeticiones is not None and serie.repeticiones > max(repeticiones):
        agregar("repeticiones_a_carga", serie.repeticiones, max(repeticiones))
    return tuple(records)
