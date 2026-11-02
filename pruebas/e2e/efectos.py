"""Elección del modo sin efectos para las pruebas (comun/efectos.js)."""

# El CI dibuja sin GPU y la detección activa el modo sin efectos. Las pruebas que miran el 3D eligen
# los efectos a mano, como haría alguien con el interruptor: la elección manda sobre la detección.
CON_EFECTOS = "try { localStorage.setItem('gimnasio-sin-efectos', 'no'); } catch {}"
