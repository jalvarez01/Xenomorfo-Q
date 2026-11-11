# Documentación técnica

Esta carpeta es la única fuente de documentación técnica de Xenomorfo-Q. Todo está en español y en Markdown.

## Índice

| Documento | Contenido |
|---|---|
| [propuesta.md](propuesta.md) | Propuesta del proyecto: problema, opción elegida, herramientas, alcance y plan de pruebas. |
| [arquitectura.md](arquitectura.md) | Partes del sistema, flujo de una pregunta por el agente y ciclo con límite de llamadas. |
| [contratos.md](contratos.md) | Interfaces acordadas: entorno, agente y alienígena por reglas (existen), herramientas (planeadas). |
| [entorno.md](entorno.md) | Formato de mapas, salas, reglas de movimiento y captura, bot provisional y limitaciones actuales. |
| [avance.md](avance.md) | Avance de la simulación con eventos (T10): uso, política del alienígena, eventos y errores. |
| [alien.md](alien.md) | Alienígena por reglas y pistas (T18, T19): cómo decide, presupuesto de pistas, uso y limitaciones. |
| [decisiones.md](decisiones.md) | Registro de decisiones de diseño con su motivo y las alternativas descartadas. |
| [guia-desarrollo.md](guia-desarrollo.md) | Instalación, ramas, flujo de Pull Requests, estilo de commits y estándar de documentación. |
| [prediccion.md](prediccion.md) | Heurística de `predecir_destino` (T12): cómo decide, resultado y limitaciones. |

## Cómo se mantiene

- La documentación se actualiza en el mismo Pull Request que el código que describe. Un PR que cambia una interfaz sin tocar `contratos.md` no se aprueba.
- Las decisiones nuevas se agregan al final de `decisiones.md`; las anteriores no se borran, se marcan como reemplazadas.
- Los ejemplos de código de estos documentos deben ejecutarse tal cual. Si un cambio los rompe, se corrigen en el mismo PR.
- Los commits de documentación no cambian comportamiento.
