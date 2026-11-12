# Ejecutor de casos de prueba

Apoyo a T21: corre los 6 casos de prueba de la directora y guarda la evidencia. Código en `experiments/casos.py`, pruebas en `tests/test_casos.py`. Los casos, la valoración y el análisis (T20 a T23) son de Simón Mazo; el ejecutor solo hace el trabajo mecánico.

## Uso

```bash
python -m experiments.casos                 # semilla 42, resultados en experiments/resultados
python -m experiments.casos --semilla 7 --salida otra/carpeta
```

Necesita `NVIDIA_API_KEY` (ver `.env.example`). Sin la clave termina con código 2 y no escribe archivos.

Cada caso corre con una `Directora` nueva, en su propia partida con la misma semilla, así C4 (que da una pista y avanza) no cambia los demás.

## Los casos

| Caso | Categoría | Pregunta | Herramientas esperadas |
|---|---|---|---|
| C1 | habitual | ¿En qué sala está el tripulante y a cuántos pasos está el alienígena? | `estado_partida`, `ruta_mas_corta` |
| C2 | habitual | ¿El alienígena está viendo al tripulante en este momento? | `ve_tripulante` |
| C3 | habitual | ¿Hacia qué sala se dirige el tripulante? | `predecir_destino` |
| C4 | varias herramientas y acción | El alienígena lleva rato perdido: dale una pista hacia la sala donde está el tripulante, avanza 10 ticks y dime si se acercó. | `estado_partida`, `dar_pista`, `avanzar_simulacion`, `ruta_mas_corta` |
| C5 | límite: sala inexistente | ¿Cuántos pasos hay desde la Enfermería hasta el Hangar? | `ruta_mas_corta` |
| C6 | extra: límite de llamadas | Calcula la distancia del alienígena a cada una de las 8 salas. | `ruta_mas_corta` |

C1 a C5 son los cinco que pide la rúbrica; C6 es adicional para mostrar el límite de llamadas ([propuesta.md](propuesta.md)).

## Valor esperado

`calcular_esperado(caso_id, semilla)` calcula la verdad de cada caso con las herramientas directamente, sin el modelo, sobre una partida nueva con la misma semilla. Con la semilla 42:

```python
from experiments.casos import CASOS, calcular_esperado

for caso in CASOS:
    print(caso["id"], calcular_esperado(caso["id"]))
```

Salida:

```
C1 {'sala_tripulante': 'Bodega', 'pasos_alienigena_tripulante': 15}
C2 {'ve': False, 'distancia_casillas': 15}
C3 {'sala': 'Bodega', 'confianza': 0.0, 'acercamiento_casillas': 0, 'ticks_analizados': 0}
C4 {'sala_pista': 'Bodega', 'pistas_restantes': 2, 'pasos_antes': 15, 'pasos_despues': 6, 'se_acerco': True, 'capturado': False, 'eventos': ['tick 6: el alienígena entró a Corredor A', 'tick 9: el alienígena vio al tripulante', 'tick 10: el alienígena perdió de vista al tripulante']}
C5 {'error': "La sala 'Enfermería' no existe. Salas válidas: Médico, Laboratorio, Comunicaciones, Corredor A, Corredor B, Bodega, Reactor, Hangar. También se aceptan 'tripulante' y 'alienigena'."}
C6 {'pasos_por_sala': {'Médico': 0, 'Laboratorio': 8, 'Comunicaciones': 16, 'Corredor A': 6, 'Corredor B': 14, 'Bodega': 12, 'Reactor': 16, 'Hangar': 26}, 'llamadas_necesarias': 8, 'limite_alcanzado': True}
```

Nota para la valoración: con la semilla 42, C3 se pregunta en el tick 0, cuando el tripulante todavía no se ha movido, así que `predecir_destino` devuelve su sala actual con confianza 0. Si se quiere que C3 muestre una predicción con movimiento, hay que avanzar la partida antes de preguntar o elegir otra semilla.

## Archivos que produce

En la carpeta de salida, dos archivos con el mismo nombre base `casos_<fecha>_prompt<PROMPT_VERSION>_semilla<semilla>`:

- `.json`: `fecha`, `prompt_version`, `modelo`, `temperatura`, `semilla`, `limite` y `casos`. Cada caso trae `id`, `categoria`, `pregunta`, `herramientas_esperadas`, `resultado_esperado`, `respuesta`, `llamadas` (herramienta, argumentos, resultado, segundos y si fue error), `numero_llamadas`, `limite_alcanzado`, `latencia_segundos`, y `valoracion` y `correcto` vacíos.
- `.md`: el mismo contenido, legible, con una tabla resumen y una sección por caso con "Valoración" y "Correcto" pendientes.

Los archivos nunca incluyen la clave ni ninguna variable de entorno; `tests/test_casos.py` lo comprueba con una clave falsa.
