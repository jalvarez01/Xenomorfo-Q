# Casos de prueba de la directora (2026-11-12)

- Modelo: `gpt-5.4-nano`, temperatura 0.0
- Prompt: versión 1; límite 6 llamadas
- Semilla: 42 (cada caso en una partida nueva)

| Caso | Categoría | Llamadas | Límite alcanzado | Latencia (s) | Correcto |
|---|---|---|---|---|---|
| C3 | habitual | 1 | no | 1.859 | |

## C3: habitual

**Pregunta:** ¿Hacia qué sala se dirige el tripulante?

**Herramientas esperadas:** predecir_destino

**Resultado esperado:**

```json
{
  "sala": "Bodega",
  "confianza": 0.0,
  "acercamiento_casillas": 0,
  "ticks_analizados": 0
}
```

**Llamadas:**

1. `predecir_destino({})`: `{"sala": "Bodega", "confianza": 0.0, "acercamiento_casillas": 0, "ticks_analizados": 0}`

**Respuesta:** El tripulante parece dirigirse a **Bodega**.

- **Confianza:** 0.0  
- **Acercamiento a esa sala:** 0 casillas  
- **Ticks analizados:** 0

**Llamadas:** 1. **Límite alcanzado:** no. **Latencia:** 1.859 s.

**Valoración:** (pendiente)

**Correcto:** (pendiente)
