# ChessChallendIII — Motor para a III Chess Challenge

## What This Is

Um motor de xadrez para competir na III Chess Challenge: fork do Stockfish em C++, com gestão de tempo escrita pela equipe, um console próprio que opera o protocolo falado da competição e cumpre o log obrigatório, e um pipeline de IA offline que treina e testa o motor antes do evento. Roda 100% local, sem rede, num notebook da própria equipe, sob controle de tempo 15 minutos + 10 segundos por lance.

O objetivo não é participar: é vencer. Toda decisão de escopo abaixo é filtrada por essa pergunta — isto aumenta a chance de ganhar partidas no dia?

## Core Value

**Fechar cada partida com mais tempo restante no relógio do que o adversário, sem nunca perder por tempo.** A competição desempata confrontos empatados pelo tempo total restante somado nas três partidas (Regra 12). Isso torna a gestão de tempo simultaneamente o componente de autoria exigido pela Regra 2 e a alavanca de desempate que nenhuma equipe adversária provavelmente vai modelar.

## Requirements

### Validated

(Nenhum ainda — construir para validar)

### Active

- [ ] Motor derivado do Stockfish compila e joga em C++ no notebook da equipe
- [ ] Gestão de tempo própria substitui o `Timeman` do Stockfish, com algoritmo documentado e defensável como componente decisório (Regra 2)
- [ ] Software replica o tabuleiro físico dos dois lados e mantém estado consistente após cada lance (Regra 5)
- [ ] Operador insere lances do adversário por notação UCI com confirmação, e o software valida legalidade
- [ ] Timer interno espelha o relógio físico, com tecla de sincronização manual quando houver divergência
- [ ] Log obrigatório em `.txt`/`.log` por lance: número, cor, lance UCI, profundidade, nós, avaliação, PV e tempo gasto (Regra 9)
- [ ] Book próprio limitado a 10 meios-lances, carregado localmente (Regra 3)
- [ ] Tablebase local até 5 peças, nunca 6 ou 7 (Regra 4)
- [ ] Pipeline de IA offline: SPRT automatizado, tuning de parâmetros e mineração de derrotas
- [ ] Conformidade auditável: declaração de projeto-base e commit de origem, licença GPLv3, dependências declaradas, nenhuma requisição externa em partida (Regras 1, 14)

### Out of Scope

- **Motor do zero** — teto realista de ~2200–2500 Elo em duas semanas; perde para qualquer fork de Stockfish. Não vence.
- **Rede neural própria treinada pela equipe** — o prazo não permite treinar uma NNUE competitiva, e o risco de regressão de força é alto.
- **LLM jogando durante a partida** — proibido implicitamente pela Regra 14 (sem rede) e inviável por latência. A IA atua offline, como fábrica.
- **Interface gráfica** — a Regra 9 declara linha de comando suficiente. GUI consome tempo sem ganhar Elo.
- **Integração automática com relógio eletrônico** — o regulamento não prevê relógio com saída de dados. Timer interno + sync manual cobre o caso.
- **Tablebases de 6 ou 7 peças** — proibidas pela Regra 4, e substituiriam justamente a lógica de final de jogo avaliada.
- **Book de terceiros como autoria** — permitido pela Regra 3, mas não conta como autoria da equipe; o book será gerado por ferramenta própria.

## Context

**O regulamento é a fonte da verdade.** `docs/competition-rules.md` é a transcrição verbatim do FAQ oficial e não deve ser editado sem confronto com a organização. Cada requisito acima referencia a regra que o origina.

**O que a competição realmente mede.** A Regra 2 exige que a equipe implemente com autoria própria ao menos um componente decisório — avaliação, busca ou gestão de tempo — funcional durante as partidas e defensável na arguição técnica. Reformatação, tradução de comentários, renomeação de variáveis e mero ajuste de parâmetros existentes **não** contam. Isso significa que a autoria precisa ser uma reescrita real, não um patch de constantes.

**Onde o jogo é ganho.** Três assimetrias exploráveis:
1. **Tempo (Regra 12)** — o desempate por tempo total restante é ignorado pela maioria. Um motor que conserva relógio ganha confrontos empatados.
2. **Protocolo falado (Regra 10)** — o lance chega por voz, em UCI, com confirmação e movimento físico. O atraso de entrada é real e a Regra 13 permite ponderar no turno adversário. Um console que trata esse atraso corretamente joga mais forte que um que não trata.
3. **Log obrigatório (Regra 9)** — todos precisam produzir. Quem instrumenta bem usa o log como fonte de diagnóstico pós-partida.

**Ambiente.** Notebook da equipe, sem limite de CPU/threads/RAM declarado (Regra 7), GPU permitida se local e declarada (Regra 8). Wi-Fi e dados móveis desligados e verificados pelo árbitro no início de cada jogo (Regra 14).

**Prazo.** 1 a 2 semanas. Isso é o determinante de escopo mais duro do projeto — não há espaço para construir o que já existe.

## Constraints

- **Licença**: GPLv3 herdada do Stockfish — o repositório precisa ser publicado e disponibilizado à banca (Regra 1). Irrelevante na prática porque o código é entregue de qualquer forma, mas obriga a manter os headers e o aviso de licença intactos.
- **Prazo**: 1 a 2 semanas até o evento — define o escopo; nenhuma fase pode depender de pesquisa longa.
- **Offline**: nenhuma requisição externa durante partidas — toda dependência precisa estar instalada e declarada antes do evento (Regra 14).
- **Protocolo de lance**: UCI falado, confirmação em voz alta, movimento físico, inserção manual no software; o tabuleiro físico é a fonte da verdade e resolve divergências (Regra 10).
- **Book**: máximo 10 meios-lances, depois disso o software decide sozinho (Regra 3).
- **Tablebase**: máximo 5 peças (Regra 4).
- **Log**: formato obrigatório por lance, entregue à banca ao final de cada partida (Regra 9).
- **Hardware**: notebook forte com muitas threads — suficiente para build e SPRT paralelo; define o orçamento de tuning.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fork do Stockfish em C++ em vez de motor do zero | Força máxima dentro do prazo; GPLv3 é irrelevante já que o repo é entregue à banca | — Pending |
| Gestão de tempo própria como componente de autoria principal | Maior ganho de Elo por esforço no TC 15+10, e endereça diretamente o desempate da Regra 12 | — Pending |
| Política de partida como reforço condicional | Fecha o flanco da arguição "isso é só ajuste de parâmetro" sem comprometer o prazo se não houver folga | — Pending |
| Avaliação própria e NNUE própria fora do escopo | Prazo não permite treinar rede competitiva; risco de regressão supera o ganho | — Pending |
| IA como fábrica offline (SPRT, tuning, mineração), não como jogadora | Rede proibida em partida; o valor da IA está em multiplicar o trabalho das 3 pessoas antes do evento | — Pending |
| Console próprio com timer interno + tecla de sync | O relógio é físico e não tem saída de dados; sync manual aproxima o software do relógio real sem digitação a cada lance | — Pending |
| Três frentes paralelas (tempo / console / pipeline) | Blocos quase independentes, permitem 3 pessoas sem conflito de merge | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-26 after initialization*
