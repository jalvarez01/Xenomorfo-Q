# Herramientas, partida y directora

Las 6 herramientas que el modelo de lenguaje puede pedir, la partida que consultan y la directora que une todo (T11). Responsable: Juan José Álvarez. Código en `director/partida.py`, `director/herramientas.py`, `director/directora.py` y `director/__main__.py`; pruebas en `tests/test_partida.py`, `tests/test_herramientas.py`, `tests/test_directora.py` y `tests/test_cli.py`. Las firmas y resultados son los de la sección 5 de [contratos.md](contratos.md).

## La partida

`Partida(semilla=42, max_ticks=300, mapa=None)` reúne lo de una partida de vela9:

- `env`: el entorno, iniciado con `env.reset(semilla)`.
- `alien`: el alienígena por reglas (`AlienReglas`, [alien.md](alien.md)); guarda las pistas.
- `avance`: `Avance(env, alien)`, que mueve la partida y registra eventos ([avance.md](avance.md)).
- `predictor`: `PredictorDestino(env.mapa)` ([prediccion.md](prediccion.md)).

Todas las herramientas leen y modifican esta misma partida, así que su estado persiste: si una pregunta da una pista o avanza la simulación, la siguiente lo ve.

**Sala en una puerta.** Las puertas no son de ninguna sala, pero las herramientas siempre informan una:

- Tripulante: la última casilla con sala de `env.trayectoria`.
- Alienígena: si está en una puerta, la sala de la casilla de atrás según `direccion_alien` (de donde viene); si esa casilla no tiene sala, la última sala registrada después de cada avance.

## Las 6 herramientas

`crear_herramientas(partida)` devuelve un diccionario nombre -> función con los parámetros exactos de `director/esquemas.py`. Todos los resultados son diccionarios serializables a JSON. Los errores esperables se lanzan como `ValueError` con un mensaje en español; `ejecutar_agente` los convierte en `{"error": ...}` para el modelo.

| Herramienta | Argumentos | Resultado | Errores |
|---|---|---|---|
| `estado_partida` | ninguno | `tick`, `tripulante` `{x, y, sala}`, `alienigena` `{x, y, sala, direccion}`, `pistas_restantes`, `capturado` | ninguno |
| `ruta_mas_corta` | `origen`, `destino` | `pasos`, `camino_resumido` | sala inexistente; sin camino |
| `predecir_destino` | ninguno | `sala`, `confianza`, `acercamiento_casillas`, `ticks_analizados` | ninguno |
| `ve_tripulante` | ninguno | `ve`, `distancia_casillas` | ninguno |
| `dar_pista` | `sala` | `sala`, `pistas_restantes` | sala inexistente; no quedan pistas |
| `avanzar_simulacion` | `ticks` (1 a 20) | `tick`, `ticks_avanzados`, `eventos`, `capturado` | ticks fuera de rango o no entero; partida terminada |

Detalles:

- **Nombres de sala.** Se comparan sin mayúsculas, tildes ni espacios repetidos con `Mapa.indice_sala` (D14): "medico" y "CORREDOR  a" sirven. Un nombre distinto, como "Enfermería", no se cambia por uno parecido (D12): da error con las salas válidas.
- **`estado_partida`.** `direccion` es "arriba", "derecha", "abajo" o "izquierda". `capturado` sigue la regla del entorno: alienígena y tripulante a distancia Manhattan de 1 o menos.
- **`ruta_mas_corta`.** `origen` y `destino` son nombres de sala o los personajes "tripulante" y "alienigena" (también "alienígena", sin importar mayúsculas). Personaje a personaje usa `ruta`; personaje a sala, `ruta_a_sala`; sala a personaje, `ruta_a_sala` desde el personaje (mismo largo). De sala a sala prueba `ruta_a_sala` desde cada casilla transitable de la sala de origen y se queda la más corta; en un empate gana la primera casilla en el orden de `mapa.transitables`. Eso cuesta una búsqueda por casilla de la sala (36 como máximo en vela9), unos milisegundos. `camino_resumido` lista las salas en orden, con "puerta" donde cruza una puerta y sin repetidos seguidos.
- **`ve_tripulante`.** `ve` es si la casilla del tripulante está en `env.campo_vision`; `distancia_casillas`, los pasos de A* del alienígena al tripulante.
- **`dar_pista`.** Resuelve el nombre y llama a `AlienReglas.dar_pista` con el nombre canónico, que revisa el presupuesto de 3 pistas y no gasta una si hay error.
- **`avanzar_simulacion`.** Llama a `Partida.avanzar`, que usa el avance con el alienígena por reglas y actualiza la última sala del alienígena.

## Ejemplo con las herramientas directamente

Sin modelo de lenguaje, con la semilla 42:

```python
from director import Partida, crear_herramientas

partida = Partida(semilla=42)
h = crear_herramientas(partida)
print(h["estado_partida"]())
print(h["ruta_mas_corta"]("alienigena", "tripulante"))
print(h["ruta_mas_corta"]("medico", "Hangar"))
print(h["ve_tripulante"]())
print(h["dar_pista"]("bodega"))
print(h["avanzar_simulacion"](20))
print(h["predecir_destino"]())
try:
    h["ruta_mas_corta"]("Enfermería", "Hangar")
except ValueError as error:
    print("error:", error)
```

Salida:

```
{'tick': 0, 'tripulante': {'x': 2, 'y': 12, 'sala': 'Bodega'}, 'alienigena': {'x': 1, 'y': 2, 'sala': 'Médico', 'direccion': 'abajo'}, 'pistas_restantes': 3, 'capturado': False}
{'pasos': 15, 'camino_resumido': ['Médico', 'puerta', 'Corredor A', 'puerta', 'Bodega']}
{'pasos': 20, 'camino_resumido': ['Médico', 'puerta', 'Laboratorio', 'Corredor B', 'puerta', 'Reactor', 'puerta', 'Hangar']}
{'ve': False, 'distancia_casillas': 15}
{'sala': 'Bodega', 'pistas_restantes': 2}
{'tick': 16, 'ticks_avanzados': 16, 'eventos': ['tick 6: el alienígena entró a Corredor A', 'tick 9: el alienígena vio al tripulante', 'tick 10: el alienígena perdió de vista al tripulante', 'tick 11: el alienígena vio al tripulante', 'tick 12: el alienígena entró a Bodega', 'tick 13: el alienígena perdió de vista al tripulante', 'tick 14: el alienígena vio al tripulante', 'tick 16: el alienígena capturó al tripulante'], 'capturado': True}
{'sala': 'Bodega', 'confianza': 0.0, 'acercamiento_casillas': 0, 'ticks_analizados': 10}
error: La sala 'Enfermería' no existe. Salas válidas: Médico, Laboratorio, Comunicaciones, Corredor A, Corredor B, Bodega, Reactor, Hangar. También se aceptan 'tripulante' y 'alienigena'.
```

De Médico al Hangar entre Laboratorio y Corredor B no aparece "puerta": la fila 5 tiene aberturas sin puerta (D6). Con la pista hacia Bodega, el alienígena va hacia allá, ve al tripulante en el tick 9, entra a Bodega persiguiéndolo en el tick 12 y lo captura en el 16, así que el avance se detiene antes de los 20 ticks pedidos.

## La directora

`Directora(semilla=42, cliente=None, config=None, limite=6, max_ticks=300)` arma la partida, las herramientas, los esquemas (`construir_esquemas`) y el prompt de sistema (`construir_prompt_sistema`). Si una función no coincide con su esquema (`validar_correspondencia`), lanza `ValueError` al crearse, no a mitad de una pregunta.

- `preguntar(pregunta)` llama a `ejecutar_agente` con el modelo y la temperatura de `config` y devuelve un `ResultadoAgente` ([contratos.md](contratos.md#6-agente)).
- Cada pregunta es independiente: el modelo no recibe el historial de las anteriores. La partida sí persiste entre preguntas.
- `reiniciar(semilla=None)` empieza una partida nueva (con la misma semilla si no se da otra).
- El cliente real del proveedor seleccionado se crea en la primera pregunta. Crear la directora, importar el paquete y correr las pruebas no necesita la clave.

```python
from director import Directora

directora = Directora(semilla=42)
resultado = directora.preguntar("¿En qué sala está el tripulante?")  # necesita la clave del proveedor
print(resultado.respuesta)
```

## El comando

```bash
python -m director "¿En qué sala está el tripulante?" --registro
python -m director "¿El alienígena ve al tripulante?" --semilla 7 --limite 4
python -m director
```

- Con una pregunta, imprime la respuesta. Con `--registro`, también cada llamada a herramienta con sus argumentos, resultado y tiempo, el número de llamadas y si se alcanzó el límite.
- Sin pregunta abre el modo interactivo (`> `): cada línea es una pregunta sobre la misma partida; `estado` muestra `estado_partida()` sin usar el modelo (útil para depurar) y `salir` termina.
- Si falta la clave del proveedor seleccionado, explica cómo configurarla con `.env.example` y termina con código 2, sin traza.
