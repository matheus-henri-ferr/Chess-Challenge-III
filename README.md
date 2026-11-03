# Chess Challenge III: motor local

## Motor de competição: Stockfish 19 + gestão de tempo da equipe

Declaração para o credenciamento:

- Projeto-base: Stockfish 19, tag `sf_19`, commit `edb0d9db6731067ec50ce619ff372b463bc4dd5d` (https://github.com/official-stockfish/Stockfish). Licença GPLv3: o código derivado completo (pasta `stockfish/`) deve ser publicado e entregue à banca.
- Componente decisório de autoria da equipe: gestão de tempo, em `stockfish/src/timeman.cpp` (`TimeManagement::init`). Ela substitui a fórmula original e reserva no relógio o tempo gasto com anúncio, repetição, movimento da peça e acionamento do relógio (opção `Move Overhead`).
- Outra alteração no Stockfish: em `stockfish/src/engine.cpp`, o máximo da opção `Move Overhead` passou de 5000 para 15000 ms. O `partida.py` usa 6000 ms por padrão (`--overhead`), que é o tempo estimado de cada lance fora da busca: digitar o relógio, anunciar, esperar a repetição, mover a peça e apertar o relógio. Meça isso num ensaio com a equipe e ajuste.
- Avaliação: rede NNUE oficial `nn-1a298aa575a0.nnue`, de terceiros, embutida no binário. Não conta como autoria.
- Sem book, sem tablebases (a menos que `--syzygy` seja usado com até 5 peças), sem GPU, sem rede.
- Dependências: `requirements.txt` (python-chess), MinGW g++ 15.2 e o shell do Git para compilar.

Compilar (PowerShell, em `stockfish/src`, com a rede `.nnue` já na pasta):

~~~
$env:PATH = 'C:\Program Files\Git\usr\bin;' + $env:PATH
mingw32-make -j12 build ARCH=x86-64-bmi2 COMP=mingw
Copy-Item stockfish.exe ..\..\stockfish_tm.exe
~~~

`stockfish.exe bench` deve imprimir `Bench: 2497913` (a busca é a original; só o tempo muda).

Partida física:

~~~
python partida.py white partida-01.log
python partida.py black partida-02.log
python partida.py white partida-01.log --retomar
~~~

Na sua vez, digite o tempo restante do NOSSO relógio físico (`812`, `13:32`) ou Enter para usar a estimativa. Anuncie o lance mostrado em `>>> ANUNCIE`, espere a repetição, mova a peça, aperte o relógio e só então digite Enter/`ok`. Se o lance físico foi outro, digite o lance real. Na vez do adversário, o motor calcula enquanto espera; digite o lance dele em UCI depois da repetição. O log (separado por tab) traz lance, cor, UCI, profundidade, nós, avaliação do ponto de vista das brancas, PV, tempo em ms e origem. Ele é regravado a cada lance; um log existente não é sobrescrito sem `--retomar`. Armageddon: `--tempo-inicial 300 --incremento 0` (brancas) ou `--tempo-inicial 240 --incremento 0` (pretas).

## Motor próprio antigo (não usado na competição)

Motor C++ independente (não é fork de Stockfish). Componentes decisórios implementados neste projeto: avaliação material/PST, busca negamax com aprofundamento iterativo, quiescência, tabela de transposição e **gestão de tempo adaptativa** em `tournament.cpp` (`allocateTime`). Não usa rede, GPU, book nem tablebases. Dependências: compilador C++17; Python 3 apenas para testes. Não promete vitória: meça a força antes do evento.

## Compilar (Windows/MinGW)

```
g++ -O3 -march=native -std=c++17 -DNDEBUG -o engine.exe main.cpp tabuleiro.cpp xadrez.cpp ui.cpp tournament.cpp
python tests/test_engine.py
```

Se trocar `-march=native` por outro notebook, **recompile naquele notebook**. Com GCC/Linux, use `-o engine` e `./engine`.

## Partida física

```
engine.exe tournament white partida-01.log
engine.exe tournament black partida-02.log
```

Use arquivo de log **novo para cada partida**: o comando sobrescreve o arquivo indicado. Oriente-se pelo tabuleiro físico; lance apenas notação UCI (`e2e4`, `e7e8q`). Antes de buscar, informe o tempo **restante** da sua equipe em segundos, lido no relógio físico, não o tempo inicial. O incremento configurado é 10 segundos. Para Armageddon sem incremento, ajuste `incrementMs` em `tournament.cpp` para `0` e recompile; confirme primeiro as regras específicas do desempate. `ok` confirma o lance **após** anúncio, repetição pelo adversário, movimento físico e acionamento do relógio. Se fez outro lance, informe o lance real em UCI no lugar de `ok`. Insira o lance adversário só depois de sua confirmação no tabuleiro. `desfazer` remove o último lance **também do log**; confira o tabuleiro físico antes de continuar. `tabuleiro` imprime a posição; `sair` encerra. Não digite tempos ou lances durante a busca.

Cada linha do `.log` contém número do lance, cor, UCI, profundidade, nós, avaliação em centipeões da perspectiva de quem joga, PV e tempo de busca em ms. Nas jogadas adversárias, profundidade/nós/tempo são `0`: **não houve busca do nosso motor**; a avaliação é estática antes do lance, e a PV contém o lance observado. Se o lance físico divergir do lance sugerido, profundidade fica `0` e a PV contém o lance efetivamente executado. O log é descarregado após cada lance.

Outros comandos: `engine.exe perft 5`, `engine.exe selfplay 0.1 80`, `engine.exe play`. O teste `perft 5` deve produzir `4865609`. Teste capturas en passant, roque, promoção, xeque e sincronização com o tabuleiro antes da competição. Sem garantia de Elo: comparar contra outros motores requer partidas com relógios e cores alternadas.

## Origem e regras

Declare à banca a origem/commit do projeto-base real. Este diretório **não contém histórico Git**: não invente hash ou autoria anterior. Se optar por integrar Stockfish, mantenha a modificação decisória própria ativa, declare sua versão/commit de origem, respeite GPLv3 e entregue o código-fonte derivado completo. Não carregue book depois de 10 meios-lances nem tablebases de 6/7 peças. Esta versão não usa nenhum deles.
