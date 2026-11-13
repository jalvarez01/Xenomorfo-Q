# Casos de prueba de la directora (2026-11-12)

- Modelo: `gpt-5.4-nano`, temperatura 0.0
- Prompt: versión 1; límite 6 llamadas
- Semilla: 42 (cada caso en una partida nueva)

| Caso | Categoría | Llamadas | Límite alcanzado | Latencia (s) | Correcto |
|---|---|---|---|---|---|
| C5 | límite: sala inexistente | 1 | no | 2.438 | |

## C5: límite: sala inexistente

**Pregunta:** ¿Cuántos pasos hay desde la Enfermería hasta el Hangar?

**Herramientas esperadas:** ruta_mas_corta

**Resultado esperado:**

```json
{
  "error": "La sala 'Enfermería' no existe. Salas válidas: Médico, Laboratorio, Comunicaciones, Corredor A, Corredor B, Bodega, Reactor, Hangar. También se aceptan 'tripulante' y 'alienigena'."
}
```

**Llamadas:**

1. `ruta_mas_corta({"origen": "Enfermería", "destino": "Hangar"})` (error): `{"error": "ValueError: La sala 'Enfermería' no existe. Salas válidas: Médico, Laboratorio, Comunicaciones, Corredor A, Corredor B, Bodega, Reactor, Hangar. También se aceptan 'tripulante' y 'alienigena'."}`

**Respuesta:** “Enfermería” no existe en la estación. Las salas válidas son: Médico, Laboratorio, Comunicaciones, Corredor A, Corredor B, Bodega, Reactor, Hangar.

¿Te referías a **Médico**? Si me confirmas, te calculo los pasos hasta **Hangar**.

**Llamadas:** 1. **Límite alcanzado:** no. **Latencia:** 2.438 s.

**Valoración:** (pendiente)

**Correcto:** (pendiente)
