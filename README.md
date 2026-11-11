# Xenomorfo-Q

Agente directora que responde preguntas sobre una partida de sigilo simulada y actúa sobre ella usando herramientas.

Proyecto final de **SI3003 Inteligencia Artificial**, Universidad EAFIT, 2026-2.

## Integrantes

| Integrante | Rol |
|---|---|
| Juan José Álvarez | Simulación y funciones de las herramientas |
| Emmanuel Castaño | Ciclo del agente, configuración del modelo de lenguaje y prompt de sistema |
| Santiago Meneses | Alienígena por reglas, predicción de destino y avance de la simulación |
| Simón Mazo | Casos de prueba, análisis, notebook de demostración y README final |

## Problema

En un juego de sigilo, la directora conoce la posición real del jugador y decide cuándo ayudar a la criatura que lo persigue. Diseñarla y probarla obliga a revisar la partida a mano: dónde está cada uno, cuántos pasos los separan, si la criatura ya vio al jugador y si conviene darle una pista. Xenomorfo-Q es un agente que responde esas preguntas en español consultando una simulación con herramientas, y que puede dar pistas o avanzar la partida.

## Opción elegida y por qué

Opción B: agente con herramientas. Las respuestas dependen de un estado que cambia en cada tick y de cálculos como rutas y distancias, no de documentos; un sistema RAG no puede consultar ese estado ni actuar sobre la partida.

## Instrucciones de ejecución

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

## Configuración de la clave

- En local: copiar `.env.example` a `.env` y completar `NVIDIA_API_KEY`.
- En Colab: guardar `NVIDIA_API_KEY` en los secretos del notebook.
- Nunca subir `.env` ni la clave al repositorio.

## Fuentes y herramientas

- Simulación propia en Python y mapa ficticio Vela-9 en [data/mapas/](data/mapas/).
- Modelo de lenguaje servido por NVIDIA NIM: `meta/llama-3.3-70b-instruct`.
- El ciclo del agente parte de los notebooks del curso de [Lecture11](https://github.com/EAFIT-IA/si3003-artificial-intelligence/tree/main/notebooks/Lecture11).

## Casos de prueba

Pendiente: se documentan al ejecutar el prototipo (3 habituales, 1 con herramientas, 1 límite y 1 del límite de llamadas).

## Análisis de resultados

Pendiente.

## Documentación

- [Índice de la documentación](docs/README.md)
- [Propuesta](docs/propuesta.md): problema, opción elegida, herramientas, alcance y plan de pruebas.
- [Arquitectura](docs/arquitectura.md): partes del sistema, flujo de una pregunta y ciclo con límite.
- [Contratos](docs/contratos.md): interfaces del entorno, las herramientas y el agente.
- [Herramientas](docs/herramientas.md): las 6 herramientas, la partida, la directora y el comando `python -m director`.
- [Entorno](docs/entorno.md): mapas, salas, reglas, bot provisional y limitaciones de la versión 0.
- [Decisiones](docs/decisiones.md): registro de decisiones de diseño.
- [Guía de desarrollo](docs/guia-desarrollo.md): instalación, ramas, PR, claves de API y estándar de documentación.

## Flujo de trabajo

- Las ramas de trabajo (`feature/...`, `fix/...`, `docs/...`) salen de `development`.
- Todo entra a `development` por Pull Request con la aprobación de otro integrante.
- Cada integrante hace sus propios commits.
