# Gramática G = (V, Σ, R, S)

Fuente de verdad del proyecto. **No se modifica.**

## Símbolo inicial
S = PROG

## No terminales
V = {PROG, RESTO, SENT, INSTR, OPB, OPS, FREG, FMEM, INM, DEST, MEM, EXP, EXP', TERM, ESC, ESCALA, REG, IDX, PILA}

## Terminales (Σ)
- Mnemónicos: `MOV ADD CMP JMP`
- IDX (22): `RAX RBX RCX RDX RSI RDI RBP R8 R9 R10 R11 R12 R13 R14 R15 EAX EBX ECX EDX ESI EDI EBP`
- PILA (2): `RSP ESP`
- Puntuación: `,  :  [  ]  +  -  *`
- Escalas: `1 2 4 8`
- `num`: clase de terminal, regex `^(0[xX][0-9A-Fa-f]+|[0-9]+)$`
- `id`: clase de terminal, regex `^[A-Za-z_][A-Za-z0-9_]*$` que NO sea mnemónico ni registro (comparación sin mayúsculas)

## Producciones
```
R1  PROG   → SENT RESTO
R2  RESTO  → SENT RESTO
R3  RESTO  → ε
R4  SENT   → id :
R5  SENT   → INSTR
R6  INSTR  → OPB OPS
R7  INSTR  → JMP DEST
R8  OPB    → MOV
R9  OPB    → ADD
R10 OPB    → CMP
R11 OPS    → REG , FREG
R12 OPS    → MEM , FMEM
R13 FREG   → REG
R14 FREG   → MEM
R15 FREG   → INM
R16 FMEM   → REG
R17 FMEM   → INM
R18 INM    → num
R19 INM    → - num
R20 DEST   → id
R21 DEST   → REG
R22 DEST   → MEM
R23 MEM    → [ EXP ]
R24 EXP    → TERM EXP'
R25 EXP'   → + TERM EXP'
R26 EXP'   → - TERM EXP'
R27 EXP'   → ε
R28 TERM   → IDX ESC
R29 TERM   → PILA
R30 TERM   → num
R31 ESC    → * ESCALA
R32 ESC    → ε
R33 ESCALA → 1 | 2 | 4 | 8            (4 producciones)
R34 REG    → IDX
R35 REG    → PILA
R36 IDX    → cualquiera de los 22 IDX  (22 producciones)
R37 PILA   → RSP | ESP                 (2 producciones)
```
Total: 62 producciones.

## Convenciones
- Mnemónicos y registros se aceptan sin distinguir mayúsculas; en el árbol se muestran en MAYÚSCULAS. Las etiquetas (`id`) conservan su escritura original.
- Los tokens `1, 2, 4, 8` son ESCALA solo justo después de `*`; en cualquier otra posición son `num`.
- Posiciones de error 1-based. El fin de entrada se representa como `$`.

## Conjuntos FIRST
Σ_reg = IDX ∪ PILA (los 24 registros).

| No terminal | FIRST |
|---|---|
| PROG, SENT | {id, MOV, ADD, CMP, JMP} |
| RESTO | {id, MOV, ADD, CMP, JMP, ε} |
| INSTR | {MOV, ADD, CMP, JMP} |
| OPB | {MOV, ADD, CMP} |
| OPS | Σ_reg ∪ {[} |
| FREG | Σ_reg ∪ {[, num, -} |
| FMEM | Σ_reg ∪ {num, -} |
| INM | {num, -} |
| DEST | Σ_reg ∪ {id, [} |
| MEM | {[} |
| EXP, TERM | Σ_reg ∪ {num} |
| EXP' | {+, -, ε} |
| ESC | {*, ε} |
| ESCALA | {1, 2, 4, 8} |
| REG | Σ_reg |
| IDX | los 22 IDX |
| PILA | {RSP, ESP} |

## Conjuntos FOLLOW
| No terminal | FOLLOW |
|---|---|
| PROG, RESTO | {$} |
| EXP, EXP' | {]} |
| TERM, ESC | {+, -, ]} |

## Cadenas de referencia
| Nombre | Cadena | Resultado esperado |
|---|---|---|
| w1 | `inicio : MOV RAX , [ RBX + RCX * 4 + 0x10 ] JMP inicio` | Válida |
| w2 | `CMP [ RBP - 8 ] , - 1 JMP [ RSP + RDI * 8 ]` | Válida |
| w_a | `MOV RAX , [ RBP - 8 + 4 ]` | Válida (ejemplo de ambigüedad de G₀) |
| w3 | `MOV [ RAX ] , [ RBX ]` | Inválida: posición 6, encontrado `[`, esperado registro, número o `-`, en FMEM |
| — | `MOV 5 , RAX` | Inválida: posición 2, en OPS |
| — | `MOV RAX , [ RAX + RSP * 4 ]` | Inválida: posición 8, en EXP' |
| — | `ADD RAX , [ RBX * 3 ]` | Inválida: posición 7, en ESCALA |
| — | `JMP` | Inválida: posición 2, encontrado `$`, en DEST |
