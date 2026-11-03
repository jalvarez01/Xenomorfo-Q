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
