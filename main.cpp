// ============================================================================
// Chess Challenge III - Motor de Xadrez
// ----------------------------------------------------------------------------
// Arquitetura modular:
//   - tabuleiro.h/.cpp -> tipos, regras, geracao de lances, aplicacao de lances
//   - xadrez.h/.cpp    -> avaliacao, busca (negamax/alpha-beta/TT), perft,
//                         conversao de notacao coordenada
//   - ui.h/.cpp        -> impressao do tabuleiro, partida interativa, selfplay
//   - main.cpp         -> ponto de entrada / despacho de comandos
//
// Como compilar:
//   g++ -O3 -march=native -std=c++17 -o engine main.cpp tabuleiro.cpp xadrez.cpp ui.cpp
//
// Como usar:
//   ./engine play            -> inicia uma partida interativa
//   ./engine perft N         -> roda teste de geracao de lances ate depth N
//   ./engine selfplay S N [s]-> motor contra ele mesmo
// ============================================================================

#include "tabuleiro.h"
#include "ui.h"
#include "xadrez.h"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <string>

using namespace std;
using namespace std::chrono;

int main(int argc, char** argv) {
    initZobrist();

    if (argc >= 2 && string(argv[1]) == "tournament") {
        if (argc < 4 || (string(argv[2]) != "white" && string(argv[2]) != "black")) {
            cerr << "Uso: engine tournament white|black arquivo.log\n";
            return 1;
        }
        return tournamentLoop(string(argv[2]) == "white", argv[3]);
    }

    if (argc >= 2 && string(argv[1]) == "selfplay") {
        double secsPerMove = (argc >= 3) ? atof(argv[2]) : 2.0;
        int maxPlies = (argc >= 4) ? atoi(argv[3]) : 200;
        bool showBoard = (argc >= 5) && (string(argv[4]) == "s" || string(argv[4]) == "1");
        selfPlay((long long)(secsPerMove * 1000), maxPlies, showBoard);
        return 0;
    }

    if (argc >= 2 && string(argv[1]) == "perft") {
        int depth = (argc >= 3) ? atoi(argv[2]) : 4;
        Board b; setStartPos(b);
        for (int d = 1; d <= depth; d++) {
            auto t0 = steady_clock::now();
            long long n = perft(b, d);
            auto t1 = steady_clock::now();
            long long ms = duration_cast<milliseconds>(t1 - t0).count();
            cout << "perft(" << d << ") = " << n << "   (" << ms << " ms)\n";
        }
        return 0;
    }

    playLoop();
    return 0;
}
