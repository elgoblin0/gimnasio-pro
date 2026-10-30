import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import {SALAS} from './escena-ocupacion-plano.js';

const codigo = readFileSync(new URL('./escena-ocupacion.js', import.meta.url), 'utf8');
const funcion = codigo.slice(codigo.indexOf('  function lugarLibre('), codigo.indexOf('  function quitar('));

for (const zona of Object.keys(SALAS)) {
  test('asigna lugares distintos al excedente y reutiliza lugares libres en ' + zona, () => {
    const sala = SALAS[zona];
    const lugares = {[zona]: Array.from({length: 24}, (_, i) => ({x: sala.x0 + .5, z: sala.z0 + i / 2, giro: 0}))};
    const personas = [];
    const contexto = vm.createContext({SALAS, lugares, personas});
    vm.runInContext(funcion, contexto);
    const agregar = () => {
      const p = {zona};
      contexto.persona = p;
      p.lugar = vm.runInContext('lugarLibre(persona.zona, persona)', contexto);
      personas.push(p);
    };
    for (let i = 0; i < 100; i++) agregar();
    const verificar = () => assert.equal(new Set(personas.map(p => p.lugar.x + ',' + p.lugar.z)).size, personas.length);
    verificar();
    personas.splice(25, 1);
    agregar();
    verificar();
    contexto.persona = personas[40];
    personas[40].lugar = vm.runInContext('lugarLibre(persona.zona, persona)', contexto);
    verificar();
  });
}
