# Xenomorfo-Q

Agente directora que responde preguntas sobre una partida de sigilo simulada y actúa sobre ella usando herramientas.

Proyecto final de **SI3003 Inteligencia Artificial**, Universidad EAFIT, 2026-2.

## Integrantes

| Integrante | Usuario | Rol |
|---|---|---|
| Juan José Álvarez | jalvarez01 | Simulación (mapa, salas, visión, rutas con A*), herramientas del agente, directora y comando |
| Emmanuel Castaño | ecastanos23 | Ciclo del agente con límite de llamadas, configuración del modelo de lenguaje, esquemas y prompt de sistema |
| Santiago Meneses | SamCr17 | Alienígena por reglas y pistas, predicción de destino y avance de la simulación con eventos |
| Simón Mazo | Smg4315 | Casos de prueba, valoración, análisis, notebook de demostración y README final |

## Problema

En un juego de sigilo, la directora conoce la posición real del jugador y decide cuándo ayudar a la criatura que lo persigue. Diseñarla y probarla obliga a revisar la partida a mano: dónde está cada uno, cuántos pasos los separan, si la criatura ya vio al jugador y si conviene darle una pista. Xenomorfo-Q es un agente que responde esas preguntas en español consultando una simulación con herramientas, y que puede dar pistas o avanzar la partida.

## Opción elegida y por qué

Opción B: agente con herramientas. Las respuestas dependen de un estado que cambia en cada tick y de cálculos como rutas y distancias, no de documentos; un sistema RAG no puede consultar ese estado ni actuar sobre la partida.

Cómo cumple la opción B:

- **Herramientas:** 6 funciones de Python sobre la simulación: `estado_partida`, `ruta_mas_corta`, `predecir_destino`, `ve_tripulante`, `dar_pista` y `avanzar_simulacion` ([docs/herramientas.md](docs/herramientas.md)).
- **Descripciones para el modelo:** cada herramienta tiene un esquema con su descripción y sus parámetros en `director/esquemas.py`, y el prompt de sistema explica cuándo usar cada una (`director/prompt.py`).
- **Ciclo de ejecución:** `director/agente.py` envía la pregunta y los esquemas al modelo, ejecuta las herramientas que pide, le devuelve los resultados y repite hasta que responde en texto ([docs/arquitectura.md](docs/arquitectura.md)).
- **Límite de llamadas:** como máximo 6 herramientas ejecutadas por pregunta. Al llegar al límite, las llamadas que sobran no se ejecutan y el modelo responde una última vez sin herramientas, diciendo que alcanzó el límite (decisión D9 en [docs/decisiones.md](docs/decisiones.md)).
- **Registro:** cada llamada queda registrada con la herramienta, los argumentos, el resultado y el tiempo; `python -m director --registro` y el notebook lo muestran.

## Instrucciones de ejecución

### En local

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

Las pruebas no llaman a la API real.

Para preguntarle a la directora hace falta la clave (ver "Configuración de la clave"):

```bash
python -m director "¿En qué sala está el tripulante?" --registro
python -m director
```

La primera forma responde una pregunta; con `--registro` muestra también cada llamada a herramienta y el número de llamadas. La segunda abre el modo interactivo sobre una misma partida: `estado` muestra el estado sin usar el modelo y `salir` termina. Las opciones `--semilla` (por defecto 42) y `--limite` (por defecto 6) cambian la partida y el máximo de llamadas. El detalle está en [docs/herramientas.md](docs/herramientas.md).

Para correr los 6 casos de prueba y guardar la evidencia (JSON y Markdown) en `experiments/resultados/`:

```bash
python -m experiments.casos --semilla 42
```

### En Colab

Abrir `notebooks/demo_directora.ipynb` en Colab y guardar la clave en los secretos del notebook (icono de llave) con el nombre `NVIDIA_API_KEY`. La primera celda clona el repositorio, instala las dependencias y carga la clave sin mostrarla. El notebook muestra las herramientas sin el modelo, cuatro preguntas con su registro de llamadas y qué pasa al llegar al límite. En local funciona igual, con la clave en `.env`.

## Configuración de la clave

- En local: copiar `.env.example` a `.env` y completar `NVIDIA_API_KEY`.
- En Colab: guardar `NVIDIA_API_KEY` en los secretos del notebook.
- Nunca subir `.env` ni la clave al repositorio.

## Fuentes y herramientas

- **Datos:** simulación propia en Python y mapa ficticio Vela-9 (15 por 24 casillas, 8 salas y 8 casilleros) en [data/mapas/](data/mapas/). No se usan datos externos ni personales.
- **Modelo:** `meta/llama-3.3-70b-instruct` servido por NVIDIA NIM, con temperatura 0 para que los casos sean repetibles.
- **Base del ciclo del agente:** los notebooks del curso de [Lecture11](https://github.com/EAFIT-IA/si3003-artificial-intelligence/tree/main/notebooks/Lecture11) (`run_agent_with_budget`).
- **Algoritmos propios:** visión con línea de vista (Bresenham) y cono, rutas con A* y heurística Manhattan, predicción de destino por acercamiento y alienígena por reglas ([docs/decisiones.md](docs/decisiones.md)).
- **Bibliotecas de Python:** `numpy` (mapa y visión), `openai` (cliente compatible con NVIDIA NIM), `python-dotenv` (clave desde `.env`) y `pytest` (pruebas sin red).

## Casos de prueba

Cinco casos que pide la rúbrica (3 habituales, 1 que exige varias herramientas y 1 límite) y uno extra para mostrar el límite de llamadas. El resultado esperado se calcula con las herramientas sin el modelo, sobre la misma partida ([docs/casos.md](docs/casos.md)). Cada caso corre en una partida nueva con la semilla 42; C3 usa una partida preparada (semilla 0, 11 ticks) para que el tripulante ya se esté moviendo.

| Caso | Tipo | Pregunta | Resultado esperado | Respuesta obtenida | Valoración |
|---|---|---|---|---|---|
| C1 | habitual | ¿En qué sala está el tripulante y a cuántos pasos está el alienígena? | Bodega, a 15 pasos | pendiente | pendiente |
| C2 | habitual | ¿El alienígena está viendo al tripulante en este momento? | No lo ve; está a 15 pasos | pendiente | pendiente |
| C3 | habitual | ¿Hacia qué sala se dirige el tripulante? | Hacia el Hangar (está en el Corredor B), confianza 0.5 | pendiente | pendiente |
| C4 | varias herramientas y acción | El alienígena lleva rato perdido: dale una pista hacia la sala donde está el tripulante, avanza 10 ticks y dime si se acercó. | Pista a Bodega (quedan 2); pasa de 15 a 6 pasos, sí se acercó | pendiente | pendiente |
| C5 | límite: sala inexistente | ¿Cuántos pasos hay desde la Enfermería hasta el Hangar? | La Enfermería no existe; lista las 8 salas válidas sin inventar una ruta | pendiente | pendiente |
| C6 | extra: límite de llamadas | Calcula la distancia del alienígena a cada una de las 8 salas. | Necesita 8 llamadas; con el límite de 6 debe responder con lo obtenido y decir que alcanzó el límite | pendiente | pendiente |

La evidencia completa de cada caso (llamadas con argumentos y resultados, respuesta, latencia) queda en `experiments/resultados/` al correr `python -m experiments.casos`.

## Análisis de resultados

Pendiente: se escribe con la evidencia de la prueba real contra NVIDIA NIM.

## Documentación

- [Índice de la documentación](docs/README.md)
- [Propuesta](docs/propuesta.md): problema, opción elegida, herramientas, alcance y plan de pruebas.
- [Arquitectura](docs/arquitectura.md): partes del sistema, flujo de una pregunta y ciclo con límite.
- [Contratos](docs/contratos.md): interfaces del entorno, las herramientas y el agente.
- [Herramientas](docs/herramientas.md): las 6 herramientas, la partida, la directora y el comando `python -m director`.
- [Casos](docs/casos.md): el ejecutor de casos, los valores esperados y el formato de la evidencia.
- [Alienígena](docs/alien.md): el alienígena por reglas y las pistas.
- [Predicción](docs/prediccion.md): la heurística de `predecir_destino`.
- [Avance](docs/avance.md): el avance de la simulación con eventos.
- [Entorno](docs/entorno.md): mapas, salas, reglas, bot provisional y limitaciones de la versión 0.
- [Decisiones](docs/decisiones.md): registro de decisiones de diseño.
- [Guía de desarrollo](docs/guia-desarrollo.md): instalación, ramas, PR, claves de API y estándar de documentación.

## Flujo de trabajo

- Las ramas de trabajo (`feature/...`, `fix/...`, `docs/...`) salen de `development`.
- Todo entra a `development` por Pull Request con la aprobación de otro integrante.
- Cada integrante hace sus propios commits.
