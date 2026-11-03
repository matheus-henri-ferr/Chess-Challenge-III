# Plano B — Rating (força de jogo)

Objetivo: jogar melhor, não só mais rápido. **Toda** mudança de força passa por SPRT.

Referência de partida: rating atual **não medido** (estimativa ~1400–1600, ±150 em TC curto).
Alvo após A1+A2+B1–B5: ~1900–2200.

---

## Fase B0 — Infraestrutura de medição (pré-requisito absoluto)

Hoje só existe `play`, `perft` e `selfplay` — impossível comparar versões.

| # | Item |
|---|---|
| B0.1 | Protocolo **UCI**: `uci`, `isready`, `position ... moves`, `go depth/nodes/movetime/wtime/btime`, `stop`, `quit`, `ucinewgame`, `setoption` |
| B0.2 | Comando `bench`: ~30 posições fixas, busca em nós fixos, imprime nós/tempo |
| B0.3 | Limites determinísticos por `depth` e `nodes` (base dos testes reproduzíveis) |
| B0.4 | Harness: `fastchess` ou `cutechess-cli`, 2 binários, cores alternadas, livro curto, `-repeat`, TC `10+0.1` |
| B0.5 | Suíte EPD de sanidade: ~50 posições (mates em N, táticas, empates técnicos) |
| B0.6 | Protocolo **SPRT** bounds `[0,5]`, α=β=0.05 |
| B0.7 | Medir o **rating atual** contra pool de referência (Stockfish com `UCI_LimitStrength` 1500/1800/2100 + motores de clube) |

**Elo direto: 0. Sem isso, nenhum ganho é verificável.**

---

## Fase B1 — Correção de bugs que custam rating

| # | Problema | Local | Correção | Elo est. |
|---|---|---|---|---|
| B1.1 | Score de mate na TT sem ajuste de ply → mate score poisoning | `xadrez.cpp:296-297` | `score ± ply` ao guardar/procurar | +5–10 |
| B1.2 | Corte `TT_EXACT` ignora repetição/50 lances no caminho | `xadrez.cpp:252-257` | Não cortar em score de empate; checar 50 lances antes do probe | +5–10 |
| B1.3 | Sem detecção de repetição dentro da busca | ausente | Pilha de hashes (A2.4) retornando 0 | +10–20 |
| B1.4 | Sem material insuficiente (K vs K, KN vs K) | ausente | Detecção no nó | +5–10 |
| B1.5 | Sem mate distance pruning | `negamax` | Poda clássica | +3–8 |
| B1.6 | `halfmoveClock` checado depois de gerar lances | `xadrez.cpp:272` | Mover para o início (coberto por A1.6) | +2–5 |
| B1.7 | Quiescence sem guarda de 50 lances/empate | `xadrez.cpp:223` | Guarda de empate | +2–5 |
| B1.8 | `Move{}` com `from=-1` retornado (`xadrez.cpp:313`) pode causar UB | `searchBestMove` | Sentinela explícita / checagem | correção |

**Gate:** `perft` inalterado + EPD sem regressão de mates.

---

## Fase B2 — Busca (maior retorno)

| Ordem | Técnica | Elo est. | Risco |
|---|---|---|---|
| B2.1 | **PVS** (null-window após o 1º lance) | +20–35 | Baixo |
| B2.2 | **Null-move pruning** (R=2–3, bloqueado em xeque/zugzwang, condicional em final) | +50–80 | Médio |
| B2.3 | **LMR** (reduzir lances tardios não-captura, re-buscar em falha) | +40–70 | Médio |
| B2.4 | **Aspiration windows** por iteração | +10–20 | Baixo |
| B2.5 | **SEE** para ordenar capturas (usa `between/beyond` do A3.6) | +25–45 | Baixo |
| B2.6 | **Futility / reverse futility pruning** | +20–40 | Médio |
| B2.7 | TT em clusters (2–4 slots), aging por geração, cache de eval | +15–30 | Baixo |
| B2.8 | Check extension (limite 1–2) | +5–15 | Baixo |
| B2.9 | Killer/history refinados (bônus por profundidade, penalização de falhas) | +10–20 | Baixo |
| B2.10 | **Time management** real (soft/hard, fração por instabilidade) | +20–40 | Baixo |

Não implementar B2.2/B2.3 antes de B1.1–B1.3: os bugs se mascaram.

---

## Fase B3 — Avaliação (segundo maior retorno, sem bitboards)

| # | Item | Elo est. |
|---|---|---|
| B3.1 | **Tapered eval (mg/eg)** por fase; tabela de rei de final separada | +30–50 |
| B3.2 | **Mobilidade** por peça (contagem por raio com ocupância; em mailbox custa NPS — medir) | +25–40 |
| B3.3 | Segurança do rei: escudo de peões, colunas abertas, atacantes na zona | +30–60 |
| B3.4 | Estrutura de peões: dobrados, isolados, atrasados, cadeias | +25–45 |
| B3.5 | Peão passado (bônus por avanço, torre atrás) | +20–35 |
| B3.6 | Par de bispos, bispo bom/ruim | +10–20 |
| B3.7 | Torre em coluna aberta/semi-aberta, torre na 7ª | +10–25 |
| B3.8 | Espaço / desenvolvimento | +10–20 |
| B3.9 | Drawishness (material reduzido, bispos de cores opostas) | +5–15 |

---

## Fase B4 — Tunagem automática (opcional, após B1–B3 estáveis)

| # | Item | Elo est. |
|---|---|---|
| B4.1 | **Texel tuning** dos pesos de eval (dataset FEN + resultado) | +30–60 |
| B4.2 | **SPSA** para parâmetros de busca (R de null-move, margens de LMR/futility) | +20–40 |
| B4.3 | Holdout set e validação em TC longo (anti-overfitting) | evita perda |

---

## Fase B5 — Ganhos de torneio

| # | Item | Elo est. |
|---|---|---|
| B5.1 | Livro de abertura (Polyglot pequeno ou linhas hardcoded) | +20–40 (TC curto) |
| B5.2 | Pondering (se o GUI suportar) | +10–30 efetivo |
| B5.3 | Regras de repetição/50 lances corretas na raiz | +5–15 |
| B5.4 | Fallback de tempo seguro (nunca estourar o relógio) | +10–20 |

---

## Guardrails

1. Nenhuma mudança entra sem SPRT ≥ 0 (bounds `[0,5]`).
2. Um commit por técnica, com resultado do SPRT na mensagem.
3. `perft` + `bench` como gate de CI a cada commit.
4. EPD: nenhuma posição de mate pode regredir.
5. Eval e busca nunca no mesmo commit.
6. Parametrizar em TC curto, confirmar em TC longo.
7. Manter o binário anterior (`engine_base.exe`) para A/B imediato.
