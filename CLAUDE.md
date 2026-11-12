# CLAUDE.md — Analizador sintáctico x86/x64

## Objetivo
Analizador sintáctico descendente recursivo (LL(1)) para un subconjunto de ensamblador
x86/x64 en sintaxis Intel, como trabajo de Teoría de Lenguajes Formales. La raíz del
proyecto es esta misma carpeta (`ensamblador-app`); no se crean subcarpetas contenedoras.

## Requisitos (obligatorios)
- El parser recibe la entrada como una LISTA de terminales ya delimitados.
- NO existe analizador léxico/tokenizer: nada clasifica ni transforma los símbolos antes
  del parser. Solo se permite dividir un texto por espacios en blanco o leer una lista
  literal de Python.
- Cada no terminal de la gramática es exactamente un método del parser (mapeo directo).
- Cadena inválida → error con: posición (1-based), símbolo encontrado (o `$` si terminó la
  entrada), terminales esperados y no terminal que se estaba expandiendo.
- Cadena válida → retornar e imprimir la jerarquía del árbol sintáctico.
- Interfaz gráfica sencilla, bonita y fácil de entender con CustomTkinter, aplicando las
  leyes de la Gestalt (proximidad, similitud, región común, continuidad, figura-fondo).

## Convenciones de código
- Python 3.11+, type hints en todo, dataclasses donde aplique.
- Código, nombres y documentación en INGLÉS: docstring por módulo, clase y función pública
  (qué hace, parámetros, retorno, excepciones y regla de la gramática que implementa).
- No comentar línea por línea; solo comentarios puntuales donde la lógica no sea obvia.
- Textos visibles para el usuario (interfaz, errores, consola) en ESPAÑOL.
- Dependencias: customtkinter, pillow y la librería estándar. Pruebas con unittest.
- Sin código muerto ni prints de depuración.

## Gramática
La fuente de verdad es `docs/GRAMMAR.md`. NO se modifica.
- Mnemónicos y registros: sin distinguir mayúsculas; en el árbol se muestran en MAYÚSCULAS.
- Las etiquetas (`id`) conservan su escritura original.
- `1 2 4 8` son ESCALA solo justo después de `*`; en otra posición son `num`.
- `num`: `^(0[xX][0-9A-Fa-f]+|[0-9]+)$`.
- `id`: `^[A-Za-z_][A-Za-z0-9_]*$` que no sea mnemónico ni registro (sin mayúsculas).
- Posiciones de error 1-based; fin de entrada = `$`.

## Estructura
```
main.py, requirements.txt, README.md, CLAUDE.md, .gitignore
docs/GRAMMAR.md
analyzer/: __init__.py, grammar.py, input_reader.py, parse_tree.py, errors.py,
           parser.py, derivations.py, semantic.py
analyzer/gui/: __init__.py, app.py, theme.py, widgets.py, tree_canvas.py
tests/: __init__.py, test_parser.py, test_derivations.py
```

## Etapas (no avanzar sin confirmación del usuario)
0. Estructura y gramática
1. Módulos base
2. Parser
3. Derivaciones, semántica y CLI
4. Interfaz base
5. Árbol gráfico y derivaciones en la interfaz
6. Pulido y verificación final
