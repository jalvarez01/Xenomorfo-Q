# Casos de prueba de la directora (2026-11-12)

- Modelo: `gpt-5.4-nano`, temperatura 0.0
- Prompt: versión 1; límite 6 llamadas
- Semilla: 42 (cada caso en una partida nueva)

| Caso | Categoría | Llamadas | Límite alcanzado | Latencia (s) | Correcto |
|---|---|---|---|---|---|
| C1 | habitual | 2 | no | 2.364 | |

## C1: habitual

**Pregunta:** ¿En qué sala está el tripulante y a cuántos pasos está el alienígena?

**Herramientas esperadas:** estado_partida, ruta_mas_corta

**Resultado esperado:**

```json
{
  "sala_tripulante": "Bodega",
  "pasos_alienigena_tripulante": 15
}
```

**Llamadas:**

1. `estado_partida({})`: `{"tick": 0, "tripulante": {"x": 2, "y": 12, "sala": "Bodega"}, "alienigena": {"x": 1, "y": 2, "sala": "Médico", "direccion": "abajo"}, "pistas_restantes": 3, "capturado": false}`
2. `ve_tripulante({})`: `{"ve": false, "distancia_casillas": 15}`

**Respuesta:** El tripulante está en **Bodega**.  
El alienígena está a **15 pasos/casillas** del tripulante (distancia: **15 casillas**).

**Llamadas:** 2. **Límite alcanzado:** no. **Latencia:** 2.364 s.

**Valoración:** (pendiente)

**Correcto:** (pendiente)
