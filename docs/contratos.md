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
- `info` hoy: `{"tick", "capturado", "distancia_real"}`.
- **Planeado:** agregar a `info` las claves `estado_arbol` (estado del alienígena por reglas: persigue, va a la sala de la pista o patrulla) y `pista_activa` (si hay una pista vigente).

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

## 5. Herramientas del agente (planeado)

Funciones de Python en `director/herramientas.py` (T11) que el modelo de lenguaje puede pedir. Cada una devuelve un diccionario serializable a JSON. Los errores también se devuelven como diccionario `{"error": "<mensaje en español>"}` para que el modelo pueda leerlos y corregir. Los esquemas que ve el modelo se definen en T13.

Responsable general: Juan José Álvarez.

### 5.1 estado_partida

```text
estado_partida() -> {"tick", "tripulante": {"x", "y", "sala"}, "alienigena": {"x", "y", "sala", "direccion"}, "pistas_restantes", "capturado"}
```

- `sala` es el nombre de la sala (ver [entorno.md](entorno.md#salas)).
- Si el tripulante o el alienígena está en una puerta, 'sala' es la última sala visitada.

### 5.2 ruta_mas_corta

```text
ruta_mas_corta(origen: str, destino: str) -> {"pasos", "camino_resumido"}
```

- `origen` y `destino` son nombres de sala o los valores especiales `"tripulante"` y `"alienigena"`.
- Calcula la ruta con A* (T09). `camino_resumido` lista las salas y puertas por las que pasa.
- Si una sala no existe, devuelve un error que lista las salas válidas.

### 5.3 predecir_destino

Responsable: Santiago Meneses (T12).

```text
predecir_destino() -> {"sala", "confianza"}
```

- Heurística sobre los últimos 10 ticks del tripulante (`env.trayectoria`); no es un modelo entrenado.
- `confianza` va de 0 a 1.

### 5.4 ve_tripulante

```text
ve_tripulante() -> {"ve", "distancia_casillas"}
```

- Usa la visión del alienígena (T08).

### 5.5 dar_pista

```text
dar_pista(sala: str) -> {"sala", "pistas_restantes"}
```

- Máximo 3 pistas por partida.
- Devuelve un error si no quedan pistas o si la sala no existe.
- La pista es una sala, nunca una casilla exacta (D2 adaptada en D8). El alienígena reacciona a ella en T19.

### 5.6 avanzar_simulacion

Responsable: Santiago Meneses (T10).

```text
avanzar_simulacion(ticks: int) -> {"tick", "eventos", "capturado"}
```

- `ticks` va de 1 a 20; fuera de ese rango devuelve un error.
- `eventos` es una lista de textos cortos (por ejemplo, el alienígena vio al tripulante o cambió de sala).
- Se detiene antes si hay captura.

## 6. Agente (planeado)

Responsable: Emmanuel Castaño (T14 a T17).

- **Backend:** NVIDIA NIM con el cliente `openai` (compatible con OpenAI), `base_url = "https://integrate.api.nvidia.com/v1"`.
- **Modelo:** `meta/llama-3.3-70b-instruct`, cambiable con la variable de entorno `XQ_MODELO`.
- **Clave:** variable de entorno `NVIDIA_API_KEY`, cargada desde `.env` o desde los secretos de Colab. Nunca en el código.
- **Temperatura:** 0, para que los casos de prueba sean repetibles.
- **Límite:** máximo 6 llamadas a herramientas por pregunta. Al llegar al límite, el ciclo hace una última llamada al modelo sin herramientas y la respuesta debe decir que se alcanzó el límite.
- **Registro:** cada llamada se guarda como `{"paso", "herramienta", "argumentos", "resultado"}` en una lista que se devuelve junto con la respuesta final.
- **Pruebas:** usan un cliente falso que simula las respuestas del modelo; nunca llaman a la API real (T17).

## 7. Dataset

**Descartado (D8).** El agente consulta la simulación en vivo con sus herramientas, así que no se generan trayectorias ni se entrena ningún modelo.
