// Serialización del formulario: enteros y decimales exactos para la API, según el catálogo.
export function prepararMedidas(medidas, valores) {
  const resultado = {};
  for (const medida of medidas) {
    const texto = String(valores[medida] ?? "").trim();
    if (!texto || !Number.isFinite(Number(texto))) throw new Error("Completá las medidas con números válidos.");
    if (["repeticiones", "duracion"].includes(medida)) {
      const valor = Number(texto);
      if (!Number.isSafeInteger(valor) || valor <= 0) throw new Error("Repeticiones y duración requieren enteros positivos.");
      resultado[medida] = valor;
    } else if (["carga", "distancia"].includes(medida)) {
      if (!/^\d+(?:\.\d{1,2})?$/.test(texto) || (medida === "distancia" && Number(texto) === 0)) {
        throw new Error("Usá medidas positivas con hasta dos decimales; la carga puede ser cero.");
      }
      resultado[medida] = texto;
    } else throw new Error("La medida del ejercicio no es válida.");
  }
  return resultado;
}
