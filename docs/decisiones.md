# Registro de decisiones

Cada entrada registra una decisión de diseño. Las decisiones nuevas van al final. Si una decisión se reemplaza, no se borra: se marca como reemplazada y se enlaza la nueva.

## D1. La directora se entrena aparte y se congela antes del DQN

- **Fecha:** 2026-10-28
- **Decisión:** la directora se entrena con aprendizaje supervisado y se congela antes de entrenar el DQN del alienígena.
- **Motivo:** entrenar ambos a la vez es inestable: el alienígena aprende a depender de pistas que siguen cambiando mientras la directora aprende.
- **Alternativas descartadas:** entrenamiento conjunto de directora y alienígena; directora que aprende por refuerzo junto al alienígena.

## D2. Las pistas son zonas, nunca la casilla exacta

- **Fecha:** 2026-10-28
- **Decisión:** una pista indica las casillas de la sala más probable, no la posición exacta del tripulante.
- **Motivo:** si la pista diera la casilla exacta, el alienígena aprendería a seguirla y nunca a usar su propia percepción.
- **Alternativas descartadas:** dar la casilla exacta; dar solo una dirección general.

## D3. El dataset se separa por partida, no por fila

- **Fecha:** 2026-10-28
- **Decisión:** la separación en entrenamiento, validación y prueba se hace por `partida_id`.
- **Motivo:** las filas de una misma partida son casi idénticas entre ticks seguidos. Separar por fila filtra información de prueba al entrenamiento y da métricas infladas.
- **Alternativas descartadas:** separación aleatoria por fila.

## D4. Se evalúa en mapas no vistos

- **Fecha:** 2026-10-28
- **Decisión:** los mapas de prueba no se usan en ningún entrenamiento.
- **Motivo:** evita que la directora memorice la distribución de un mapa en vez de aprender a leer la trayectoria.
- **Alternativas descartadas:** evaluar en los mismos mapas de entrenamiento con partidas nuevas.

## D5. Interfaz tipo Gym para el entorno

- **Fecha:** 2026-10-28
- **Decisión:** el entorno expone `reset(semilla)` y `step(accion)` con la forma de Gym.
- **Motivo:** fija un contrato estable desde el inicio y permite trabajar en paralelo en la simulación, la directora y el alienígena.
- **Alternativas descartadas:** usar Gymnasium como dependencia; un bucle de simulación propio sin interfaz fija.

## D6. Las salas se definen con un archivo de anotación por mapa

- **Fecha:** 2026-10-29
- **Decisión:** cada mapa tiene un archivo `<mapa>_salas.txt` que asigna a mano un índice de sala a cada casilla de piso o casillero. `Mapa` lo valida al cargarlo y expone `sala(x, y)`.
- **Motivo:** la directora (T15) y la columna `sala_destino` del dataset necesitan salas fijas y con nombre. En `vela9.txt` la fila 5 tiene aberturas sin puerta, así que las salas no se pueden deducir de las puertas.
- **Alternativas descartadas:** componentes conectadas separadas por puertas (en vela9 da 6 zonas, no 8 salas); agregar puertas al mapa para cerrar las aberturas (cambia la jugabilidad del prototipo).

## D7. Parámetros de visión del alienígena

- **Fecha:** 2026-11-04
- **Decisión:** el alienígena ve hasta 7.5 casillas (15 m), en un cono de unos 127 grados (coseno mínimo 0.45) hacia donde mira, y a menos de 1.5 casillas en cualquier dirección. Solo las paredes tapan la vista; las puertas y los casilleros no. La línea de vista usa Bresenham desde el alienígena hacia la casilla. Detalle en [entorno.md](entorno.md#visión).
- **Motivo:** son los mismos parámetros del prototipo visual, donde el comportamiento ya se validó jugando; mantenerlos evita volver a ajustar la dificultad de la caza.
- **Alternativas descartadas:** visión de 360 grados (la caza se vuelve trivial: el alienígena ve al tripulante en cuanto entra a su alcance); raycasting simétrico (más costo por tick y en este mapa no cambia qué casillas se ven).

## D9. El límite de llamadas cuenta herramientas ejecutadas

- **Fecha:** 2026-11-03
- **Decisión:** el límite de `ejecutar_agente` cuenta cada herramienta ejecutada, no cada turno del modelo. Si un turno pide más herramientas de las que quedan, las sobrantes no se ejecutan y reciben un mensaje de no ejecutada.
- **Motivo:** con llamadas en paralelo, contar por turno permitiría ejecutar muchas más herramientas que el límite (por ejemplo, 6 turnos con 5 herramientas cada uno serían 30 ejecuciones).
- **Alternativas descartadas:** contar por turno del modelo.

## D11. Rutas con A* y heurística Manhattan

- **Fecha:** 2026-11-04
- **Decisión:** `ruta` y `ruta_a_sala` (T09) usan A* con movimientos en 4 direcciones, costo 1 por paso y heurística Manhattan, con desempate determinista. Detalle en [entorno.md](entorno.md#rutas-con-a).
- **Motivo:** con costos unitarios y 4 movimientos, la distancia Manhattan nunca sobreestima (es admisible) y cumple la desigualdad triangular (es consistente), así que A* devuelve un camino de largo mínimo y, para un solo destino, expande menos casillas que BFS.
- **Alternativas descartadas:** BFS para todo (da el mismo resultado pero expande más casillas para un solo destino); Dijkstra (innecesario con costos unitarios, donde equivale a BFS).
- **Nota:** `PredictorDestino` (PR #6) precalcula con BFS la distancia de todas las casillas a cada sala. Es otra necesidad: muchas consultas sobre el mismo mapa, no un camino entre dos puntos.
