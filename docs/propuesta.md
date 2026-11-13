# Propuesta de proyecto final: Xenomorfo-Q

- **Curso:** SI3003 Inteligencia Artificial, Universidad EAFIT, 2026-2.
- **Opción elegida:** B, agente con herramientas.
- **Repositorio:** https://github.com/jalvarez01/Xenomorfo-Q

## Equipo

| Integrante | Responsabilidad |
|---|---|
| Juan José Álvarez | Simulación y funciones de las herramientas |
| Emmanuel Castaño | Ciclo del agente, configuración del modelo de lenguaje y prompt de sistema |
| Santiago Meneses | Alienígena por reglas, predicción de destino y avance de la simulación |
| Simón Mazo | Casos de prueba, análisis, notebook de demostración y README final |

## Problema

En un juego de sigilo, una "directora" es el sistema que conoce la posición real del jugador y decide cuándo ayudar a la criatura que lo persigue. Diseñarla y probarla obliga a revisar la partida a mano: dónde está cada uno, cuántos pasos los separan, si la criatura ya vio al jugador y si conviene darle una pista.

Construimos un agente que responde en español las preguntas de un diseñador o tester sobre una partida simulada. Para responder consulta la simulación con herramientas, y además puede actuar sobre ella: dar una pista al alienígena o avanzar la partida y contar qué pasó.

## Para quién

Diseñadores y testers de juegos de sigilo. Dentro del proyecto, los usuarios somos el propio equipo, que necesita inspeccionar partidas para ajustar el comportamiento del alienígena.

## Preguntas y tareas

- ¿En qué sala está el tripulante y a cuántos pasos está el alienígena?
- ¿El alienígena lo está viendo ahora?
- ¿Hacia qué sala parece que va el tripulante?
- Dale una pista al alienígena sobre dónde buscar.
- Avanza la partida unos ticks y resume qué pasó.

## Por qué un agente y no RAG

Las respuestas dependen del estado de la partida, que cambia en cada tick, y de cálculos como rutas y distancias. No están escritas en ningún documento. Un sistema RAG solo puede recuperar texto: no puede consultar el estado actual ni actuar sobre la partida. Un agente con herramientas sí.

## Datos y herramientas

**Datos.** Una simulación propia en Python y un mapa ficticio, Vela-9, de 15 por 24 casillas con 8 salas y 8 casilleros, guardado en `data/mapas/`. No usamos datos externos ni personales.

**Herramientas del agente:**

| Herramienta | Qué hace |
|---|---|
| `estado_partida()` | Devuelve tick, posición y sala del tripulante y del alienígena, pistas restantes y si hubo captura. |
| `ruta_mas_corta(origen, destino)` | Calcula con A* los pasos entre dos salas o personajes. |
| `predecir_destino()` | Estima hacia qué sala va el tripulante a partir de sus últimos 10 ticks. |
| `ve_tripulante()` | Dice si el alienígena ve al tripulante y a cuántas casillas está. |
| `dar_pista(sala)` | Le indica una sala al alienígena; máximo 3 por partida. |
| `avanzar_simulacion(ticks)` | Avanza de 1 a 20 ticks y devuelve los eventos ocurridos. |

**Modelo.** Un modelo de lenguaje servido por NVIDIA NIM (`meta/llama-3.3-70b-instruct` por defecto), con cliente compatible con OpenAI y clave privada guardada fuera del repositorio.

> Nota posterior a la entrega del 2026-11-03: ese modelo llegó al fin de su vida en NVIDIA NIM y el proveedor pasó a ser configurable, con OpenAI como principal. Ver la decisión D15 en [decisiones.md](decisiones.md). La propuesta se conserva como se entregó.

**Límite.** El agente hace como máximo 6 llamadas a herramientas por pregunta. Si llega al límite, el modelo responde sin herramientas con lo que ya sabe y dice que alcanzó el límite. Cada llamada queda registrada con la herramienta, los argumentos y el resultado.

## Fuera del alcance

- Entrenar modelos propios (DQN, redes de predicción o similares).
- Gráficos en tiempo real.
- Varios mapas o varios agentes.

## Plan de pruebas

| Caso | Tipo | Ejemplo |
|---|---|---|
| 1 a 3 | Habituales | Preguntas de una sola herramienta: sala del tripulante, si el alienígena lo ve, ruta entre dos salas. |
| 4 | Varias herramientas y acción | "¿Hacia dónde va el tripulante? Si el alienígena no lo ve, dale una pista y avanza 10 ticks." |
| 5 | Límite | Pregunta por una sala que no existe; el agente debe reconocer el error y listar las salas válidas. |
| 6 | Extra: límite de llamadas | Una pregunta que exige más de 6 llamadas; el agente debe detenerse y decirlo. |

Los casos 1 a 5 son los cinco que pide la rúbrica; el 6 es adicional para mostrar el límite de llamadas.

Por cada caso registramos la pregunta, las herramientas llamadas con sus argumentos y resultados, el número de llamadas, la respuesta final y si fue correcta frente a lo que muestra la simulación.
