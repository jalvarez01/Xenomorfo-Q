# Casos de prueba de la directora (2026-11-12)

- Modelo: `gpt-5.4-nano`, temperatura 0.0
- Prompt: versión 1; límite 6 llamadas
- Semilla: 42 (cada caso en una partida nueva)

| Caso | Categoría | Llamadas | Límite alcanzado | Latencia (s) | Correcto |
|---|---|---|---|---|---|
| C4 | varias herramientas y acción | 4 | no | 4.766 | |

## C4: varias herramientas y acción

**Pregunta:** El alienígena lleva rato perdido: dale una pista hacia la sala donde está el tripulante, avanza 10 ticks y dime si se acercó.

**Herramientas esperadas:** estado_partida, dar_pista, avanzar_simulacion, ruta_mas_corta

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

**Respuesta:** Listo: pista dada hacia **Bodega**. Quedan **2** pistas.

Avancé **10 ticks** (hasta el tick **10**). Eventos relevantes:
- tick 9: el alienígena **vio al tripulante**
- tick 10: el alienígena **perdió de vista** al tripulante

Ahora mismo, **no lo ve** (distancia: **6 casillas**).

**Llamadas:** 4. **Límite alcanzado:** no. **Latencia:** 4.766 s.

**Valoración:** (pendiente)

**Correcto:** (pendiente)
