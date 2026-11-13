# Casos de prueba de la directora (2026-11-12)

- Modelo: `gpt-5.4-nano`, temperatura 0.0
- Prompt: versión 2; límite 6 llamadas
- Semilla: 42 (cada caso en una partida nueva; los casos con preparación usan la suya)

| Caso | Categoría | Llamadas | Límite alcanzado | Latencia (s) | Comparación automática | Valoración sugerida | Correcto |
|---|---|---|---|---|---|---|---|
| C1 | habitual | 3 | no | 2.888 | 2 de 2 | correcto | |
| C2 | habitual | 1 | no | 1.518 | 1 de 1 | correcto | |
| C3 | habitual | 1 | no | 2.102 | 2 de 2 | correcto | |
| C4 | varias herramientas y acción | 4 | no | 4.895 | 3 de 5 | parcial | |
| C5 | límite: sala inexistente | 1 | no | 1.929 | 3 de 3 | correcto | |
| C6 | extra: límite de llamadas | 6 | sí | 4.417 | 7 de 7 | correcto | |

## C1: habitual

**Pregunta:** ¿En qué sala está el tripulante y a cuántos pasos está el alienígena?

**Herramientas esperadas:** estado_partida, ruta_mas_corta

**Partida:** semilla 42, sin preparación.

**Resultado esperado:**

```json
{
  "sala_tripulante": "Bodega",
  "pasos_alienigena_tripulante": 15
}
```

**Llamadas:**

1. `estado_partida({})`: `{"tick": 0, "tripulante": {"x": 2, "y": 12, "sala": "Bodega"}, "alienigena": {"x": 1, "y": 2, "sala": "Médico", "direccion": "abajo"}, "pistas_restantes": 3, "capturado": false}`
2. `ruta_mas_corta({"origen": "alienigena", "destino": "tripulante"})`: `{"pasos": 15, "camino_resumido": ["Médico", "puerta", "Corredor A", "puerta", "Bodega"]}`
3. `ve_tripulante({})`: `{"ve": false, "distancia_casillas": 15}`

**Respuesta:** - El tripulante está en **Bodega**.
- El alienígena está a **15 pasos** del tripulante (ruta más corta: **Médico → Corredor A → Bodega**).

**Llamadas:** 3. **Límite alcanzado:** no. **Latencia:** 2.888 s.

**Comparación automática:**

| Dato | Esperado | Obtenido | Coincide |
|---|---|---|---|
| sala del tripulante | Bodega | mencionado | sí |
| pasos del alienígena al tripulante | 15 | mencionado | sí |

**Valoración sugerida:** correcto: coinciden los 2 datos esperados; usó estado_partida, ruta_mas_corta, ve_tripulante.

**Valoración:** (pendiente)

**Correcto:** (pendiente)

## C2: habitual

**Pregunta:** ¿El alienígena está viendo al tripulante en este momento?

**Herramientas esperadas:** ve_tripulante

**Partida:** semilla 42, sin preparación.

**Resultado esperado:**

```json
{
  "ve": false,
  "distancia_casillas": 15
}
```

**Llamadas:**

1. `ve_tripulante({})`: `{"ve": false, "distancia_casillas": 15}`

**Respuesta:** No. En este momento el alienígena **no** está viendo al tripulante.  
Distancia actual: **15 casillas**.

**Llamadas:** 1. **Límite alcanzado:** no. **Latencia:** 1.518 s.

**Comparación automática:**

| Dato | Esperado | Obtenido | Coincide |
|---|---|---|---|
| lo ve | no | mencionado | sí |

**Valoración sugerida:** correcto: coinciden los 1 datos esperados; usó ve_tripulante.

**Valoración:** (pendiente)

**Correcto:** (pendiente)

## C3: habitual

**Pregunta:** ¿Hacia qué sala se dirige el tripulante?

**Herramientas esperadas:** predecir_destino

**Partida:** semilla 0, preparada avanzando 11 ticks con el alienígena por reglas antes de preguntar.

**Resultado esperado:**

```json
{
  "sala": "Hangar",
  "confianza": 0.5,
  "acercamiento_casillas": 5,
  "ticks_analizados": 10,
  "sala_actual_tripulante": "Corredor B"
}
```

**Llamadas:**

1. `predecir_destino({})`: `{"sala": "Hangar", "confianza": 0.5, "acercamiento_casillas": 5, "ticks_analizados": 10}`

**Respuesta:** El tripulante parece dirigirse a **Hangar**.

- **Confianza:** 0.5  
- **Acercamiento (casillas) en la ventana:** 5  
- **Ticks analizados:** 10

**Llamadas:** 1. **Límite alcanzado:** no. **Latencia:** 2.102 s.

**Comparación automática:**

| Dato | Esperado | Obtenido | Coincide |
|---|---|---|---|
| sala destino | Hangar | mencionado | sí |
| confianza | 0.5 | mencionado | sí |

**Valoración sugerida:** correcto: coinciden los 2 datos esperados; usó predecir_destino.

**Valoración:** (pendiente)

**Correcto:** (pendiente)

## C4: varias herramientas y acción

**Pregunta:** El alienígena lleva rato perdido: dale una pista hacia la sala donde está el tripulante, avanza 10 ticks y dime si se acercó.

**Herramientas esperadas:** estado_partida, dar_pista, avanzar_simulacion, ruta_mas_corta

**Partida:** semilla 42, sin preparación.

**Resultado esperado:**

```json
{
  "sala_pista": "Bodega",
  "pistas_restantes": 2,
  "pasos_antes": 15,
  "pasos_despues": 6,
  "se_acerco": true,
  "capturado": false,
  "eventos": [
    "tick 6: el alienígena entró a Corredor A",
    "tick 9: el alienígena vio al tripulante",
    "tick 10: el alienígena perdió de vista al tripulante"
  ]
}
```

**Llamadas:**

1. `estado_partida({})`: `{"tick": 0, "tripulante": {"x": 2, "y": 12, "sala": "Bodega"}, "alienigena": {"x": 1, "y": 2, "sala": "Médico", "direccion": "abajo"}, "pistas_restantes": 3, "capturado": false}`
2. `dar_pista({"sala": "Bodega"})`: `{"sala": "Bodega", "pistas_restantes": 2}`
3. `avanzar_simulacion({"ticks": 10})`: `{"tick": 10, "ticks_avanzados": 10, "eventos": ["tick 6: el alienígena entró a Corredor A", "tick 9: el alienígena vio al tripulante", "tick 10: el alienígena perdió de vista al tripulante"], "capturado": false}`
4. `ve_tripulante({})`: `{"ve": false, "distancia_casillas": 6}`

**Respuesta:** - Pista dada: **Bodega**. Pistas restantes: **2**.
- Avancé **10 ticks** (hasta tick **10**). Eventos:  
  - tick 6: el alienígena entró a **Corredor A**  
  - tick 9: el alienígena **vio al tripulante**  
  - tick 10: el alienígena **perdió de vista** al tripulante
- ¿Se acercó? **No puedo confirmarlo** con números: ahora mismo **no lo ve** (ve=false) y la herramienta solo me da distancia cuando lo ve.

**Llamadas:** 4. **Límite alcanzado:** no. **Latencia:** 4.895 s.

**Comparación automática:**

| Dato | Esperado | Obtenido | Coincide |
|---|---|---|---|
| sala de la pista | Bodega | mencionado | sí |
| pistas restantes | 2 | mencionado | sí |
| pasos antes | 15 | no mencionado | no |
| pasos después | 6 | mencionado | sí |
| se acercó | sí | no mencionado | no |

**Valoración sugerida:** parcial: no coincide pasos antes, se acercó; usó estado_partida, dar_pista, avanzar_simulacion, ve_tripulante.

**Valoración:** (pendiente)

**Correcto:** (pendiente)

## C5: límite: sala inexistente

**Pregunta:** ¿Cuántos pasos hay desde la Enfermería hasta el Hangar?

**Herramientas esperadas:** ruta_mas_corta

**Partida:** semilla 42, sin preparación.

**Resultado esperado:**

```json
{
  "error": "La sala 'Enfermería' no existe. Salas válidas: Médico, Laboratorio, Comunicaciones, Corredor A, Corredor B, Bodega, Reactor, Hangar. También se aceptan 'tripulante' y 'alienigena'."
}
```

**Llamadas:**

1. `ruta_mas_corta({"origen": "Enfermería", "destino": "Hangar"})` (error): `{"error": "ValueError: La sala 'Enfermería' no existe. Salas válidas: Médico, Laboratorio, Comunicaciones, Corredor A, Corredor B, Bodega, Reactor, Hangar. También se aceptan 'tripulante' y 'alienigena'."}`

**Respuesta:** La sala **“Enfermería”** no existe en esta estación. Las salas válidas son: **Médico, Laboratorio, Comunicaciones, Corredor A, Corredor B, Bodega, Reactor, Hangar**.

¿Te refieres a **“Médico”**? Si confirmas, te digo los pasos exactos hasta **Hangar**.

**Llamadas:** 1. **Límite alcanzado:** no. **Latencia:** 1.929 s.

**Comparación automática:**

| Dato | Esperado | Obtenido | Coincide |
|---|---|---|---|
| dice que la sala no existe | no existe | mencionado | sí |
| lista las 8 salas válidas | 8 salas | mencionado | sí |
| no calcula una ruta | ninguna ruta calculada | mencionado | sí |

**Valoración sugerida:** correcto: coinciden los 3 datos esperados; usó ruta_mas_corta.

**Valoración:** (pendiente)

**Correcto:** (pendiente)

## C6: extra: límite de llamadas

**Pregunta:** Calcula la distancia del alienígena a cada una de las 8 salas.

**Herramientas esperadas:** ruta_mas_corta

**Partida:** semilla 42, sin preparación.

**Resultado esperado:**

```json
{
  "pasos_por_sala": {
    "Médico": 0,
    "Laboratorio": 8,
    "Comunicaciones": 16,
    "Corredor A": 6,
    "Corredor B": 14,
    "Bodega": 12,
    "Reactor": 16,
    "Hangar": 26
  },
  "llamadas_necesarias": 8,
  "limite_alcanzado": true
}
```

**Llamadas:**

1. `estado_partida({})`: `{"tick": 0, "tripulante": {"x": 2, "y": 12, "sala": "Bodega"}, "alienigena": {"x": 1, "y": 2, "sala": "Médico", "direccion": "abajo"}, "pistas_restantes": 3, "capturado": false}`
2. `ruta_mas_corta({"origen": "alienigena", "destino": "Médico"})`: `{"pasos": 0, "camino_resumido": ["Médico"]}`
3. `ruta_mas_corta({"origen": "alienigena", "destino": "Laboratorio"})`: `{"pasos": 8, "camino_resumido": ["Médico", "puerta", "Laboratorio"]}`
4. `ruta_mas_corta({"origen": "alienigena", "destino": "Comunicaciones"})`: `{"pasos": 16, "camino_resumido": ["Médico", "puerta", "Laboratorio", "puerta", "Comunicaciones"]}`
5. `ruta_mas_corta({"origen": "alienigena", "destino": "Corredor A"})`: `{"pasos": 6, "camino_resumido": ["Médico", "puerta", "Corredor A"]}`
6. `ruta_mas_corta({"origen": "alienigena", "destino": "Corredor B"})`: `{"pasos": 14, "camino_resumido": ["Médico", "puerta", "Laboratorio", "Corredor B"]}`

**Respuesta:** Con la información ya obtenida (y **alcanzando el límite de llamadas a herramientas**), solo tengo distancias/rutas calculadas para estas salas:

- **Médico**: 0 pasos (camino: Médico)
- **Laboratorio**: 8 pasos (camino: Médico → puerta → Laboratorio)
- **Comunicaciones**: 16 pasos (camino: Médico → puerta → Laboratorio → puerta → Comunicaciones)
- **Corredor A**: 6 pasos (camino: Médico → puerta → Corredor A)
- **Corredor B**: 14 pasos (camino: Médico → puerta → Laboratorio → Corredor B)

Para las otras 3 salas (**Bodega**, **Reactor**, **Hangar**) **no se pudo calcular** porque se alcanzó el límite de llamadas a herramientas antes de obtener sus resultados.

**Llamadas:** 6. **Límite alcanzado:** sí. **Latencia:** 4.417 s.

**Comparación automática:**

| Dato | Esperado | Obtenido | Coincide |
|---|---|---|---|
| alcanza el límite | True | mencionado | sí |
| dice que alcanzó el límite | límite | mencionado | sí |
| pasos a Médico | 0 | 0 | sí |
| pasos a Laboratorio | 8 | 8 | sí |
| pasos a Comunicaciones | 16 | 16 | sí |
| pasos a Corredor A | 6 | 6 | sí |
| pasos a Corredor B | 14 | 14 | sí |

**Valoración sugerida:** correcto: coinciden los 7 datos esperados; usó estado_partida, ruta_mas_corta.

**Valoración:** (pendiente)

**Correcto:** (pendiente)
