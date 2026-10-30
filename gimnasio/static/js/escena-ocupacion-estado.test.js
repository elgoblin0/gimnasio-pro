import {test} from 'node:test';
import assert from 'node:assert/strict';
import {diferenciarVisitas} from './escena-ocupacion-estado.js';

const visita = {id: 'visita-1', zona: 'cardio', minutos: 5};
test('entrada', () => {
  assert.deepEqual(diferenciarVisitas([], [visita]), {entradas: [visita], salidas: [], cambios: []});
});
test('salida', () => {
  assert.deepEqual(diferenciarVisitas([visita], []), {entradas: [], salidas: [visita], cambios: []});
});
test('cambio de zona de la sede conserva la identidad', () => {
  const cambiada = {...visita, zona: 'funcional'};
  assert.deepEqual(diferenciarVisitas([visita], [cambiada]), {entradas: [], salidas: [], cambios: [cambiada]});
});
test('sin cambios, aunque avance la permanencia o cambie el orden', () => {
  const otra = {...visita, id: 'visita-2'};
  assert.deepEqual(diferenciarVisitas([visita, otra], [otra, {...visita, minutos: 6, por_conciliar: true}]),
    {entradas: [], salidas: [], cambios: []});
});
test('distingue cambios simultáneos y no modifica los estados', () => {
  const anterior = Object.freeze([Object.freeze(visita), Object.freeze({...visita, id: 'saliente'})]);
  const cambio = Object.freeze({...visita, zona: 'musculacion'});
  const entrada = Object.freeze({...visita, id: 'entrante'});
  assert.deepEqual(diferenciarVisitas(anterior, Object.freeze([cambio, entrada])),
    {entradas: [entrada], salidas: [anterior[1]], cambios: [cambio]});
});
