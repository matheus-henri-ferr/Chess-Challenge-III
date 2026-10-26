# Requirements: ChessChallendIII

**Defined:** 2026-10-26
**Core Value:** Fechar cada partida com mais tempo restante no relógio do que o adversário, sem nunca perder por tempo.

**Prazo:** 5 de novembro de 2026 — 10 dias corridos a partir de 26/10.
**Referência normativa:** `docs/competition-rules.md` (transcrição verbatim do FAQ oficial). Todo requisito abaixo referencia a regra que o origina.

---

## v1 Requirements

Requisitos para a entrada na competição. Cada um mapeia para exatamente uma fase do roadmap.

### Fundação e Conformidade

- [ ] **FOUND-01**: O repositório é um `git clone --branch sf_19` real com histórico upstream preservado e tag `base-sf19`, e `NOTICE` registra URL, SHA completo, tag, data do fork, arquivos modificados, comando de build, `ARCH`, versão do compilador e contagem de nós do bench (R1)
- [ ] **FOUND-02**: `Copying.txt` e `AUTHORS` permanecem byte-intactos; todo arquivo tocado conserva o header GPLv3 original mais uma linha datada de modificação (R1)
- [ ] **FOUND-03**: `PROVENANCE.md` declara o nome, tamanho, SHA-256 e origem da rede NNUE, o inventário de tablebases e o manifesto de dependências; a rede é marcada explicitamente como "não autoral" (R1, R15)
- [ ] **FOUND-04**: O build funciona completamente offline — `make net` executado antes do evento, árvore arquivada, e um `unshare -n make -j` limpo é provado no notebook da partida (R14)
- [ ] **FOUND-05**: `docs/PROTOCOL.md` e `docs/LOGBOOK.md` estão congelados e versionados antes de qualquer commit de implementação, definindo a linha `go` exata, o formato do trace do TM e o schema dos oito campos do log (R9, R10)
- [ ] **FOUND-06**: Repositório público ou acesso ao painel verificado por dry run; arquivo em USB iniciado (R1)

### Conformidade de Limites

- [ ] **LIMIT-01**: `SyzygyProbeLimit` é forçado a 5 no startup (o default upstream é 7) e `MaxCardinality` é assertado; o valor efetivo aparece no checklist pré-jogo (R4)
- [ ] **LIMIT-02**: O diretório de tablebases contém apenas arquivos de 3, 4 e 5 peças, com inventário SHA-256 e um scan de nomes de arquivo que falha ruidosamente se qualquer peça > 5 estiver presente (R4)
- [ ] **LIMIT-03**: O loader de book rejeita qualquer linha com mais de 10 meios-lances, contados a partir do início da partida, com `BOOK_MAX_PLY = 10` como constante única e teste de fronteira (R3)
- [ ] **LIMIT-04**: Nenhuma requisição externa em partida; todas as dependências instaladas e declaradas em manifesto, e um `doctor` de startup falha se algum caminho de asset for remoto ou relativo (R14)

### Protocolo Falado e Tabuleiro

- [ ] **PROTO-01**: Parser UCI estrito aceita `e2e4`, `g1f3`, `e7e8q` e roques `e1g1`/`e1c1`, tolera caixa e espaços, e rejeita SAN (`Nf3`, `e4`, `O-O`), `0000` e tokens malformados com erro tipado; todo token rejeitado é logado como evidência (R10)
- [ ] **PROTO-02**: Réplica do tabuleiro mantém FEN autoritativo e lista ordenada de lances, avançada apenas por lances validados, cobrindo os dois lados (R5)
- [ ] **PROTO-03**: Lance anunciado ilegal não avança o estado; o loop de entrada permanece vivo, o operador é instruído a anunciar outro, e o evento é logado com timestamp; um `bestmove` ilegal nunca é exibido (R10)
- [ ] **PROTO-04**: Campo ANNOUNCE é populado exclusivamente por `bestmove`, renderizado em maiúsculas com separador (`E2-E4`, `E7-E8=Q`), visualmente distinto da PV e travado até o `bestmove` chegar (R10)
- [ ] **PROTO-05**: Máquina de estados explícita `IDLE → OUR_SEARCH → ANNOUNCE_PENDING → AWAIT_OPP_CONFIRM → OPP_TURN/PONDERING`, com tabela de transições e guarda de lado-a-jogar que rejeita dois lances consecutivos do mesmo lado (R10, R13)
- [ ] **PROTO-06**: Entrada do operador é só teclado, sempre focada, tolerante a colagem, com eco imediato do lance parseado e do FEN resultante, e cue de rejeição audível ou visual (R10)
- [ ] **PROTO-07**: Resync a partir do tabuleiro: o operador declara divergência, o estado é reconstruído preferindo "reentrar os últimos N lances" a edição livre de FEN, com confirmação e registro `RESYNC` anexado ao journal e ao log — nunca reescrevendo o histórico (R10)
- [ ] **PROTO-08**: Relógio do adversário é capturado a cada passagem de turno por um único atalho (`t 7:42`), tolerante a formatos alternativos, armazenado no journal e no log (R7, R12)

### Relógio e Resiliência

- [ ] **CLOCK-01**: Modelo de relógio duplo calcula nossa crença a partir de deltas de `monotonic_ns()` — nunca por tick — com backdating de `input_latency` no evento de entrada do lance e incremento adicionado no pressionar (R7, R12)
- [ ] **CLOCK-02**: Uma tecla SYNC re-baseia a estimativa ao relógio físico mesmo durante busca, exibe `previsto/observado/delta`, e exige segunda confirmação para divergências acima de 5 s (R7)
- [ ] **CLOCK-03**: Todo cálculo de deadline usa o pessimista entre estimativa de software e leitura física, com drift visível na tela (R7, R12)
- [ ] **CLOCK-04**: Watchdog do console dispara `stop` (nunca `quit`) em `crença − margem`, independente do timer interno do motor, com modo scramble abaixo do piso de emergência (R7)
- [ ] **CLOCK-05**: Supervisão do motor detecta morte ou travamento, reinicia, reproduz `position` e sempre mantém um lance legal de fallback disponível a partir da última PV completa (R5, R7, R10)
- [ ] **CLOCK-06**: Journal append-only com `fsync` por registro permite `resume` reconstruindo a partida completa após `kill -9` (R5)
- [ ] **CLOCK-07**: Console detecta tripla repetição e regra dos 50 lances de forma independente do motor, mantendo histórico de chaves de posição, e alerta o operador para chamar o árbitro (R12)
- [ ] **CLOCK-08**: Resultado, motivo e ambos os relógios no instante do término são registrados, com suporte a desistência e empate acordado, e o log é congelado (R9, R12)
- [ ] **CLOCK-09**: Modelo de match persiste índice de partida, nossa cor por partida com a regra de que a terceira repete a cor da primeira, registro de tempo restante por partida, totais correntes de desempate e flag de Armageddon (R11, R12)

### Log Obrigatório

- [ ] **LOG-01**: Um arquivo `.log` por partida, append-only, com flush incremental, contendo os oito campos obrigatórios para **cada meio-lance, incluindo os do adversário** (R9)
- [ ] **LOG-02**: Os oito campos são número do lance, cor, lance escolhido em UCI, profundidade, nós, avaliação, PV e tempo gasto; `score` é registrado verbatim incluindo `mate N` e flags de bound (R9)
- [ ] **LOG-03**: Tempo gasto registra tanto `engine_ms` (do `info` UCI) quanto `wall_ms` (relógio de parede), resolvendo a ambiguidade de "tempo gasto" (R9)
- [ ] **LOG-04**: Lances de book aparecem com `src=book`, `d=0`, `n=0`, e lances terminais também são logados com campos não-vazios (R9, R3)
- [ ] **LOG-05**: Comando `export-log` entrega o arquivo bruto ao árbitro ao final de cada partida, com header contendo o conjunto completo de opções e hashes dos assets, e trailer com relógios finais e hash do log (R9)

### Checklist Pré-Jogo

- [ ] **CHECK-01**: Um comando único imprime e asserta identidade do motor e commit base, `SyzygyProbeLimit` efetivo, contagem de linhas e ply máximo do book, caminho do log gravável, caminhos de asset locais e absolutos, threads e hash, GPU declarada ou não, e asserção de rede limpa (R1, R3, R4, R8, R14)

### Autoria — Gestão de Tempo

- [ ] **TM-01**: Alocador de tempo escrito do zero atrás da interface `TimeManagement` preservada (`init`, `optimum`, `maximum`, `elapsed`, `clear`), de modo que `search.cpp` não precise de edição (R2)
- [ ] **TM-02**: `docs/timeman/00-DESIGN.md` é commitado **antes** do commit de implementação (R2)
- [ ] **TM-03**: O alocador recebe entradas que o upstream não tem: latência medida p50/p95 do protocolo, relógio do adversário, banco de tempo do match, índice da partida e contexto de Armageddon (R2, R12)
- [ ] **TM-04**: O alocador mantém estado novo: banco de segundos, modelo de latência, reserva e histórico de gasto (R2)
- [ ] **TM-05**: A lei de controle é nova: orçamento restrito por reserva sobre os lances restantes esperados, em vez do polinômio fechado em `ply` do upstream (R2)
- [ ] **TM-06**: O alocador produz saídas novas: orçamento, flag de instant-move e código de razão (R2)
- [ ] **TM-07**: Um termo de overhead de protocolo medido é aplicado, clampado em `[1200, 6000]` ms, default 3500, carregado via opção `TM Latency` (R2, R13)
- [ ] **TM-08**: Banking ciente de incremento: solvência `spend < inc − overhead`, alvo de 2–4 s adiantado, com `banked_seconds` como valor de primeira classe (R12)
- [ ] **TM-09**: Invariante de máximo duro `maximum ≤ time[us] − exec_tail − safety` que torna o flag estruturalmente impossível (R7)
- [ ] **TM-10**: Modos `sudden_death` e `armageddon` além de `increment` (R12)
- [ ] **TM-11**: O motor emite `info string tm=custom-vX.Y mode=… latency_p95_ms=… bank_ms=… budget_ms=… reason=…` no início de cada busca, e o console copia essa linha para o log daquele lance (R2)
- [ ] **TM-12**: Opção `TimeManager=upstream|custom` existe para ablação, com `custom` como default de jogo e um self-test de startup que falha ruidosamente se o caminho custom não estiver ativo (R2)
- [ ] **TM-13**: A cláusula de +25% do upstream em `Ponder` é removida e o ponder é tratado como economia de tempo (R13)

### Defesa de Autoria

- [ ] **AUTH-01**: `AUTHORSHIP.md` de duas páginas contém a alegação em uma frase, a tabela de mapeamento da Regra 2, o que é novo, o que é herdado com file:line, as não-alegações explícitas, a receita de verificação de 60 segundos e o índice de evidências (R2)
- [ ] **AUTH-02**: `docs/timeman/01-ALGORITHM.md` documenta pseudocódigo, invariantes, modos de falha e complexidade (R2)
- [ ] **AUTH-03**: `docs/timeman/02-EVIDENCE.md` contém ablação A/B no mesmo binário em 15+10 com latência humana simulada, relatando Elo, V/E/D, time forfeits, relógio restante médio e vitórias de desempate (R2)
- [ ] **AUTH-04**: `docs/timeman/03-DEFENSE.md` contém roteiro de 3 minutos e as 15 perguntas antecipadas, e os três membros conseguem explicar algoritmo, evidência e diff (R2)
- [ ] **AUTH-05**: `docs/timeman/04-DECISIONS.md` é um log de decisões datado explicando por que X e não Y (R2)
- [ ] **AUTH-06**: `experiments/timeman-ablation/run.sh` reproduz a tabela de evidência com um comando (R2)
- [ ] **AUTH-07**: O teste de reversão está documentado: reverter a mudança a uma única constante ou fator de escala remove uma decisão que o motor não consegue mais tomar (R2)

### Pipeline Offline de IA

- [ ] **PIPE-01**: fastchess v1.8.2-alpha instalado e funcionando, com receita SPRT documentada (`elo0=0 elo1=5 alpha=beta=0.05`, `tc=10+0.1`, `-repeat`, `option.Move_Overhead=100` nos dois motores, `-report penta=true`) (R2)
- [ ] **PIPE-02**: Um gate de regressão de 200–400 partidas contra o TM upstream roda como verificação, não como campanha de tuning (R2)
- [ ] **PIPE-03**: Harness de injeção de falhas dirige o stdin do console com atrasos jitterizados de 0,5–6 s e asserta ausência de lance duplo, avanço em entrada ilegal, campo de log faltante, lado errado a jogar, contabilidade de tempo errada e zero timeouts (R10, R13)
- [ ] **PIPE-04**: Perfil de recursos do notebook da partida é medido — núcleos físicos e não irmãos SMT, `Hash ≤ min(4096 MB, 50% RAM)` — e declarado (R7)
- [ ] **PIPE-05**: Uma execução sustentada de 60 minutos sob carga prova que as suposições de nps do TM se mantêm na terceira partida (R7)

### Prontidão Operacional

- [ ] **OPS-01**: Checklist pré-jogo assinado por partida cobre `rfkill block all`, modo avião, auto-connect e updaters desabilitados, ausência de análise em background, `Hash`/`Threads` verificados, perfil de energia de performance, cabo conectado e superfície rígida (R14)
- [ ] **OPS-02**: Papéis atribuídos — Operador, Cronometrista-Árbitro, Técnico-Analista — com runbook de uma página cobrindo pré-jogo, por lance, por partida e emergência (R10)
- [ ] **OPS-03**: Ritual de entrega do log: um arquivo por partida, exportado ao USB e em papel ao final de cada jogo, nunca editado (R9)
- [ ] **OPS-04**: Demo offline de 3 minutos ensaiada: alternar `upstream|custom` numa posição e relógio roteirizados, mostrando orçamento e tipo de decisão diferentes, uma linha de log real com a atestação, e a tabela de ablação (R2)
- [ ] **OPS-05**: Um rehearsal hostil com as 15 perguntas da banca é executado antes do evento (R2)
- [ ] **OPS-06**: Dress rehearsal completo: Bo3 no tabuleiro físico, com o operador real, UCI falado, offline, no notebook da partida (R10, R14)

## v2 Requirements

Adiado. Rastreado mas fora do roadmap atual.

### Política de Partida e Ponder

- **POL-01**: Política de empate ciente do placar do match, com função de valor de empate dependente de estado
- **POL-02**: Otimizador de tempo total restante através das três partidas, com preço sombra do tempo
- **POL-03**: Wiring completo de ponder (`go ponder` / `ponderhit` / `stop` com descarte por search-id)
- **POL-04**: Perfil de Armageddon com política de cor: pretas com empate = vitória, brancas com empate = derrota
- **POL-05**: Conselheiro de desistência e oferta de empate baseado em valor esperado

### Book

- **BOOK-01**: Book próprio gerado por ferramenta da equipe, limitado a 10 meios-lances, emitindo `.bin` e `.epd`
- **BOOK-02**: Timing de handoff book→motor com pré-aquecimento deliberado no ply 11

### Diagnóstico

- **DIAG-01**: Diagnóstico pós-partida dirigido por log — curva de tempo por lance, oscilações de eval, re-busca de blunders, brief de uma página entre partidas

## Out of Scope

Excluído explicitamente. Documentado para prevenir retorno do escopo.

| Feature | Reason |
|---|---|
| Motor do zero | Teto de ~2200–2500 Elo em duas semanas; perde para qualquer fork de Stockfish |
| Rede neural própria treinada pela equipe | O prazo não permite treinar uma NNUE competitiva; risco de regressão de força supera o ganho |
| LLM jogando durante a partida | Regra 14 proíbe rede em partida; latência inviável. A IA atua offline |
| Interface gráfica | Regra 9 declara linha de comando suficiente; GUI custa tempo sem ganhar Elo |
| Integração automática com relógio eletrônico | O regulamento não prevê relógio com saída de dados |
| Tablebases de 6 ou 7 peças | Proibidas pela Regra 4 |
| Book de terceiros como autoria | Permitido pela Regra 3, mas não conta como autoria da equipe |
| Reconhecimento de tabuleiro por câmera | Complexidade alta, risco de erro catastrófico sob relógio, e a Regra 10 já define o operador humano como entrada |
| Qualquer coisa em rede ou nuvem | Regra 14 |
| UI de torneio ou bracket | Zero ganho de partida |
| Book baixado com mais de 10 plies | Violação da Regra 3 |
| Search ou eval próprios | Pior subsistema possível para brigar em duas semanas; o net oficial já é forte |
| Paridade completa de GUI UCI | Não é o produto |
| SPRT distribuído | Overhead de infraestrutura sem ganho no prazo |
| Contempt como componente de autoria | É explicitamente ajuste de parâmetro pela Regra 2 |

## Traceability

Preenchido durante a criação do roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 … FOUND-06 | Phase 1 | Pending |
| LIMIT-01 … LIMIT-04 | Phase 1, Phase 3 | Pending |
| PROTO-01 … PROTO-08 | Phase 2 | Pending |
| CLOCK-01 … CLOCK-09 | Phase 3 | Pending |
| LOG-01 … LOG-05 | Phase 2 | Pending |
| CHECK-01 | Phase 3 | Pending |
| TM-01 … TM-13 | Phase 4 | Pending |
| AUTH-01 … AUTH-07 | Phase 4, Phase 7 | Pending |
| PIPE-01 … PIPE-05 | Phase 6 | Pending |
| OPS-01 … OPS-06 | Phase 6, Phase 7 | Pending |

**Coverage:**
- v1 requirements: 58 total
- Mapped to phases: 58
- Unmapped: 0 ✓

---
*Requirements defined: 2026-10-26*
*Last updated: 2026-10-26 after initial definition*
