#include "ui.h"

#include "xadrez.h"

#include <iostream>
#include <string>
#include <vector>

using namespace std;

// ---------------------------------------------------------------------------
// Impressao do tabuleiro
// ---------------------------------------------------------------------------

void printBoard(const Board &b) {
    cout << "\n";
    for (int r = 7; r >= 0; r--) {
        cout << (r + 1) << " ";
        for (int f = 0; f < 8; f++) cout << pieceChar(b.sq[sqOf(f, r)]) << " ";
        cout << "\n";
    }
    cout << "  a b c d e f g h\n";
    cout << (b.whiteToMove ? "Brancas jogam" : "Pretas jogam") << "\n\n";
}

// ---------------------------------------------------------------------------
// Partida interativa
// ---------------------------------------------------------------------------

void playLoop() {
    Board b; setStartPos(b);
    cout << "=== Chess Challenge III - Motor ===\n";
    cout << "Voce quer jogar de branca ou preta? (b/p): ";
    string colorInput; cin >> colorInput;
    bool userIsWhite = (colorInput == "b" || colorInput == "B");

    cout << "Tempo de pensamento do motor por lance, em segundos (ex: 5): ";
    double secs = 5.0; cin >> secs;
    long long timeMs = (long long)(secs * 1000);

    cout << "\nDigite lances em notacao coordenada (ex: e2e4, ou e7e8q para promocao).\n";
    cout << "Digite 'sair' para encerrar.\n";

    while (true) {
        printBoard(b);
        vector<Move> legal;
        genLegalMoves(b, legal);
        if (legal.empty()) {
            if (inCheck(b, b.whiteToMove)) cout << (b.whiteToMove ? "Pretas" : "Brancas") << " vencem por xeque-mate!\n";
            else cout << "Empate por afogamento.\n";
            break;
        }
        if (b.halfmoveClock >= 100) { cout << "Empate pela regra dos 50 lances.\n"; break; }

        bool engineTurn = (b.whiteToMove != userIsWhite);
        if (engineTurn) {
            cout << "Motor pensando...\n";
            Move best = searchBestMove(b, timeMs);
            cout << ">>> Lance do motor: " << moveToStr(best) << "  <-- mova a peca no tabuleiro fisico\n";
            b = makeMove(b, best);
        } else {
            cout << "Seu lance: ";
            string in; cin >> in;
            if (in == "sair") break;
            Move m;
            if (!parseUserMove(b, in, m)) {
                cout << "Lance invalido, tente novamente.\n";
                continue;
            }
            b = makeMove(b, m);
        }
    }
}

// ---------------------------------------------------------------------------
// Selfplay: motor contra ele mesmo (util para teste/tuning)
// ---------------------------------------------------------------------------

void selfPlay(long long timeMs, int maxPlies, bool showBoard) {
    Board b; setStartPos(b);
    vector<uint64_t> hashHistory;
    vector<string> moveList;

    cout << "=== Selfplay: motor (brancas) x motor (pretas) ===\n";
    cout << "Tempo por lance: " << (timeMs / 1000.0) << "s | Limite de lances: " << maxPlies << "\n\n";

    string result = "*";
    string reason = "";

    for (int ply = 0; ply < maxPlies; ply++) {
        vector<Move> legal;
        genLegalMoves(b, legal);

        if (legal.empty()) {
            if (inCheck(b, b.whiteToMove)) {
                result = b.whiteToMove ? "0-1" : "1-0";
                reason = "xeque-mate";
            } else {
                result = "1/2-1/2";
                reason = "afogamento";
            }
            break;
        }
        if (b.halfmoveClock >= 100) {
            result = "1/2-1/2"; reason = "regra dos 50 lances"; break;
        }
        uint64_t h = computeHash(b);
        int reps = 0;
        for (auto hh : hashHistory) if (hh == h) reps++;
        if (reps >= 2) { // 3a ocorrencia desta posicao
            result = "1/2-1/2"; reason = "tripla repeticao"; break;
        }
        hashHistory.push_back(h);

        Move best = searchBestMove(b, timeMs);
        string mstr = moveToStr(best);
        moveList.push_back(mstr);

        int moveNum = (ply / 2) + 1;
        if (ply % 2 == 0) cout << moveNum << ". " << mstr << " " << flush;
        else cout << mstr << "\n" << flush;

        b = makeMove(b, best);
        if (showBoard) printBoard(b);
    }

    if (result == "*") { result = "1/2-1/2"; reason = "limite de lances atingido"; }

    cout << "\n\nResultado: " << result << "  (" << reason << ")\n";
    cout << "Total de lances (meios-lances): " << moveList.size() << "\n";
    cout << "\nPartida completa (notacao coordenada):\n";
    for (size_t i = 0; i < moveList.size(); i++) {
        if (i % 2 == 0) cout << (i / 2 + 1) << ". ";
        cout << moveList[i] << " ";
        if (i % 2 == 1) cout << "\n";
    }
    cout << "\n";
}
