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
# {'sala': 'Bodega', 'confianza': 0.0, 'acercamiento_casillas': 0, 'ticks_analizados': 10}
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

1. Toma las últimas 11 posiciones de la trayectoria (10 ticks). Cada posición debe estar a lo sumo a una casilla de la anterior, como en `env.trayectoria`.
2. Para cada sala calcula `d0`, la distancia caminando al inicio de la ventana, y `d1`, al final. La distancia es BFS sobre las casillas transitables hasta la casilla más cercana de la sala; dentro de la sala es 0. En una cuadrícula sin pesos, BFS da la misma distancia que A*.
3. **Regla de llegada:** si el tripulante terminó dentro de una sala a la que entró durante la ventana (`d0 > 0` y `d1 = 0`), esa sala es el destino, con confianza `d0 / ticks`.
4. Si no, `acercamiento = d0 - d1`. Solo cuentan las salas con acercamiento positivo.
5. `puntaje = acercamiento × (acercamiento / d0)`: el acercamiento ponderado por la fracción del camino recorrido. Gana la sala de mayor puntaje; en un empate, la más cercana al final y después la de menor índice.
6. `confianza = acercamiento / ticks`.
7. Si no se acercó a ninguna sala (quieto o solo alejándose), devuelve la última sala en la que estuvo, con confianza 0.

Por qué hacen falta la regla de llegada y el puntaje: al caminar hacia el este, la sala más lejana del este siempre suma más pasos de acercamiento que la más cercana, y lo sigue haciendo mientras el tripulante camina dentro de la sala a la que ya llegó. Sin la regla de llegada, desde Médico por la fila 3 la predicción pasaba a Corredor B y a Comunicaciones aunque el tripulante ya estuviera en (11, 3), dentro del Laboratorio. Con la regla gana el Laboratorio mientras siga ahí; cuando el inicio de la ventana ya está dentro del Laboratorio, la regla deja de aplicar y el puntaje elige la sala siguiente. Ver [D10](decisiones.md#d10-predecir_destino-usa-acercamiento-ponderado-por-camino-recorrido).

## Ejemplos verificados en vela9

| Trayectoria | Resultado |
|---|---|
| De Médico (1, 3) a cualquier casilla del Laboratorio en la fila 3, de (8, 3) a (14, 3) | Laboratorio |
| De Bodega (1, 12) a cualquier casilla del Reactor en la fila 12, de (7, 12) a (15, 12) | Reactor |
| Del Corredor A (8, 6) a la puerta (3, 9) | Bodega |
| Del Corredor B (13, 7) a la puerta (20, 9) | Hangar, confianza 0.89 (8 de 9 ticks lo acercaron) |

## Limitaciones

- La confianza mide qué tan directo caminó, no qué tan ambigua es la elección. Caminando por un corredor hacia dos salas alineadas, la confianza puede ser 1.0 aunque el destino real sea la segunda sala.
- Solo mira 10 ticks: no recuerda salas visitadas antes ni hábitos del tripulante.
- Con el bot provisional del entorno, que camina al azar, las predicciones cambian mucho de un tick a otro. La tarea opcional T31 reemplaza esta heurística por un árbol de decisión entrenado con trayectorias de bots.
