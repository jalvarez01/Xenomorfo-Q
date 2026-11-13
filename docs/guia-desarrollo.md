# Guía de desarrollo

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

`pytest.ini` agrega la raíz del repositorio al path, así que `pytest` funciona desde la raíz sin instalar el paquete.

## Ramas

- `main`: versión entregable. Solo recibe cambios desde `development`.
- `development`: rama de integración y rama por defecto.
- Ramas de trabajo, siempre creadas desde `development`:
  - `feature/<tema>` para funcionalidad nueva, por ejemplo `feature/vision-alien`.
  - `fix/<tema>` para correcciones.
  - `docs/<tema>` para documentación.

## Flujo de Pull Requests

1. Actualizar `development` y crear la rama de trabajo.
2. Hacer commits pequeños.
3. Abrir un Pull Request hacia `development`.
4. Otro integrante lo revisa y lo aprueba (mínimo una aprobación).
5. Se hace merge cuando la revisión está aprobada y las pruebas pasan.

Nadie hace push directo a `main` ni a `development`.

## Commits

- Mensajes cortos, en minúscula y en español, describiendo el cambio: `agrega vision del alienigena`, `corrige captura en puertas`.
- Cada integrante hace sus propios commits.
- No se reescribe historia ya publicada (nada de `--amend` sobre commits publicados ni `push --force`).

## Estándar de documentación

Aplica a todo el código nuevo y a cada cambio.

- Cada módulo empieza con un docstring: propósito, contenido principal y tareas relacionadas (T07, T09...).
- Cada clase, método y función pública tiene un docstring estilo Google en español, con `Args`, `Returns`, `Raises` (cuando aplica) y un `Example` corto cuando ayuda.
- Todas las firmas públicas llevan anotaciones de tipo.
- Los comentarios en línea explican el porqué (una decisión, una restricción, un truco), nunca repiten lo que hace el código.
- Las constantes tienen un comentario con su significado y sus unidades.
- Cada prueba tiene un docstring de una línea que describe el comportamiento que verifica.
- `docs/` es la única fuente de documentación técnica, en español y en Markdown, y se actualiza en el mismo PR que el código que describe.
- La documentación y los docstrings no cambian comportamiento: los commits de documentación no tocan la lógica.

Ejemplo de docstring:

```python
def es_pared(self, x: int, y: int) -> bool:
    """Indica si la casilla es pared.

    Fuera del mapa se considera pared, así quien llama no tiene que revisar límites.

    Args:
        x: Columna.
        y: Fila.

    Returns:
        True si es pared o está fuera del mapa.
    """
```

Los ejemplos de los docstrings se pueden verificar con `python -m pytest --doctest-modules sim`.

## Claves de API

- El agente lee `OPENAI_API_KEY` para `XQ_PROVEEDOR=openai` o `NVIDIA_API_KEY` para `XQ_PROVEEDOR=nvidia`.
- En local: copiar `.env.example` a `.env` y completar la clave. `.env` está en `.gitignore`.
- En Colab: guardar la clave en los secretos del notebook y no escribirla en ninguna celda.
- Nunca se sube una clave al repositorio, ni en código, ni en notebooks, ni en commits.
- Antes de abrir cada PR, correr `git grep -nE "nvapi-[A-Za-z0-9]"` y confirmar que no aparece nada. El patrón busca claves reales (empiezan por `nvapi-`) y no coincide con esta misma línea.
- Las pruebas nunca llaman a la API real: usan un cliente falso que simula las respuestas del modelo.

## Lista de revisión del PR

- [ ] Las pruebas pasan (`pytest`).
- [ ] El código nuevo tiene docstrings, anotaciones de tipo y comentarios según el estándar.
- [ ] `docs/` está actualizado, en especial `contratos.md` si cambió una interfaz.
- [ ] No hay claves en el repositorio (`git grep -nE "nvapi-[A-Za-z0-9]"` sin resultados) ni archivos `.env`.
