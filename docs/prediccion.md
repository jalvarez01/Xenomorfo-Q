# Predicción del destino del tripulante

Heurística detrás de la herramienta `predecir_destino` (T12). Responsable: Santiago Meneses. Código en `director/prediccion.py`, pruebas en `tests/test_prediccion.py`.

## Uso

```python
from director.prediccion import PredictorDestino
from sim import EstacionEnv

env = EstacionEnv()
env.reset(semilla=42)
for _ in range(10):
    env.step(1)

predictor = PredictorDestino(env.mapa)       # precalcula distancias una vez por mapa
predictor.predecir(env.trayectoria)
# {'sala': ..., 'confianza': ..., 'acercamiento_casillas': ..., 'ticks_analizados': 10}
```

La herramienta de T11 crea un `PredictorDestino` por partida y llama a `predecir(env.trayectoria)`, sin argumentos para el modelo.

## Resultado

| Clave | Tipo | Significado |
|---|---|---|
| `sala` | `str` o `None` | Nombre de la sala estimada. `None` solo si en toda la ventana estuvo en puertas. |
| `confianza` | `float` | De 0 a 1, con dos decimales. Qué tan directo caminó hacia esa sala. |
| `acercamiento_casillas` | `int` | Pasos que se acercó a la sala estimada en la ventana. |
| `ticks_analizados` | `int` | Ticks usados: 10, o menos si la partida acaba de empezar. |

Las claves `acercamiento_casillas` y `ticks_analizados` se suman a `{sala, confianza}`, que es lo que pide la hoja de contratos, para que el agente pueda explicar la estimación ("se acercó 6 casillas en los últimos 10 ticks").

## Cómo decide

1. Toma las últimas 11 posiciones de la trayectoria (10 ticks).
2. Para cada sala calcula `d0`, la distancia caminando al inicio de la ventana, y `d1`, al final. La distancia es BFS sobre las casillas transitables hasta la casilla más cercana de la sala; dentro de la sala es 0. En una cuadrícula sin pesos, BFS da la misma distancia que A*.
3. `acercamiento = d0 - d1`. Solo cuentan las salas con acercamiento positivo.
4. `puntaje = acercamiento × (acercamiento / d0)`: el acercamiento ponderado por la fracción del camino recorrido. Gana la sala de mayor puntaje; en un empate, la más cercana al final y después la de menor índice.
5. `confianza = acercamiento / ticks`.
6. Si no se acercó a ninguna sala (quieto o solo alejándose), devuelve la última sala en la que estuvo, con confianza 0.

Por qué el puntaje no es solo el acercamiento: al caminar hacia el este, la sala más lejana del este siempre suma más pasos de acercamiento que la más cercana. Si el tripulante entra al Laboratorio y se detiene, el acercamiento puro diría Comunicaciones. Con la fracción recorrida gana el Laboratorio (llegó, fracción 1) y, si sigue de largo, al quedar el Laboratorio fuera de la ventana gana la sala siguiente. Ver [D10](decisiones.md#d10-predecir_destino-usa-acercamiento-ponderado-por-camino-recorrido).

## Ejemplos verificados en vela9

| Trayectoria | Resultado |
|---|---|
| De Médico (2, 3) al Laboratorio (10, 3) | Laboratorio |
| Del Corredor A (8, 6) a la puerta (3, 9) | Bodega |
| Del Corredor B (13, 7) a la puerta (20, 9) | Hangar, confianza 0.89 (8 de 9 ticks lo acercaron) |

## Limitaciones

- La confianza mide qué tan directo caminó, no qué tan ambigua es la elección. Caminando por un corredor hacia dos salas alineadas, la confianza puede ser 1.0 aunque el destino real sea la segunda sala.
- Solo mira 10 ticks: no recuerda salas visitadas antes ni hábitos del tripulante.
- Con el bot provisional del entorno, que camina al azar, las predicciones cambian mucho de un tick a otro. La tarea opcional T31 reemplaza esta heurística por un árbol de decisión entrenado con trayectorias de bots.
