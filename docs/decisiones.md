# Registro de decisiones

Cada entrada registra una decisión de diseño. Las decisiones nuevas van al final. Si una decisión se reemplaza, no se borra: se marca como reemplazada y se enlaza la nueva.

## D1. La directora se entrena aparte y se congela antes del DQN

- **Fecha:** 2026-10-28
- **Decisión:** la directora se entrena con aprendizaje supervisado y se congela antes de entrenar el DQN del alienígena.
- **Motivo:** entrenar ambos a la vez es inestable: el alienígena aprende a depender de pistas que siguen cambiando mientras la directora aprende.
- **Alternativas descartadas:** entrenamiento conjunto de directora y alienígena; directora que aprende por refuerzo junto al alienígena.
- **Estado:** reemplazada por D8 (fuera del alcance).

## D2. Las pistas son zonas, nunca la casilla exacta

- **Fecha:** 2026-10-28
- **Decisión:** una pista indica las casillas de la sala más probable, no la posición exacta del tripulante.
- **Motivo:** si la pista diera la casilla exacta, el alienígena aprendería a seguirla y nunca a usar su propia percepción.
- **Alternativas descartadas:** dar la casilla exacta; dar solo una dirección general.
- **Estado:** vigente, adaptada en D8: la pista es una sala, con máximo 3 por partida.

## D3. El dataset se separa por partida, no por fila

- **Fecha:** 2026-10-28
- **Decisión:** la separación en entrenamiento, validación y prueba se hace por `partida_id`.
- **Motivo:** las filas de una misma partida son casi idénticas entre ticks seguidos. Separar por fila filtra información de prueba al entrenamiento y da métricas infladas.
- **Alternativas descartadas:** separación aleatoria por fila.
- **Estado:** reemplazada por D8 (fuera del alcance).

## D4. Se evalúa en mapas no vistos

- **Fecha:** 2026-10-28
- **Decisión:** los mapas de prueba no se usan en ningún entrenamiento.
- **Motivo:** evita que la directora memorice la distribución de un mapa en vez de aprender a leer la trayectoria.
- **Alternativas descartadas:** evaluar en los mismos mapas de entrenamiento con partidas nuevas.
- **Estado:** reemplazada por D8 (fuera del alcance).

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
- **Nota (D8):** el motivo vigente es que las herramientas (estado_partida, ruta_mas_corta, dar_pista) consultan salas fijas por nombre; las referencias a T15 y al dataset quedaron fuera del alcance.

## D7. Parámetros de visión del alienígena

- **Fecha:** 2026-11-04
- **Decisión:** el alienígena ve hasta 7.5 casillas (15 m), en un cono de unos 127 grados (coseno mínimo 0.45) hacia donde mira, y a menos de 1.5 casillas en cualquier dirección. Solo las paredes tapan la vista; las puertas y los casilleros no. La línea de vista usa Bresenham desde el alienígena hacia la casilla. Detalle en [entorno.md](entorno.md#visión).
- **Motivo:** son los mismos parámetros del prototipo visual, donde el comportamiento ya se validó jugando; mantenerlos evita volver a ajustar la dificultad de la caza.
- **Alternativas descartadas:** visión de 360 grados (la caza se vuelve trivial: el alienígena ve al tripulante en cuanto entra a su alcance); raycasting simétrico (más costo por tick y en este mapa no cambia qué casillas se ven).

## D8. Reorientación a la opción B: agente con herramientas

- **Fecha:** 2026-11-03
- **Decisión:** el proyecto pasa a ser un agente directora con modelo de lenguaje y herramientas sobre la simulación existente. Se descartan el DQN, la directora CNN, el dataset de trayectorias y todo entrenamiento guiado por recompensa.
- **Motivo:** la rúbrica oficial del proyecto exige un prototipo construido alrededor de un modelo de lenguaje. La simulación que ya existe (mapa, salas y entorno) sirve directamente como fuente de datos para las herramientas del agente.
- **Alternativas descartadas:** RAG, porque las respuestas dependen de un estado que cambia en cada tick y no de documentos; mantener el DQN, porque no cumple la rúbrica y no cabe en el tiempo hasta la sustentación del 2026-11-17.

## D9. El límite de llamadas cuenta herramientas ejecutadas

- **Fecha:** 2026-11-03
- **Decisión:** el límite de `ejecutar_agente` cuenta cada herramienta ejecutada, no cada turno del modelo. Si un turno pide más herramientas de las que quedan, las sobrantes no se ejecutan y reciben un mensaje de no ejecutada.
- **Motivo:** con llamadas en paralelo, contar por turno permitiría ejecutar muchas más herramientas que el límite (por ejemplo, 6 turnos con 5 herramientas cada uno serían 30 ejecuciones).
- **Alternativas descartadas:** contar por turno del modelo.

## D10. predecir_destino usa acercamiento ponderado por camino recorrido

- **Fecha:** 2026-11-03
- **Decisión:** `predecir_destino` (T12) mira los últimos 10 ticks con distancias caminando (BFS), no en línea recta. Si el tripulante entró a una sala durante la ventana y sigue en ella, esa sala es el destino (regla de llegada). Si no, elige la sala con mayor `acercamiento × (acercamiento / d0)`. La confianza es `acercamiento / ticks`. Detalle en [prediccion.md](prediccion.md).
- **Motivo:** con el acercamiento puro, al caminar en una dirección siempre gana la sala más lejana en esa dirección, aunque el tripulante ya haya llegado a una más cercana. La fracción recorrida sola no basta: mientras el tripulante camina dentro de la sala a la que llegó, las de más adelante siguen sumando y le ganan (lo encontró la revisión del PR #6, en la fila 3 del Laboratorio). La distancia en línea recta ignora las paredes y señala salas a las que no se llega por ese lado.
- **Alternativas descartadas:** acercamiento puro; distancia Manhattan o euclidiana; confianza como fracción del acercamiento total entre salas (se descartó porque en un corredor reparte la confianza entre las salas de adelante aunque el tripulante camine directo); un modelo entrenado (queda como opcional en T31).

## D11. Rutas con A* y heurística Manhattan

- **Fecha:** 2026-11-04
- **Decisión:** `ruta` y `ruta_a_sala` (T09) usan A* con movimientos en 4 direcciones, costo 1 por paso y heurística Manhattan, con desempate determinista. Detalle en [entorno.md](entorno.md#rutas-con-a).
- **Motivo:** con costos unitarios y 4 movimientos, la distancia Manhattan nunca sobreestima (es admisible) y cumple la desigualdad triangular (es consistente), así que A* devuelve un camino de largo mínimo y, para un solo destino, expande menos casillas que BFS.
- **Alternativas descartadas:** BFS para todo (da el mismo resultado pero expande más casillas para un solo destino); Dijkstra (innecesario con costos unitarios, donde equivale a BFS).
- **Nota:** `PredictorDestino` (PR #6) precalcula con BFS la distancia de todas las casillas a cada sala. Es otra necesidad: muchas consultas sobre el mismo mapa, no un camino entre dos puntos.

## D12. Las salas se pasan como texto libre, sin enum

- **Fecha:** 2026-11-05
- **Decisión:** en los esquemas de `ruta_mas_corta` y `dar_pista`, los parámetros de sala son texto libre. Los nombres válidos van en la descripción, con la instrucción de pasar el nombre tal como lo dijo el usuario.
- **Motivo:** con enum, el modelo podría reemplazar en silencio una sala inexistente por una válida (por ejemplo, "Enfermería" por "Médico"). Sin enum, la herramienta devuelve el error con las salas válidas y la directora puede sugerir sin inventar (caso de prueba C5).
- **Alternativas descartadas:** enum estricto con los nombres de sala.

## D13. El alienígena por reglas busca donde lo vio y va al centro de las salas

- **Fecha:** 2026-11-11
- **Decisión:** al árbol de T18 (perseguir, pista, patrullar) se le agrega una regla entre perseguir y la pista: si perdió de vista al tripulante, va a la última casilla donde lo vio. Las pistas y la patrulla apuntan al centro de cada sala (la casilla transitable más cercana al promedio de la sala), y la patrulla va siempre al centro más cercano que no haya visitado en la vuelta. Detalle en [alien.md](alien.md).
- **Motivo:** sin la última casilla vista, el alienígena abandonaba la caza en cuanto el tripulante salía del cono, aunque estuviera a dos pasos. Ir al centro, y no a la primera casilla de la sala, lo hace entrar de verdad a la sala y ver la mayor parte de ella. En vela9 captura en 18 de 20 partidas (semillas 0 a 19).
- **Alternativas descartadas:** usar la posición real del tripulante sin verlo (sería trampa: esa información es de la directora); patrullar las salas en el orden de sus índices (en vela9 cruza el mapa de lado a lado entre Comunicaciones y Corredor A); patrulla al azar (los casos de prueba dejan de ser repetibles).

## D14. Los nombres de sala se comparan sin mayúsculas ni tildes

- **Fecha:** 2026-11-11
- **Decisión:** las herramientas (T11) buscan las salas con `Mapa.indice_sala`, que compara sin mayúsculas, sin tildes (NFD sin marcas combinadas) y con los espacios repetidos reducidos a uno. Las funciones internas reciben siempre el nombre canónico del mapa. Detalle en [herramientas.md](herramientas.md).
- **Motivo:** los usuarios escriben "medico" o "corredor a", y el modelo pasa el nombre tal como lo dijo el usuario (D12). Normalizar no es corregir: "medico" es Médico escrito sin tilde, mientras que "Enfermería" sigue siendo una sala inexistente, así que D12 se mantiene.
- **Alternativas descartadas:** coincidencia exacta (falla con "medico", que es un nombre válido escrito sin tilde); coincidencia aproximada por similitud (cambiaría "Enfermería" por otra sala, justo lo que D12 evita).

## D15. Proveedor configurable y cambio de modelo

- **Fecha:** 2026-11-12
- **Decisión:** el proveedor del modelo se elige con `XQ_PROVEEDOR`: `openai` (principal, modelo por defecto `gpt-5.4-nano`) o `nvidia` (NVIDIA NIM, alternativa gratuita, modelo por defecto `openai/gpt-oss-20b`). Cada proveedor tiene su clave (`OPENAI_API_KEY` o `NVIDIA_API_KEY`); `XQ_MODELO` y `XQ_URL_BASE` siguen permitiendo cambiar modelo y URL. Detalle en `director/llm.py` y en la sección 6 de [contratos.md](contratos.md).
- **Motivo:** en la primera prueba real, `meta/llama-3.3-70b-instruct` respondió 410: llegó al fin de su vida en NVIDIA NIM el 2026-08-26. De los modelos de NIM que probamos, tres respondieron 404 para nuestra cuenta (`nvidia/llama-3.1-nemotron-70b-instruct`, `mistralai/mistral-large-2-instruct` y `nvidia/nemotron-3-super-120b-a12b`), `deepseek-ai/deepseek-v4.1-flash` no respondió, y `openai/gpt-oss-20b` pidió bien la herramienta y aceptó la llamada de cierre sin herramientas, pero tardó unos 4 minutos por pregunta. En OpenAI, `gpt-5.4-nano`, `gpt-5.4-mini` y `gpt-4.1-mini` pasaron la prueba de herramienta, la de cierre y el caso C1 con las herramientas reales en menos de 4 s; `gpt-4o-mini` respondió C1 con un número inventado y `gpt-5-nano` y `gpt-5-mini` no aceptan temperatura 0. Se eligió OpenAI como principal por estabilidad en la sustentación en vivo y confiabilidad en las llamadas a herramientas, y `gpt-5.4-nano` por ser el más barato de los que pasaron. La llamada de cierre sin herramientas funciona en los dos proveedores, así que el ciclo (D9) no cambia.
- **Alternativas descartadas:** seguir solo con NVIDIA NIM (sin un modelo que responda a tiempo para una demostración en vivo); fijar un modelo sin hacerlo configurable (el mismo problema se repetiría si un modelo deja de estar disponible).
- **Nota:** la propuesta entregada el 2026-11-03 (`docs/propuesta.md` y el PDF) nombra el modelo anterior y se conserva como se entregó.

## D16. Panel web local como ayuda visual

- **Fecha:** 2026-11-12
- **Decisión:** se agrega `python -m panel`, un panel web local para observar una partida, jugarla moviendo al tripulante y preguntarle a la directora sobre esa misma partida. Usa solo la biblioteca estándar (`http.server`) y una página con el CSS y el JS en línea, sin recursos externos, y escucha solo en `127.0.0.1`. Todo lo que muestra sale del código: la partida es la de la directora, los pasos usan el mismo avance que `avanzar_simulacion` y el chat llama a `Directora.preguntar`. Para el modo de juego, `EstacionEnv.step` y `Avance.avanzar` aceptan una acción opcional del tripulante; sin ella el bot y el generador aleatorio se usan exactamente como antes, y una prueba compara las partidas con semilla contra huellas tomadas antes del cambio.
- **Motivo:** en la sustentación ayuda ver el mapa, el campo de visión y la ruta del alienígena mientras la directora responde. La rúbrica no exige interfaz gráfica, así que el panel es opcional: el agente, las herramientas, los esquemas, el prompt, el límite de llamadas y la evidencia oficial no cambian, y `python -m director`, el notebook y `python -m experiments.casos` se comportan igual.
- **Qué no muestra:** el mock visual de la fase de diseño tenía creencia bayesiana, propagación de ruido, un medidor de tensión del director, escondites en casilleros y una fase con DQN. No se muestran porque no están implementados en la simulación ni en el agente (D8 dejó fuera el DQN); el panel no inventa datos que el código no calcula.
- **Alternativas descartadas:** un framework web o una biblioteca de gráficos (dependencias nuevas a días de la entrega); portar la simulación del mock a JavaScript (mostraría un comportamiento distinto al del código real).


## D17. Versión máxima del cliente de OpenAI

- **Fecha:** 2026-11-12
- **Decisión:** `requirements.txt` fija `openai>=1.40,<3`. Con la regla anterior (`openai>=1.40`), una instalación limpia trae la serie 3.x.
- **Motivo:** en una máquina del equipo, `import openai` falló con la serie 3.x hasta recrear el entorno virtual. En entornos limpios no se reprodujo: con 2.54.0 y con 3.50.0 pasan las pruebas y una pregunta real al modelo responde bien. La serie 2.x queda verificada para la entrega y el tope evita saltar de serie sin probarla.
- **Alternativas descartadas:** dejar el requisito abierto (cada instalación puede traer una serie distinta a la verificada); fijar una versión exacta (impide recibir correcciones de la serie 2.x).

## D18. Panel en línea en una instancia EC2 detrás de Caddy

- **Fecha:** 2026-11-13
- **Decisión:** el panel se puede publicar en una sola instancia EC2 (`t3.micro`, Ubuntu 24.04) con Caddy delante. Los archivos están en `deploy/` y la guía en `docs/despliegue.md`.
  - **Red:** Caddy es lo único que escucha en internet. Da HTTPS con un dominio `<ip>.sslip.io` y pide usuario y contraseña en todo salvo `/salud`.
  - **Panel:** sigue escuchando solo en 127.0.0.1, como servicio systemd con un usuario sin privilegios.
  - **Sesiones:** cada visitante tiene su propia partida, por una cookie aleatoria (HttpOnly, SameSite=Lax y Secure si Caddy avisa que la petición llegó por HTTPS). Hay como máximo 30 sesiones en memoria, cada una dura 30 minutos sin uso y, con el almacén lleno, se descarta la menos usada.
  - **Cupos del chat:** 20 preguntas por sesión y 60 por hora en todo el servidor (`XQ_PANEL_MAX_SESION`, `XQ_PANEL_MAX_HORA`). Pasado un cupo, el chat responde 429 con un aviso y lo demás sigue funcionando.
  - **Puerto:** `--puerto` también se toma de `PORT`.
  - **`/salud`:** responde `{"ok": true}`.
- **Motivo:** mostrar el panel fuera de la red local sin exponer la clave del modelo ni dejar que cualquiera gaste crédito. El usuario y la contraseña cierran el acceso, y los cupos acotan el costo aunque alguien entre o borre su cookie para tener una sesión nueva. Con una partida por visitante, dos personas no se mueven la partida la una a la otra.
- **En local:** `python -m panel` se comporta igual que antes. La única diferencia visible es el cupo de 20 preguntas por sesión, que se quita con `XQ_PANEL_MAX_SESION=0`.
- **Alternativas descartadas:**
  - un servicio administrado (App Runner, Elastic Beanstalk): más piezas y costo para una demostración;
  - exponer el panel directamente en el puerto 8000: sin HTTPS ni contraseña;
  - guardar las sesiones en disco o en una base de datos: no hace falta para una demostración y obliga a pensar en datos de visitantes.

## D19. Niveles de dificultad solo en el panel, con normal por defecto

- **Fecha:** 2026-11-13
- **Decisión:** el panel tiene un selector de dificultad con tres niveles. Cambiarlo reinicia la partida con la misma semilla.
  - **normal:** todo por defecto; es la partida de siempre.
  - **difícil:** la visión del alienígena llega a 10 casillas en vez de 7.5, y cada 3 ticks en los que persigue da un paso extra.
  - **pesadilla:** difícil, más una pista automática hacia la sala real del tripulante cuando el alienígena lleva 25 ticks sin verlo, como máximo 3 por partida.
- **Cómo se implementa:** con parámetros opcionales cuyos valores por defecto son los de siempre.
  - `EstacionEnv(alcance_vision)`.
  - `AlienReglas(paso_extra_cada)`, con `accion_extra()`, que `Avance` aplica con `env.paso_extra_alien()`. Ese método usa las mismas reglas de movimiento y de captura y no usa el generador aleatorio.
  - `Avance(tras_tick)`.
  - `AlienReglas.dar_pista(sala, contar=False)`.
  - La pista automática es una regla del panel (`PistaAutomatica` en `panel/sesion.py`), no de la directora. Lleva su propio presupuesto, aparte de las 3 pistas de la directora, y deja en el registro "directora automática: pista hacia <sala>".
  - La directora del chat trabaja sobre la misma partida del nivel elegido, y `ve_tripulante` lee el campo de visión real, con el alcance del nivel.
- **Por qué solo en el panel:** los niveles son para jugar en la demostración. Los casos de prueba, `python -m director`, `python -m experiments.casos`, el notebook y la evidencia oficial deben seguir midiendo el mismo problema que se documentó. Si la dificultad entrara ahí, cambiarían los valores esperados y la corrida oficial dejaría de ser comparable.
- **Por qué normal es el valor por defecto:** así nada cambia para quien no toca el selector. Una prueba lo verifica:
  - las huellas de las partidas con semillas 42, 0 y 7 y la de 200 pasos de `env.step` son las mismas que se tomaron antes de agregar los niveles;
  - los valores esperados de los 6 casos son los de la evidencia oficial.
- **Alternativas descartadas:**
  - un alienígena más rápido en todo momento: haría injugable el modo Tú y no se parece a una persecución;
  - dar las pistas automáticas con el presupuesto de la directora: le quitaría pistas al agente sin que él lo decida.
