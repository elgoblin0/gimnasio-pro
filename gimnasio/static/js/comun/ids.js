import { crearReloj } from "./reloj.js";

const reloj = crearReloj();
const mascara62 = (1n << 62n) - 1n;
let ultimoMilisegundo;
let aleatorio = 0n;

// Secuencia por módulo en el mismo milisegundo (RFC 9562, 6.2).
// Al retroceder el reloj se vuelve a la fecha indicada, con nuevos bits aleatorios.
export function nuevoId() {
  const milisegundo = reloj.ahora().getTime();
  if (!Number.isSafeInteger(milisegundo) || milisegundo < 0 || milisegundo >= 2 ** 48) {
    throw new RangeError("El momento debe caber en los 48 bits de milisegundos del UUIDv7");
  }
  let siguiente;
  if (milisegundo === ultimoMilisegundo) {
    siguiente = aleatorio + 1n;
  } else {
    const datos = crypto.getRandomValues(new Uint8Array(10));
    siguiente = 0n;
    for (const dato of datos) siguiente = (siguiente << 8n) | BigInt(dato);
    siguiente &= (1n << 74n) - 1n;
  }
  if (siguiente >= 1n << 74n) {
    throw new RangeError("Se agotaron los UUIDv7 del milisegundo actual");
  }
  ultimoMilisegundo = milisegundo;
  aleatorio = siguiente;
  const valor = (BigInt(milisegundo) << 80n) | (7n << 76n) |
    ((aleatorio >> 62n) << 64n) | (2n << 62n) | (aleatorio & mascara62);
  const texto = valor.toString(16).padStart(32, "0");
  return `${texto.slice(0, 8)}-${texto.slice(8, 12)}-${texto.slice(12, 16)}-${texto.slice(16, 20)}-${texto.slice(20)}`;
}
