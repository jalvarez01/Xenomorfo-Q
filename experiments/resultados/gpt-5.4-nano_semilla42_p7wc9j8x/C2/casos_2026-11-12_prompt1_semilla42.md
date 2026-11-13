# Casos de prueba de la directora (2026-11-12)

- Modelo: `gpt-5.4-nano`, temperatura 0.0
- Prompt: versión 1; límite 6 llamadas
- Semilla: 42 (cada caso en una partida nueva)

| Caso | Categoría | Llamadas | Límite alcanzado | Latencia (s) | Correcto |
|---|---|---|---|---|---|
| C2 | habitual | 1 | no | 1.989 | |

## C2: habitual

**Pregunta:** ¿El alienígena está viendo al tripulante en este momento?

**Herramientas esperadas:** ve_tripulante

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

**Llamadas:** 1. **Límite alcanzado:** no. **Latencia:** 1.989 s.

**Valoración:** (pendiente)

**Correcto:** (pendiente)
