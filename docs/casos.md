# Ejecutor de casos de prueba

Apoyo a T21: corre los 6 casos de prueba de la directora y guarda la evidencia. Código en `experiments/casos.py`, pruebas en `tests/test_casos.py`. Los casos, la valoración y el análisis (T20 a T23) son de Simón Mazo; el ejecutor solo hace el trabajo mecánico.

## Uso

```bash
python -m experiments.casos                 # semilla 42, resultados en experiments/resultados
python -m experiments.casos --semilla 7 --salida otra/carpeta
python -m experiments.casos --recomparar experiments/resultados/<archivo>.json   # sin el modelo
```

Necesita la clave del proveedor elegido con `XQ_PROVEEDOR` (ver `.env.example`). Sin la clave termina con código 2 y no escribe archivos.

Cada caso corre con una `Directora` nueva, en su propia partida con la misma semilla, así C4 (que da una pista y avanza) no cambia los demás. C3 es la excepción: usa su propia preparación (ver abajo).

## Los casos

| Caso | Categoría | Pregunta | Herramientas esperadas |
|---|---|---|---|
| C1 | habitual | ¿En qué sala está el tripulante y a cuántos pasos está el alienígena? | `estado_partida`, `ruta_mas_corta` |
| C2 | habitual | ¿El alienígena está viendo al tripulante en este momento? | `ve_tripulante` |
| C3 | habitual | ¿Hacia qué sala se dirige el tripulante? (partida preparada: semilla 0, 11 ticks) | `predecir_destino` |
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
C3 {'sala': 'Hangar', 'confianza': 0.5, 'acercamiento_casillas': 5, 'ticks_analizados': 10, 'sala_actual_tripulante': 'Corredor B'}
C4 {'sala_pista': 'Bodega', 'pistas_restantes': 2, 'pasos_antes': 15, 'pasos_despues': 6, 'se_acerco': True, 'capturado': False, 'eventos': ['tick 6: el alienígena entró a Corredor A', 'tick 9: el alienígena vio al tripulante', 'tick 10: el alienígena perdió de vista al tripulante']}
C5 {'error': "La sala 'Enfermería' no existe. Salas válidas: Médico, Laboratorio, Comunicaciones, Corredor A, Corredor B, Bodega, Reactor, Hangar. También se aceptan 'tripulante' y 'alienigena'."}
C6 {'pasos_por_sala': {'Médico': 0, 'Laboratorio': 8, 'Comunicaciones': 16, 'Corredor A': 6, 'Corredor B': 14, 'Bodega': 12, 'Reactor': 16, 'Hangar': 26}, 'llamadas_necesarias': 8, 'limite_alcanzado': True}
```

## Preparación de C3

Con la semilla 42, C3 se preguntaba en el tick 0, cuando el tripulante todavía no se había movido, y `predecir_destino` devolvía su sala actual con confianza 0: un caso trivial. Por eso un caso puede tener `"preparacion": {"semilla", "ticks"}`. Su partida usa esa semilla y avanza esos ticks con el alienígena por reglas (`preparar_partida`) antes de preguntar, y el valor esperado se calcula después de la misma preparación.

La preparación de C3 sale de `buscar_preparacion()`: recorre las semillas de 0 a 50 y, para cada una, de 5 a 15 ticks, en ese orden, y se queda con la primera combinación en la que no hubo captura y `predecir_destino` señala una sala distinta de la sala actual del tripulante con confianza de al menos 0.5. El resultado es la semilla 0 con 11 ticks: el tripulante está en el Corredor B y va hacia el Hangar con confianza 0.5 (5 casillas en 10 ticks). Hay 40 combinaciones que cumplen; `tests/test_casos.py` revisa que la guardada en `CASOS` sea la primera.

El valor esperado de C3 incluye `sala_actual_tripulante` para la valoración: una respuesta correcta da el destino (Hangar), no la sala donde ya está.

## Comparación automática y valoración sugerida

`comparar` busca en la respuesta cada dato esperado del caso (números y nombres, sin importar mayúsculas ni tildes) y `sugerir_valoracion` resume: **correcto** si coinciden todos, **parcial** si coinciden algunos e **incorrecto** si no coincide ninguno, con el motivo y las herramientas usadas. Los datos de cada caso:

| Caso | Datos comparados |
|---|---|
| C1 | sala del tripulante, pasos del alienígena al tripulante |
| C2 | si lo ve (busca la negación "no") |
| C3 | sala destino, confianza (acepta 0.5, 0,5 o 50 %) |
| C4 | sala de la pista, pistas restantes, pasos antes, pasos después, si se acercó |
| C5 | dice que la sala no existe, lista las 8 salas válidas, no calcula ninguna ruta |
| C6 | alcanza el límite, dice que lo alcanzó, y los pasos de cada sala que la respuesta informa (un número seguido de "paso" justo después del nombre) |

Es una comparación textual simple para revisar rápido; la valoración final (`valoracion` y `correcto`) la hace una persona. `--recomparar` vuelve a calcularla sobre un JSON guardado sin llamar al modelo, por ejemplo después de corregir una regla.

## Resultados de la corrida oficial

[experiments/resultados/casos_2026-11-12_prompt2_semilla42.md](../experiments/resultados/casos_2026-11-12_prompt2_semilla42.md) (y su `.json`): `gpt-5.4-nano`, temperatura 0, prompt versión 2, semilla 42 (C3 preparado con semilla 0 y 11 ticks).

| Caso | Llamadas | Límite | Latencia (s) | Comparación | Valoración sugerida |
|---|---|---|---|---|---|
| C1 | 3 | no | 2.9 | 2 de 2 | correcto |
| C2 | 1 | no | 1.5 | 1 de 1 | correcto |
| C3 | 1 | no | 2.1 | 2 de 2 | correcto |
| C4 | 4 | no | 4.9 | 3 de 5 | parcial: no dio la distancia inicial ni dijo si se acercó |
| C5 | 1 | no | 1.9 | 3 de 3 | correcto |
| C6 | 6 | sí | 4.4 | 7 de 7 | correcto |

**Estabilidad de C4.** En la corrida oficial C4 salió parcial: el modelo no midió la distancia antes de la pista y afirmó, sin razón, que `ve_tripulante` solo da la distancia cuando ve al tripulante (la herramienta la da siempre). Con el mismo prompt y temperatura 0, en otras 8 corridas (3 con `python -m director` y 5 con el ejecutor) midió 15 y 6 casillas y respondió que sí se acercó. La temperatura 0 reduce la variación pero no la elimina; la evidencia oficial se deja como salió.

## Archivos que produce

En la carpeta de salida, dos archivos con el mismo nombre base `casos_<fecha>_prompt<PROMPT_VERSION>_semilla<semilla>`:

- `.json`: `fecha`, `prompt_version`, `modelo`, `temperatura`, `semilla`, `limite` y `casos`. Cada caso trae `id`, `categoria`, `pregunta`, `herramientas_esperadas`, `preparacion` (si la tiene), `semilla_caso`, `resultado_esperado`, `comparacion`, `valoracion_sugerida`, `respuesta`, `llamadas` (herramienta, argumentos, resultado, segundos y si fue error), `numero_llamadas`, `limite_alcanzado`, `latencia_segundos`, y `valoracion` y `correcto` vacíos.
- `.md`: el mismo contenido, legible, con una tabla resumen y una sección por caso con "Valoración" y "Correcto" pendientes.

Los archivos nunca incluyen la clave ni ninguna variable de entorno; `tests/test_casos.py` lo comprueba con una clave falsa.
