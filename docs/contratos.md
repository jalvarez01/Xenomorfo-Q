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

## 8. Agente

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
- Los resultados que no son `str` se envían con `json.dumps(..., ensure_ascii=False)`.

Contrato para las herramientas (T11, T12): funciones de Python con argumentos por nombre, serializables a JSON, que devuelven `str` o un valor serializable a JSON. Los errores esperables pueden lanzarse como excepción con un mensaje claro; el agente los convierte en JSON.

Configuración del LLM (`director/llm.py`):

| Variable | Por defecto | Uso |
|---|---|---|
| `NVIDIA_API_KEY` | (ninguno) | Obligatoria para `crear_cliente`; si falta, lanza `ClaveFaltanteError`. Nunca se sube al repositorio. |
| `XQ_MODELO` | `meta/llama-3.3-70b-instruct` | Nombre del modelo. |
| `XQ_URL_BASE` | `https://integrate.api.nvidia.com/v1` | Backend compatible con OpenAI. |
| `XQ_TEMPERATURA` | `0` | Temperatura; 0 para casos repetibles. |

```python
config = cargar_config()          # lee el entorno y .env si existe -> ConfigLLM(modelo, url_base, temperatura)
cliente = crear_cliente(config)   # openai.OpenAI; no hace llamadas de red al crearse
```

La plantilla de variables está en `.env.example`.
