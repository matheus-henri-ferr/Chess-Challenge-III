# Plano A — Performance (mailbox, sem bitboards)

Objetivo: mais nós/segundo e mais profundidade no mesmo tempo, **sem alterar as decisões da busca**.
Gate único: `perft` idêntico em todas as profundidades.

Estado atual (medição de referência obrigatória antes de qualquer mudança):

```
perft(1) = 20
perft(2) = 400
perft(3) = 8902
perft(4) = 197281
perft(5) = 4865609
```

---

## Fase A1 — Quick wins sem mudar arquitetura (estimativa 2–4x)

| # | Tarefa | Arquivos |
|---|---|---|
| A1.1 | `struct MoveList { Move m[256]; int n; }` substituindo `vector<Move>` em geração, quiescence e negamax | `tabuleiro.h`, `tabuleiro.cpp:294`, `xadrez.cpp:229,264` |
| A1.2 | Eliminar a dupla aplicação do lance: hoje `genLegalMoves` aplica `makeMove` para testar legalidade e `negamax` aplica de novo (`xadrez.cpp:265` + `:280`). Passar a iterar pseudo-lances, aplicar uma vez, testar `inCheck` do lado que moveu, e detectar mate/afogamento pela contagem de legais | `xadrez.cpp:244-301` |
| A1.3 | `orderMoves` com selection-sort sob demanda (melhor lance restante por iteração), eliminando os dois vetores auxiliares e o `sort` completo | `xadrez.cpp:206-221` |
| A1.4 | Cachear posição dos reis no `Board` (`int8_t kingSq[2]`), `findKing` O(1) | `tabuleiro.h`, `tabuleiro.cpp:174` |
| A1.5 | `genPseudoCaptures` (capturas + promoções) para a quiescence, com teste de legalidade sob demanda | `tabuleiro.cpp`, `xadrez.cpp:230` |
| A1.6 | Checar `halfmoveClock >= 100` **antes** de gerar lances | `xadrez.cpp:272` |
| A1.7 | `Move` com cópia trivial (campos contíguos, sem bools dispersos) — opcional, mantém mailbox | `tabuleiro.h` |

**Aceitação:** `perft 1..5` com os valores acima; `bench` com melhora de tempo mensurável.

---

## Fase A2 — Estado incremental (estimativa 2–3x)

| # | Tarefa |
|---|---|
| A2.1 | `makeMove`/`unmakeMove` com `struct Undo { int8_t captured; int8_t ep; uint8_t castle; int halfmove; uint64_t hash; int evalScore; int kingSq[2]; }` — fim das cópias de `Board` (`tabuleiro.cpp:247`) |
| A2.2 | Zobrist incremental: XOR das peças/castle/ep alterados dentro de make, restaurado no unmake; remover a varredura de 64 casas de `computeHash` (`xadrez.cpp:37`) |
| A2.3 | Avaliação incremental: manter `materialAndPstScore` no `Undo`; `evaluate` vira O(1) (`xadrez.cpp:135`) |
| A2.4 | Pilha de hashes para repetição na busca (reaproveitada pelo Plano B) |
| A2.5 | Ajustar `negamax`, `quiescence`, `perft` e o loop raiz para o par make/unmake |

**Aceitação:** `perft` idêntico; **mesma árvore** — com ordem de lances fixa e profundidade fixa, a
contagem de nós deve ser igual à versão anterior.

---

## Fase A3 — Geração de lances mailbox otimizada (estimativa 2–4x adicional)

Sem bitboards.

| # | Tarefa |
|---|---|
| A3.1 | Board 0x88 ou 10x12 (com borda) para eliminar `onBoard`/`sqOf` do hot path |
| A3.2 | Tabelas pré-computadas `knightAttacks[64]`, `kingAttacks[64]`, `pawnAttacks[2][64]` |
| A3.3 | Tabelas de raios: `rayTargets[64][8]` com comprimento por direção, evitando recomputar `f±d`, `r±d` |
| A3.4 | Listas de peças incrementais (`pieceList[13][n]` + `index[64]`) para iterar só peças existentes |
| A3.5 | `isSquareAttacked` usando listas de peças + raios pré-computados (fim da varredura de 64 casas — `tabuleiro.cpp:38`) |
| A3.6 | Tabelas `between[64][64]` / `beyond[64][64]` pré-computadas (base para SEE e checagens) |

**Aceitação:** `perft 1..5` idêntico; `bench` com NPS medido antes/depois.

---

## Fase A4 — Build e micro-otimizações

| # | Tarefa |
|---|---|
| A4.1 | `-O3 -march=native -flto -DNDEBUG` |
| A4.2 | Trocar `throw TimeUp` por retorno com flag (exceção no hot path custa) — ou manter isolado e medir |
| A4.3 | Comando `bench` determinístico (nós fixos sobre posições fixas) como gate de regressão de velocidade |
| A4.4 | TT alinhada a 64 bytes; evitar `iostream` no hot path (`cerr` do ID pode ir para buffer) |

---

## Dependências

`A1 → A2 → A3 → A4`.

Não iniciar A3 antes de A1.2/A1.3 (senão você otimiza código que será reescrito).

---

## Guardrails

1. `perft` como gate obrigatório a cada commit.
2. `bench` (nós/tempo) antes/depois de cada fase.
3. Uma fase por commit, mensagem com números medidos.
4. Nenhuma mudança de comportamento de busca dentro do Plano A.
