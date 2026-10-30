export const CARRIL = -.5;
export const PUERTA = {x: CARRIL, z: 15.5};
export const SALAS = {
  'Musculación': {x0: -18, x1: -3, z0: -13, z1: 0, pasillo: -6, puertaX: -3},
  'Peso libre': {x0: 2, x1: 18, z0: -13, z1: -2, pasillo: -8, puertaX: 2},
  'Cardio': {x0: -18, x1: -3, z0: 0, z1: 13, pasillo: 6, puertaX: -3},
  'Funcional': {x0: 2, x1: 18, z0: -2, z1: 13, pasillo: 6, puertaX: 2},
  'En la sede': {x0: -3, x1: 2, z0: -13, z1: 13, pasillo: null, puertaX: CARRIL},
};
export const NOMBRES = Object.keys(SALAS);

