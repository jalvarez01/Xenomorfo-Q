# Documentación técnica

Esta carpeta es la única fuente de documentación técnica de Xenomorfo-Q. Todo está en español y en Markdown.

## Índice

| Documento | Contenido |
|---|---|
| [arquitectura.md](arquitectura.md) | Visión general del sistema, flujo de datos por tick y pipeline de entrenamiento. |
| [contratos.md](contratos.md) | Interfaces acordadas entre módulos: lo que existe hoy (versión 0) y lo planeado. |
| [entorno.md](entorno.md) | Formato de mapas, reglas de movimiento y captura, bot provisional y limitaciones actuales. |
| [decisiones.md](decisiones.md) | Registro de decisiones de diseño con su motivo y las alternativas descartadas. |
| [guia-desarrollo.md](guia-desarrollo.md) | Instalación, ramas, flujo de Pull Requests, estilo de commits y estándar de documentación. |

## Cómo se mantiene

- La documentación se actualiza en el mismo Pull Request que el código que describe. Un PR que cambia una interfaz sin tocar `contratos.md` no se aprueba.
- Las decisiones nuevas se agregan al final de `decisiones.md`; las anteriores no se borran, se marcan como reemplazadas.
- Los ejemplos de código de estos documentos deben ejecutarse tal cual. Si un cambio los rompe, se corrigen en el mismo PR.
- Los commits de documentación no cambian comportamiento.
