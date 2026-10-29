# Contratos

Interfaces acordadas entre módulos. Cada sección indica su estado:

- **Existe (v0):** implementado hoy y cubierto por pruebas.
- **Planeado:** acordado pero sin implementar; puede ajustarse en la tarea indicada.

Cambiar un contrato requiere actualizar este archivo en el mismo Pull Request.

## 1. Entorno

**Existe (v0)**, en `sim/env.py`.

```python
EstacionEnv(mapa, max_ticks=300, distancia_inicial=10, semilla=None)
obs = env.reset(semilla)                              # np.ndarray (4, alto, ancho) float32
obs, recompensa, terminado, info = env.step(accion)
```

- `mapa`: un `Mapa` o la ruta a un archivo de mapa. Por defecto `data/mapas/vela9.txt`.
- `info` hoy: `{"tick", "capturado", "distancia_real"}`.
- **Planeado:** agregar a `info` las claves `estado_arbol` (estado del árbol de comportamiento del alienígena por reglas) y `pista_activa` (si hay una pista vigente).

## 2. Acciones

**Existe (v0).**

| Acción | Significado |
|---|---|
| 0 | arriba |
| 1 | derecha |
| 2 | abajo |
| 3 | izquierda |
| 4 | revisar casillero contiguo |

En v0 la acción 4 siempre cuenta como casillero vacío (los casilleros reales llegan en T09).

## 3. Observación

**Existe (v0)** con las capas 1 y 3 en su forma provisional.

Tensor `(4, alto, ancho)` en `float32`:

| Capa | Contenido | v0 |
|---|---|---|
| 0 | Paredes: 1 pared, 0.5 casillero, 0 libre | Completa |
| 1 | Creencia sobre la posición del tripulante; suma 1 | Uniforme sobre las casillas libres |
| 2 | Posición del alienígena (one-hot) | Completa |
| 3 | Pista de la directora como mapa de calor de zona | Ceros |

## 4. Recompensa

**Existe (v0).**

- `+100` por captura, y el episodio termina.
- `-1` por cada tick.
- `-5` adicional por revisar un casillero vacío.
- El episodio termina sin captura al llegar a `max_ticks`.

Una captura en un tick con movimiento da `99.0` (100 - 1).

## 5. Directora

**Planeado** (T15 a T20).

```python
predecir(trayectoria: list[tuple[int, int]], mapa) -> np.ndarray  # forma (n_salas,), suma 1
```

- Entrada: las últimas 10 posiciones del tripulante.
- Salida: una probabilidad por sala. `n_salas` viene de `mapa.n_salas`; en vela9 es 8.
- Las salas son las del archivo de anotación del mapa y se consultan con `Mapa.sala(x, y)` (**existe**). Ver [entorno.md](entorno.md#salas).
- Etiqueta: sala destino (definición pendiente de confirmar en T15).
- Modelo guardado en `director/modelos/directora_cnn.pt`, congelado tras T20.

## 6. Pistas

**Planeado** (T19).

- Solo se da una pista si el alienígena lleva más de X ticks a más de 6 casillas del tripulante.
- Presupuesto limitado de pistas por episodio.
- Formato: zona (las casillas de la sala más probable), nunca la casilla exacta.
- X y el presupuesto se definen en T19.

## 7. Dataset

**Planeado.**

- Formato CSV o NPZ en `data/trayectorias/` (esa carpeta no se sube a GitHub).
- Columnas: `partida_id`, `mapa`, `estilo`, `tick`, `x`, `y`, `sala`, `escondido`, `sala_destino`.
- `sala` sale de `Mapa.sala(x, y)` (índice de 0 a `n_salas - 1`; en vela9, 8 salas). Mientras el tripulante está en una puerta, `sala(x, y)` devuelve `-1` y la columna guarda la última sala visitada. Esa regla se implementa con el dataset en T12.
- `sala_destino` usa los mismos índices; su definición exacta está pendiente de confirmar en T15.
- Separación por `partida_id`: 70 % entrenamiento, 15 % validación, 15 % prueba.
- Los mapas de prueba nunca se ven durante el entrenamiento.
