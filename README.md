# Xenomorfo-Q

Un cazador que aprende con Deep Q-Learning y una directora que predice: simulación en cuadrícula inspirada en *Alien: Isolation*.
Proyecto final de **SI3003 Inteligencia Artificial**, Universidad EAFIT, 2026-2.

## Idea

- **Directora** (aprendizaje supervisado): conoce la posición real del tripulante, predice a qué sala va y le da pistas de zona al alienígena.
- **Alienígena** (DQN con CNN): caza usando lo que ve, lo que oye y las pistas de la directora.
- **Experimento:** tasa de captura y tiempo medio en tres casos: sin pistas, pistas por reglas y pistas de la directora.

Técnicas: A*, BFS, filtro bayesiano, árbol de comportamiento, árbol de decisión, CNN y DQN.

## Equipo

| Integrante | Responsabilidad |
|---|---|
| Juan José Álvarez | Simulación, bots y dataset |
| Emmanuel Castaño | Directora (dataset, árbol, CNN, pistas) |
| Santiago Meneses | Alienígena (reglas, entorno RL, DQN) |
| Simón | Experimentos, visualización y documento final |

## Estructura

```
sim/           entorno de la estación (mapa, percepción, reglas)
director/      modelo de la directora y reglas de pistas
alien/         alienígena por reglas y DQN
experiments/   protocolo de evaluación y análisis
data/mapas/    mapas en texto (# pared, . piso, + puerta, L casillero)
tests/         pruebas con pytest
docs/          documento final y diagramas
```

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

## Uso del entorno

```python
from sim import EstacionEnv

env = EstacionEnv()
obs = env.reset(semilla=42)          # (4, alto, ancho)
obs, recompensa, terminado, info = env.step(1)
```

Acciones: `0` arriba, `1` derecha, `2` abajo, `3` izquierda, `4` revisar casillero.
Recompensa: `+100` captura, `-1` por paso, `-5` por revisar un casillero vacío.

## Documentación

- [Índice de la documentación](docs/README.md)
- [Arquitectura](docs/arquitectura.md): visión general, flujo por tick y pipeline de entrenamiento.
- [Contratos](docs/contratos.md): interfaces entre módulos, actuales y planeadas.
- [Entorno](docs/entorno.md): mapas, salas, reglas, bot provisional y limitaciones de la versión 0.
- [Decisiones](docs/decisiones.md): registro de decisiones de diseño.
- [Guía de desarrollo](docs/guia-desarrollo.md): instalación, ramas, PR y estándar de documentación.

## Flujo de trabajo

- Ramas: `feature/...`, `fix/...`, `docs/...`.
- Todo entra a `development` por Pull Request con revisión de otro integrante.
- Cada integrante hace sus propios commits.
