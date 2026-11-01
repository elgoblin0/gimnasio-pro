import assert from "node:assert/strict";
import test from "node:test";
import {
  anuncioDeCambio, cambioDeOcurrencia, cambiosDeAgenda, marcasDeCupo, semanasDeAgenda, TOPE_ASIENTOS, TOPE_ESPERA,
} from "./clases-agenda.js";

const fila = (extra = {}) => ({
  clase_id: "clase", fecha: "2026-10-27", clase: "Funcional", hora_inicio: "18:00",
  cupo: 3, libres: 0, espera: 2, cancelada: false, reserva: null, ...extra,
});
const conLugar = { id: "r", estado: "con_lugar", posicion: null };
const enEspera = (posicion) => ({ id: "r", estado: "en_espera", posicion });

test("agrupa dos semanas de lunes a domingo y ordena cada día por hora", () => {
  const semanas = semanasDeAgenda({ desde: "2026-10-26", ocurrencias: [
    fila({ hora_inicio: "18:00" }), fila({ clase_id: "otra", hora_inicio: "07:00" }), fila({ fecha: "2026-11-08" }),
  ] });
  assert.deepEqual(semanas.map(({ titulo, desde, hasta }) => [titulo, desde, hasta]),
    [["Esta semana", "2026-10-26", "2026-11-01"], ["La siguiente", "2026-11-02", "2026-11-08"]]);
  assert.equal(semanas[0].dias[1].nombre, "Martes");
  assert.deepEqual(semanas[0].dias[1].ocurrencias.map((o) => o.hora_inicio), ["07:00", "18:00"]);
  assert.equal(semanas[1].dias[6].ocurrencias.length, 1);
  assert.equal(semanas[0].dias[0].ocurrencias.length, 0);
});

test("las semanas cruzan el cambio de mes sin correrse", () => {
  const [, siguiente] = semanasDeAgenda({ desde: "2026-12-21", ocurrencias: [] });
  assert.equal(siguiente.dias[6].fecha, "2027-01-03");
});

test("dibuja asientos ocupados, libres y el propio primero", () => {
  assert.deepEqual(marcasDeCupo(fila({ libres: 1, espera: 0 })).asientos, ["ocupado", "ocupado", "libre"]);
  assert.deepEqual(marcasDeCupo(fila({ libres: 1, espera: 0, reserva: conLugar })).asientos, ["propio", "ocupado", "libre"]);
});

test("marca la posición propia en la lista de espera", () => {
  assert.deepEqual(marcasDeCupo(fila({ reserva: enEspera(2) })).espera, ["espera", "propio"]);
});

test("una ocurrencia cancelada no muestra lugares ocupados ni propios", () => {
  const marcas = marcasDeCupo(fila({ cancelada: true, libres: 0, espera: 0, reserva: conLugar }));
  assert.deepEqual(marcas.asientos, ["libre", "libre", "libre"]);
  assert.equal(marcas.proporcion, 0);
});

test("un cupo grande pasa a barra y una espera larga a un resto, sin perder la marca propia", () => {
  const grande = marcasDeCupo(fila({ cupo: TOPE_ASIENTOS + 1, libres: 1, espera: 0 }));
  assert.equal(grande.asientos, null);
  assert.equal(grande.proporcion, TOPE_ASIENTOS / (TOPE_ASIENTOS + 1));
  const larga = marcasDeCupo(fila({ espera: TOPE_ESPERA + 4, reserva: enEspera(TOPE_ESPERA + 3) }));
  assert.equal(larga.espera.length, TOPE_ESPERA);
  assert.equal(larga.espera.at(-1), "propio");
  assert.equal(larga.restoEspera, 4);
});

test("reservar con lugar entra un asiento y estampa el propio", () => {
  const cambio = cambioDeOcurrencia(fila({ libres: 2, espera: 0 }), fila({ libres: 1, espera: 0, reserva: conLugar }));
  assert.equal(cambio.propio, "reservo");
  assert.deepEqual(cambio.entran, [0, 1]);
  assert.deepEqual(cambio.vuelos, []);
});

test("cancelar sin espera libera el último asiento", () => {
  const cambio = cambioDeOcurrencia(fila({ libres: 1, espera: 0, reserva: conLugar }), fila({ libres: 2, espera: 0 }));
  assert.equal(cambio.propio, "cancelo");
  assert.deepEqual(cambio.salen, [1]);
});

test("pasar de la espera a tener lugar vuela de la posición propia al asiento propio", () => {
  const cambio = cambioDeOcurrencia(fila({ reserva: enEspera(2) }), fila({ espera: 1, reserva: conLugar }));
  assert.equal(cambio.propio, "paso_a_tener_lugar");
  assert.equal(cambio.subidas, 1);
  assert.deepEqual(cambio.vuelos, [{ desdeEspera: 1, asiento: 0 }]);
  assert.deepEqual(cambio.entran, [0]);
});

test("quien libera su lugar en una clase llena ve subir al primero de la espera", () => {
  const cambio = cambioDeOcurrencia(fila({ reserva: conLugar }), fila({ espera: 1 }));
  assert.equal(cambio.propio, "cancelo");
  assert.deepEqual(cambio.vuelos, [{ desdeEspera: 0, asiento: 2 }]);
});

test("subir el cupo sube a los primeros de la espera", () => {
  const cambio = cambioDeOcurrencia(fila({ espera: 2 }), fila({ cupo: 5, espera: 0 }));
  assert.equal(cambio.subidas, 2);
  assert.deepEqual(cambio.entran, [3, 4]);
  assert.deepEqual(cambio.vuelos, [{ desdeEspera: 0, asiento: 3 }, { desdeEspera: 1, asiento: 4 }]);
});

test("si alguien deja la espera sin que se mueva el cupo, no se inventa una subida", () => {
  const cambio = cambioDeOcurrencia(fila({ espera: 2 }), fila({ espera: 1 }));
  assert.equal(cambio.subidas, 0);
  assert.deepEqual(cambio.vuelos, []);
  assert.equal(cambio.cifras, true);
});

test("sobre una barra de cupo no hay asientos adonde volar", () => {
  const grande = { cupo: TOPE_ASIENTOS + 1 };
  const cambio = cambioDeOcurrencia(fila({ ...grande, reserva: enEspera(1) }), fila({ ...grande, espera: 1, reserva: conLugar }));
  assert.equal(cambio.subidas, 1);
  assert.deepEqual(cambio.vuelos, []);
});

test("volver a la espera y avanzar en ella se distinguen", () => {
  assert.equal(cambioDeOcurrencia(fila({ reserva: conLugar }), fila({ reserva: enEspera(1) })).propio, "volvio_a_espera");
  assert.equal(cambioDeOcurrencia(fila({ reserva: enEspera(2) }), fila({ espera: 1, reserva: enEspera(1) })).propio, "avanzo_en_espera");
});

test("cancelar la ocurrencia no cuenta como cancelación propia", () => {
  const cambio = cambioDeOcurrencia(fila({ reserva: conLugar }), fila({ cancelada: true, espera: 0 }));
  assert.equal(cambio.cancelada, true);
  assert.equal(cambio.propio, null);
  assert.deepEqual(cambio.vuelos, []);
});

test("sin cambio visible devuelve null", () => {
  assert.equal(cambioDeOcurrencia(fila(), fila()), null);
});

test("la primera lectura y las ocurrencias nuevas no se animan", () => {
  assert.deepEqual(cambiosDeAgenda(null, [fila()]), []);
  assert.deepEqual(cambiosDeAgenda([fila()], [fila(), fila({ fecha: "2026-11-03", libres: 3 })]), []);
  const [cambio, ...resto] = cambiosDeAgenda([fila()], [fila({ libres: 1 })]);
  assert.equal(cambio.clave, "clase|2026-10-27");
  assert.equal(resto.length, 0);
});

test("anuncia al lector solo lo que importa a quien mira", () => {
  const detalle = "Funcional, 27/10/2026 18:00.";
  const despues = fila({ espera: 1, reserva: conLugar });
  const cambio = cambioDeOcurrencia(fila({ reserva: enEspera(1) }), despues);
  assert.equal(anuncioDeCambio(despues, cambio), `Ya tenés lugar: ${detalle}`);
  assert.equal(anuncioDeCambio(despues, cambio, "socio"), `El socio pasó a tener lugar: ${detalle}`);
  const cancelada = fila({ cancelada: true, espera: 0 });
  assert.equal(anuncioDeCambio(cancelada, cambioDeOcurrencia(fila(), cancelada)), `Se canceló la ocurrencia: ${detalle}`);
  const ajena = fila({ libres: 1 });
  assert.equal(anuncioDeCambio(ajena, cambioDeOcurrencia(fila(), ajena)), "");
});
