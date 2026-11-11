# Alienígena por reglas

El alienígena que caza al tripulante (T18) y su reacción a las pistas de la directora (T19). Responsable: Santiago Meneses. Código en `alien/reglas.py`, pruebas en `tests/test_alien_reglas.py`.

## Uso

```python
from alien.reglas import AlienReglas
from sim import EstacionEnv
from sim.avance import Avance

env = EstacionEnv()
env.reset(semilla=42)
alien = AlienReglas(env)              # uno por partida, después de reset()
avance = Avance(env, alien)           # el alienígena es la política de Avance

print(alien.dar_pista("Bodega"))
r = avance.avanzar(20)
print(r["tick"], r["capturado"], alien.estado)
```

Salida:

```
{'sala': 'Bodega', 'pistas_restantes': 2}
16 True persigue
```

Para T11: la herramienta `dar_pista(sala)` llama a `alien.dar_pista(sala)`, `estado_partida` lee `alien.pistas_restantes`, y `avanzar_simulacion(ticks)` usa el `Avance` creado con este alienígena.

## Cómo decide

En cada tick, en este orden:

1. **Lo ve** (el tripulante está en `env.campo_vision`): lo persigue por el camino más corto (A*) y recuerda esa casilla.
2. **Lo perdió de vista:** va a la última casilla donde lo vio. Si llega y no lo ve, deja de buscarlo ahí.
3. **Tiene una pista vigente:** va al centro de la sala de la pista. Al llegar, la pista se cumple.
4. **Si no:** patrulla. Recorre los centros de las salas, siempre hacia el más cercano que no haya visitado en la vuelta actual; cuando visitó todas, empieza otra vuelta.

El estado de la última decisión queda en `alien.estado`: `"persigue"` (reglas 1 y 2), `"va a la pista"` o `"patrulla"`.

**No hace trampa.** Solo usa la posición del tripulante cuando lo está viendo. La posición real la conoce la directora, y la única forma de pasársela es una pista: una sala, nunca una casilla (D2 adaptada en D8).

**Centro de una sala:** la casilla transitable más cercana al promedio de las casillas de la sala. En vela9:

| Sala | Centro |
|---|---|
| Médico | (4, 3) |
| Laboratorio | (11, 3) |
| Comunicaciones | (19, 3) |
| Corredor A | (6, 7) |
| Corredor B | (17, 7) |
| Bodega | (3, 12) |
| Reactor | (11, 12) |
| Hangar | (19, 12) |

## Pistas (T19)

`alien.dar_pista(sala)` devuelve `{"sala", "pistas_restantes"}`.

- Hay 3 pistas por partida (`PISTAS_POR_PARTIDA`).
- El nombre de la sala se reconoce sin importar mayúsculas ni espacios en los extremos: `"  bodega "` es Bodega. Los acentos sí cuentan: "Medico" no es "Médico".
- La pista no mueve al alienígena: queda vigente y la sigue en los próximos ticks. Si ve al tripulante, perseguirlo tiene prioridad, y la pista sigue vigente para después.
- Una pista nueva reemplaza la anterior. `alien.pista_activa` es el nombre de la sala de la pista vigente, o `None`.
- Al llegar al centro de la sala, la pista se cumple y `Avance` registra el evento `"tick N: el alienígena llegó a <sala>, la sala de la pista"`.

Errores, con `ValueError` y sin gastar la pista:

- No quedan pistas: `No quedan pistas: ya se usaron las 3 de la partida.`
- La sala no existe: `La sala 'Enfermería' no existe. Salas válidas: Médico, Laboratorio, ...`

## Resultados en vela9

Con la visión real y `Avance`, en las semillas 0 a 19 y el máximo de 300 ticks, el alienígena captura al tripulante en 18 de las 20 partidas; en las otras 2 se acaba el tiempo. Sin ver nunca al tripulante, la patrulla pasa por el centro de las 8 salas.

## Limitaciones

- Solo recuerda la última casilla donde lo vio: no predice hacia dónde huyó.
- Al llegar al centro de la sala de la pista da la pista por cumplida, aunque el tripulante esté en una esquina que no ve desde ahí.
- La patrulla es fija para un mismo mapa y punto de partida: un tripulante que la conozca podría evitarla.
