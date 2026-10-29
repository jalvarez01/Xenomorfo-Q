# Entorno de la estación

Código en `sim/mapa.py` y `sim/env.py`. Interfaz formal en [contratos.md](contratos.md).

## Formato de mapas

Los mapas son archivos de texto en `data/mapas/`, un carácter por casilla. Todas las filas deben tener el mismo ancho; las líneas vacías se ignoran.

| Símbolo | Significado | ¿Se camina? |
|---|---|---|
| `#` | pared | no |
| `.` | piso | sí |
| `+` | puerta | sí |
| `L` | casillero (escondite) | no |

Coordenadas `(x, y)`: `x` es la columna, `y` la fila, con `(0, 0)` en la esquina superior izquierda. Fuera del mapa cuenta como pared.

El mapa por defecto es `data/mapas/vela9.txt` (15 filas por 24 columnas, 8 casilleros).

## Reglas

**Movimiento.** En cada tick el alienígena se mueve una casilla en una de las cuatro direcciones. Si la casilla de destino es pared o casillero, se queda donde está. No hay movimiento diagonal.

**Orden del tick.** Primero se mueve el alienígena, luego el tripulante.

**Captura.** Hay captura si la distancia Manhattan entre alienígena y tripulante es 1 o menos. Se revisa justo después de mover al alienígena y otra vez después de mover al tripulante, así que si el alienígena llega a su lado, el tripulante no alcanza a escapar.

**Inicio.** El alienígena aparece en una casilla transitable al azar y el tripulante en otra a por lo menos `distancia_inicial` casillas (10 por defecto).

**Fin.** El episodio termina con la captura o al llegar a `max_ticks` (300 por defecto).

## Bot provisional del tripulante

Mientras llegan los bots con estilos (T11), el tripulante usa un bot simple:

- Opciones: quedarse quieto o moverse a una casilla vecina transitable, sin entrar a la casilla del alienígena.
- Si el alienígena está a 6 casillas o menos, elige al azar entre las opciones que más lo alejan de él.
- Si no, camina al azar.

Todas las decisiones aleatorias usan `env.rng`, así que con la misma semilla y las mismas acciones la partida se repite igual.

## Limitaciones de la versión 0

- Sin visión: el alienígena no tiene línea de vista (T07).
- Sin ruido: no hay propagación de sonido por BFS (T08).
- Casilleros no utilizables: el tripulante no se esconde y la acción 4 siempre cuenta como casillero vacío (T09).
- Creencia uniforme: la capa 1 reparte la probabilidad por igual entre todas las casillas libres (T21).
- Sin pistas: la capa 3 está en ceros (T19).

## Uso

```python
from sim import EstacionEnv

env = EstacionEnv(max_ticks=50)
obs = env.reset(semilla=42)
print("observación:", obs.shape, obs.dtype)
print("alien:", env.alien, "tripulante:", env.tripulante)

total = 0.0
terminado = False
while not terminado:
    obs, recompensa, terminado, info = env.step(1)  # siempre a la derecha
    total += recompensa
print("fin:", info, "recompensa total:", total)
```

Salida:

```
observación: (4, 15, 24) float32
alien: (1, 2) tripulante: (2, 12)
fin: {'tick': 50, 'capturado': False, 'distancia_real': 13} recompensa total: -50.0
```

También se puede pasar otro mapa: `EstacionEnv(mapa="data/mapas/otro.txt")` o `EstacionEnv(mapa=Mapa([...]))`.

## Cómo extenderlo

- **Mapas nuevos:** agregar un `.txt` en `data/mapas/` con los símbolos de arriba. `Mapa` valida el formato al cargarlo.
- **Nuevas mecánicas (visión, ruido, casilleros):** se agregan dentro de `EstacionEnv` sin cambiar las firmas de `reset` y `step`. Si hace falta información nueva, va en `info` o en una capa de la observación, y se documenta en [contratos.md](contratos.md).
- **Bots con estilos:** reemplazan a `_paso_tripulante`; deben usar `self.rng` para seguir siendo reproducibles.
- Cada cambio de reglas lleva su prueba en `tests/`.
