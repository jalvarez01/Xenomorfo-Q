# Contratos

Interfaces acordadas entre módulos. Cada sección indica su estado:

- **Existe (v0):** implementado hoy y cubierto por pruebas.
- **Planeado:** acordado pero sin implementar; puede ajustarse en la tarea indicada.

Cambiar un contrato requiere actualizar este archivo en el mismo Pull Request.

## 1. Entorno

**Existe (v0)**, en `sim/env.py`. Responsable: Juan José Álvarez.

```python
EstacionEnv(mapa, max_ticks=300, distancia_inicial=10, semilla=None)
obs = env.reset(semilla)                              # np.ndarray (4, alto, ancho) float32
obs, recompensa, terminado, info = env.step(accion)
```

- `mapa`: un `Mapa` o la ruta a un archivo de mapa. Por defecto `data/mapas/vela9.txt`.
- `info` hoy: `{"tick", "capturado", "distancia_real", "ve_tripulante"}`. `ve_tripulante` es `True` si el tripulante está en el campo de visión del alienígena al final del tick.
- Atributos de visión (T08): `direccion_alien`, la dirección `(dx, dy)` hacia la que mira el alienígena (`(0, 1)` al empezar; cambia con las acciones 0 a 3 aunque choque y no cambia con la 4), y `campo_vision`, matriz booleana `(alto, ancho)` con las casillas que ve, recalculada en `reset()` y en cada tick.
- Funciones públicas para T11 y T18: en `sim/percepcion.py`, `linea_de_vista(mapa, origen, destino)`, `ve_casilla(mapa, pos, direccion, casilla)` y `campo_de_vision(mapa, pos, direccion)`; en `sim/rutas.py`, `ruta(mapa, origen, destino)` y `ruta_a_sala(mapa, origen, sala)`, que devuelven la lista de casillas (pasos = `len(camino) - 1`) o `None` si no hay camino. Reglas en [entorno.md](entorno.md#visión) y [entorno.md](entorno.md#rutas-con-a).
- El estado del alienígena por reglas y la pista vigente no van en `info`: son atributos de `AlienReglas` (`estado` y `pista_activa`), ver la sección 8.

## 2. Acciones

**Existe (v0).**

| Acción | Significado |
|---|---|
| 0 | arriba |
| 1 | derecha |
| 2 | abajo |
| 3 | izquierda |
| 4 | revisar casillero contiguo |

En v0 la acción 4 siempre cuenta como casillero vacío; esconderse en casilleros no está en el plan actual.

## 3. Observación

Se conserva para la simulación; el agente no usa la observación ni la recompensa (D8).

**Existe (v0)** con las capas 1 y 3 en su forma provisional.

Tensor `(4, alto, ancho)` en `float32`:

| Capa | Contenido | v0 |
|---|---|---|
| 0 | Paredes: 1 pared, 0.5 casillero, 0 libre | Completa |
| 1 | Creencia sobre la posición del tripulante; suma 1 | Uniforme sobre las casillas libres |
| 2 | Posición del alienígena (one-hot) | Completa |
| 3 | Pista de la directora como mapa de calor de zona | Ceros |

## 4. Recompensa

Se conserva para la simulación; el agente no usa la observación ni la recompensa (D8).

**Existe (v0).**

- `+100` por captura, y el episodio termina.
- `-1` por cada tick.
- `-5` adicional por revisar un casillero vacío.
- El episodio termina sin captura al llegar a `max_ticks`.

Una captura en un tick con movimiento da `99.0` (100 - 1).

## 5. Herramientas del agente

**Existe (T11)**, en `director/herramientas.py` con `crear_herramientas(partida)`. Detalle, partida y ejemplos en [herramientas.md](herramientas.md).

Funciones de Python que el modelo de lenguaje puede pedir. Cada una devuelve un diccionario serializable a JSON. Los errores también se devuelven como diccionario `{"error": "<mensaje en español>"}` para que el modelo pueda leerlos y corregir. Los esquemas que ve el modelo están en `director/esquemas.py` (**Existe**, T13): `construir_esquemas(nombres_salas)` y `validar_correspondencia(esquemas, herramientas)`; las salas son texto libre, sin enum (D12).

Los nombres de sala se comparan sin mayúsculas, tildes ni espacios repetidos con `Mapa.indice_sala` (D14): "medico" o "corredor a" sirven, pero un nombre distinto no se cambia por uno parecido (D12). Los errores esperables se lanzan como `ValueError` y el agente los convierte en `{"error": ...}`.

Responsable general: Juan José Álvarez.

### 5.1 estado_partida

**Existe (T11).** Ver [herramientas.md](herramientas.md#las-6-herramientas).

```text
estado_partida() -> {"tick", "tripulante": {"x", "y", "sala"}, "alienigena": {"x", "y", "sala", "direccion"}, "pistas_restantes", "capturado"}
```

- `sala` es el nombre de la sala (ver [entorno.md](entorno.md#salas)).
- Si el tripulante o el alienígena está en una puerta, 'sala' es la última sala visitada.
- `direccion` es "arriba", "derecha", "abajo" o "izquierda".

### 5.2 ruta_mas_corta

**Existe (T11)**, sobre `sim/rutas.py` (T09). Ver [herramientas.md](herramientas.md#las-6-herramientas) y [entorno.md](entorno.md#rutas-con-a).

```text
ruta_mas_corta(origen: str, destino: str) -> {"pasos", "camino_resumido"}
```

- `origen` y `destino` son nombres de sala o los valores especiales `"tripulante"` y `"alienigena"`.
- Calcula la ruta con A* (T09). `camino_resumido` lista las salas por las que pasa, con "puerta" donde cruza una puerta y sin repetidos seguidos.
- `"alienigena"` también se acepta con tilde y en mayúsculas. De sala a sala, la ruta es la más corta entre cualquier casilla de las dos salas.
- Si una sala no existe, devuelve un error que lista las salas válidas.

### 5.3 predecir_destino

Responsable: Santiago Meneses (T12). **Existe (T11)**, sobre `director/prediccion.py` (T12). Ver [herramientas.md](herramientas.md#las-6-herramientas) y [prediccion.md](prediccion.md).

```text
predecir_destino() -> {"sala", "confianza", "acercamiento_casillas", "ticks_analizados"}
```

- `acercamiento_casillas`: pasos que el tripulante se acercó a la sala estimada en la ventana. `ticks_analizados`: ticks usados (10, o menos al inicio de la partida).

- Heurística sobre los últimos 10 ticks del tripulante (`env.trayectoria`); no es un modelo entrenado.
- `confianza` va de 0 a 1.

### 5.4 ve_tripulante

**Existe (T11)**, sobre `sim/percepcion.py` (T08). Ver [herramientas.md](herramientas.md#las-6-herramientas) y [entorno.md](entorno.md#visión).

```text
ve_tripulante() -> {"ve", "distancia_casillas"}
```

- `ve` es si el tripulante está en `env.campo_vision`; `distancia_casillas`, los pasos de A* del alienígena al tripulante.

### 5.5 dar_pista

**Existe (T11).** Ver [herramientas.md](herramientas.md#las-6-herramientas).

```text
dar_pista(sala: str) -> {"sala", "pistas_restantes"}
```

- Máximo 3 pistas por partida.
- Devuelve un error si no quedan pistas o si la sala no existe.
- La pista es una sala, nunca una casilla exacta (D2 adaptada en D8).
- **Base existe:** `AlienReglas.dar_pista(sala)` en `alien/reglas.py` (T19) lleva el presupuesto y devuelve este resultado; la herramienta (T11) resuelve el nombre con `Mapa.indice_sala` y la llama con el nombre canónico. Ver la sección 8.

### 5.6 avanzar_simulacion

Responsable: Santiago Meneses (T10). **Existe (T11)**, sobre `sim/avance.py` (T10). Ver [herramientas.md](herramientas.md#las-6-herramientas) y [avance.md](avance.md).

```text
avanzar_simulacion(ticks: int) -> {"tick", "ticks_avanzados", "eventos", "capturado"}
```

- `ticks` va de 1 a 20; fuera de ese rango devuelve un error.
- `ticks_avanzados` es menor que `ticks` si la partida terminó antes.
- `eventos` es una lista de textos cortos con el formato `"tick N: ..."` (por ejemplo, el alienígena entró a una sala o capturó al tripulante).
- Se detiene antes si hay captura o si se acaba el tiempo de la partida.
- La partida (`director/partida.py`) crea un `Avance(env, alien)` con `alien = AlienReglas(env)` (T18) como política, y la herramienta lo usa.
- Si la política tiene un método `tomar_eventos()`, sus eventos se agregan al registro; así llega `"tick N: el alienígena llegó a <sala>, la sala de la pista"`.

## 6. Agente

**Existe**, en `director/agente.py` y `director/llm.py` (T14, T15; pruebas en T17).

```python
ejecutar_agente(
    pregunta: str,
    herramientas: dict[str, Callable[..., Any]],   # nombre -> función de Python
    esquemas: list[dict],                          # formato "tools" de OpenAI
    cliente,                                       # objeto con chat.completions.create(**kwargs)
    modelo: str,
    prompt_sistema: str,
    limite: int = 6,
    temperatura: float = 0.0,
    *,
    max_turnos: int | None = None,                 # por defecto limite + 2
) -> ResultadoAgente

ResultadoAgente(respuesta: str, registro: list[RegistroLlamada], limite_alcanzado: bool, llamadas: int)
RegistroLlamada(herramienta: str, argumentos: dict, resultado: str, segundos: float, error: bool)
formatear_registro(registro) -> str
```

Regla del límite (ver [D9](decisiones.md#d9-el-límite-de-llamadas-cuenta-herramientas-ejecutadas)):

- `limite` cuenta herramientas ejecutadas, no turnos del modelo. Varias `tool_calls` en un turno suman una cada una.
- Si el límite se agota a mitad de turno, las `tool_calls` restantes no se ejecutan, no cuentan ni entran al registro, pero reciben un mensaje `tool` con `{"error": "No ejecutada: se alcanzó el límite de llamadas"}`.
- Al agotar el límite, o el tope de turnos `max_turnos`, se hace una última llamada **sin** `tools` pidiendo responder con lo ya obtenido y declarar el límite. El resultado sale con `limite_alcanzado=True`.
- Los errores nunca rompen el ciclo; llegan al modelo como JSON y quedan en el registro con `error=True`:
  - herramienta inexistente: `{"error": ..., "herramientas_validas": [...]}` (cuenta como llamada);
  - argumentos que no son JSON o no corresponden a la firma: `{"error": ...}`;
  - excepción dentro de la herramienta: `{"error": "<tipo>: <mensaje>"}`.
  - resultado de tipo `dict` con la clave `"error"`: se envía al modelo tal cual y queda en el registro con `error=True`.
- Los resultados que no son `str` se envían con `json.dumps(..., ensure_ascii=False)`.

Contrato para las herramientas (T11, T12): funciones de Python con argumentos por nombre, serializables a JSON, que devuelven `str` o un valor serializable a JSON. Para los errores esperables se admiten dos estilos: lanzar una excepción con un mensaje claro (el agente la convierte en JSON) o devolver `{"error": ...}`. En ambos casos el registro queda con `error=True`.

Configuración del LLM (`director/llm.py`):

El proveedor es configurable (D15): OpenAI es el principal y NVIDIA NIM queda como alternativa gratuita.

| Variable | Por defecto | Uso |
|---|---|---|
| `XQ_PROVEEDOR` | `openai` | `openai` o `nvidia`. Elige la clave, la URL y el modelo por defecto. |
| `OPENAI_API_KEY` | (ninguno) | Clave de OpenAI; obligatoria para `crear_cliente` con `openai`. Si falta, lanza `ClaveFaltanteError`. |
| `NVIDIA_API_KEY` | (ninguno) | Clave de NVIDIA NIM; obligatoria para `crear_cliente` con `nvidia`. |
| `XQ_MODELO` | `gpt-5.4-nano` (openai) o `openai/gpt-oss-20b` (nvidia) | Nombre del modelo. |
| `XQ_URL_BASE` | la de OpenAI (openai) o `https://integrate.api.nvidia.com/v1` (nvidia) | Backend compatible con OpenAI. |
| `XQ_TEMPERATURA` | `0` | Temperatura; 0 para casos repetibles. |

Las claves nunca se suben al repositorio ni se imprimen; el mensaje de `ClaveFaltanteError` solo nombra la variable del proveedor elegido.

```python
config = cargar_config()          # lee el entorno y .env si existe -> ConfigLLM(modelo, url_base, temperatura, proveedor)
cliente = crear_cliente(config)   # openai.OpenAI; no hace llamadas de red al crearse
```

La plantilla de variables está en `.env.example`.

### Prompt de sistema

**Existe**, en `director/prompt.py` (T16).

```python
construir_prompt_sistema(nombres_salas: list[str], limite: int = 6, pistas_max: int = 3) -> str
PROMPT_VERSION = "1"
```

- El texto se genera con las salas del mapa, el límite y las pistas; no lleva esos valores escritos a mano. `limite` debe ser el mismo que se pasa a `ejecutar_agente`.
- `PROMPT_VERSION` se sube cada vez que cambia la plantilla, y cada caso de prueba (T21) registra la versión usada.
- Regla de salas inexistentes: el modelo pasa el nombre tal como lo dijo el usuario. Si la herramienta responde que la sala no existe, la directora lo dice, lista las salas válidas y puede preguntar por un nombre parecido, pero no calcula ni inventa una ruta para la sala sugerida hasta que el usuario lo confirme.

## 7. Dataset

**Descartado (D8).** El agente consulta la simulación en vivo con sus herramientas, así que no se generan trayectorias ni se entrena ningún modelo.

## 8. Alienígena por reglas

**Existe**, en `alien/reglas.py` (T18, T19). Responsable: Santiago Meneses. Detalle en [alien.md](alien.md).

```python
alien = AlienReglas(env)            # uno por partida, después de env.reset()
accion = alien.decidir()            # o alien(env): sirve como política de Avance
alien.dar_pista(sala: str) -> {"sala", "pistas_restantes"}
alien.tomar_eventos() -> list[str]  # eventos desde la última llamada; Avance los usa
alien.estado                        # "persigue", "va a la pista" o "patrulla"
alien.pista_activa                  # nombre de la sala de la pista vigente, o None
alien.pistas_restantes              # de 3 a 0
```

- Reglas, en orden: si ve al tripulante lo persigue; si lo perdió de vista va a la última casilla donde lo vio; si hay pista va al centro de esa sala; si no, patrulla los centros de las salas. Se mueve con `ruta` (A*, T09).
- Solo usa la posición del tripulante cuando está en `env.campo_vision`.
- `dar_pista` lanza `ValueError` si no quedan pistas o la sala no existe (con la lista de salas válidas), sin gastar la pista. El nombre se compara sin mayúsculas ni espacios en los extremos.
- Requiere un mapa con salas; si no tiene, `AlienReglas(env)` lanza `ValueError`.
