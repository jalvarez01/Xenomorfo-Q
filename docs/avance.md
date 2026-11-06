# Avance de la simulación con eventos

Base de la herramienta `avanzar_simulacion` (T10). Responsable: Santiago Meneses. Código en `sim/avance.py`, pruebas en `tests/test_avance.py`.

## Uso

```python
from sim import EstacionEnv
from sim.avance import Avance

def siempre_derecha(env):
    return 1

env = EstacionEnv()
env.reset(semilla=42)
avance = Avance(env, siempre_derecha)   # uno por partida, después de reset()
avance.avanzar(10)
# {'tick': 10, 'ticks_avanzados': 10, 'eventos': [...], 'capturado': False}
```

La herramienta de T11 crea un `Avance` por partida y llama a `avanzar(ticks)` con el número que pida el modelo.

## Quién mueve al alienígena

`Avance` recibe una **política**: una función que recibe el entorno y devuelve la acción del alienígena (0 arriba, 1 derecha, 2 abajo, 3 izquierda, 4 revisar casillero). Así T10 no depende del alienígena por reglas: hoy las pruebas usan políticas simples, y cuando exista T18 se pasa su función sin cambiar este módulo.

La acción 4 no mueve al alienígena, así que sirve como "quedarse quieto" mientras no haya otra opción.

## Resultado

| Clave | Tipo | Significado |
|---|---|---|
| `tick` | `int` | Tick de la partida al terminar. |
| `ticks_avanzados` | `int` | Ticks que avanzó; menos que los pedidos si la partida terminó antes. |
| `eventos` | `list[str]` | Eventos de esta llamada, por ejemplo `"tick 12: el tripulante entró a Laboratorio"`. |
| `capturado` | `bool` | True si el tripulante fue capturado. |

`ticks_avanzados` se suma a `{tick, eventos, capturado}` de la hoja de contratos para que el agente sepa si la partida se cortó antes. `Avance.historial` guarda los eventos de toda la partida.

## Eventos

| Evento | Cuándo |
|---|---|
| `el tripulante entró a <sala>` | Llega a una sala distinta de la última en que estuvo. Las puertas no cuentan: pisar una puerta y volver no es evento. |
| `el alienígena entró a <sala>` | Igual, para el alienígena. |
| `el alienígena vio al tripulante` | `info["ve_tripulante"]` pasa a True. |
| `el alienígena perdió de vista al tripulante` | `info["ve_tripulante"]` pasa a False. |
| `el alienígena capturó al tripulante` | Hubo captura; el avance se detiene en ese tick. |
| `se acabó el tiempo de la partida (<n> ticks)` | Se llegó a `max_ticks`; el avance se detiene. |

Los eventos de visión están activos: el entorno informa `ve_tripulante` en `info` desde la visión (T08, ver [entorno.md](entorno.md#visión)). Al crear el `Avance` se asume que el alienígena no ve al tripulante.

## Errores

`avanzar` lanza `ValueError` con un mensaje claro, sin avanzar la partida, si:

- `ticks` no es un entero entre 1 y 20;
- la partida ya terminó por captura o por tiempo.

El agente convierte esas excepciones en `{"error": ...}` para el modelo (sección Agente de [contratos.md](contratos.md)).

## Pendiente

- Evento de pista: cuando exista `dar_pista` (T11) y la reacción del alienígena (T19), por ejemplo "el alienígena llegó a la sala de la pista".
- Conectar la política del alienígena por reglas (T18).
