# Casos de prueba de la directora (2026-11-12)

- Modelo: `gpt-5.4-nano`, temperatura 0.0
- Prompt: versión 1; límite 6 llamadas
- Semilla: 42 (cada caso en una partida nueva)

| Caso | Categoría | Llamadas | Límite alcanzado | Latencia (s) | Correcto |
|---|---|---|---|---|---|
| C6 | extra: límite de llamadas | 6 | sí | 4.707 | sí |

## C6: extra: límite de llamadas

**Pregunta:** Calcula la distancia del alienígena a cada una de las 8 salas.

**Herramientas esperadas:** ruta_mas_corta

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

**Respuesta:** Con la información ya obtenida:

- Médico: 0 casillas (camino: ["Médico"])
- Laboratorio: 8 casillas (camino: ["Médico", "puerta", "Laboratorio"])
- Comunicaciones: 16 casillas (camino: ["Médico", "puerta", "Laboratorio", "puerta", "Comunicaciones"])
- Corredor A: 6 casillas (camino: ["Médico", "puerta", "Corredor A"])
- Corredor B: 14 casillas (camino: ["Médico", "puerta", "Laboratorio", "Corredor B"])

No pude calcular las distancias a:
- Bodega
- Reactor
- Hangar

porque alcanzé el límite de llamadas a herramientas en esta pregunta (las 3 últimas rutas no se ejecutaron).

**Llamadas:** 6. **Límite alcanzado:** sí. **Latencia:** 4.707 s.

**Valoración:** Alcanzó el límite de seis llamadas y lo comunicó; las cinco distancias informadas coinciden con la referencia. Indicó que Bodega, Reactor y Hangar quedaron sin calcular, en lugar de inventar resultados.

**Correcto:** sí (comportamiento esperado al alcanzar el límite; la solicitud de ocho distancias quedó incompleta).
