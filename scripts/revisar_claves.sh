#!/bin/sh
# Hook pre-commit de Xenomorfo-Q: bloquea el commit si los cambios preparados agregan algo
# con forma de clave de API (NVIDIA: nvapi-..., OpenAI: sk- seguido de 20 o más caracteres).
#
# Instalación (una vez por clon):
#   cp scripts/revisar_claves.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
#
# Solo revisa las líneas agregadas, y si encuentra algo muestra el nombre del archivo, nunca
# el valor, para que la clave no quede en la terminal ni en ningún registro.

patron='nvapi-[A-Za-z0-9]|sk-[A-Za-z0-9]{20,}'
encontrados=""

# Archivos agregados, copiados, modificados o renombrados en el área de preparación.
for archivo in $(git diff --cached --name-only --diff-filter=ACMR); do
    if git diff --cached -U0 --no-color -- "$archivo" | grep '^+' | grep -v '^+++' | grep -qE "$patron"; then
        encontrados="$encontrados $archivo"
    fi
done

if [ -n "$encontrados" ]; then
    echo "Commit bloqueado: estos archivos agregan algo con forma de clave de API:" >&2
    for archivo in $encontrados; do
        echo "  - $archivo" >&2
    done
    echo "Las claves van solo en .env, que está en .gitignore. Quítala de los cambios y vuelve a intentar." >&2
    exit 1
fi
exit 0
