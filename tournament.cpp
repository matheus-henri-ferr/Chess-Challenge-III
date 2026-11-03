#include "ui.h"
#include "xadrez.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace std;

// Our own decision component: conservative 15+10 clock allocation, recomputed
// from the physical clock at every turn. Works with Armageddon clocks too.
static long long allocateTime(long long remainingMs, long long incrementMs,
                              int fullmove, int legalCount, bool checked) {
    long long reserve = max(1500LL, remainingMs / 60);
    long long spendable = max(1LL, remainingMs - reserve);
    int movesToGo = max(16, 38 - fullmove / 2);
    double complexity = (checked ? 1.3 : 1.0) *
                        (legalCount >= 35 ? 1.2 : legalCount <= 10 ? 0.8 : 1.0);
    long long target = (long long)((spendable / (double)movesToGo +
                                    incrementMs * 0.7) * complexity);
    return max(1LL, min({target, spendable, max(1LL, remainingMs / 8)}));
}

static string pvText(const vector<Move> &pv) {
    string text;
    for (const Move &m : pv) {
        if (!text.empty()) text += ' ';
        text += moveToStr(m);
    }
    return text;
}

int tournamentLoop(bool engineWhite, const char *logPath) {
    ofstream log(logPath, ios::trunc);
    if (!log) { cerr << "Nao foi possivel criar o log: " << logPath << '\n'; return 1; }
    log << "# lance cor uci profundidade nos avaliacao_cp pv tempo_ms\n" << flush;
    Board b; setStartPos(b);
    vector<Board> positions{b};
    vector<string> entries;
    vector<uint64_t> hashes;

    cout << "Modo torneio: motor joga " << (engineWhite ? "BRANCAS" : "PRETAS")
         << ". Log: " << logPath << "\n"
         << "Relogio FISICO manda: informe o tempo restante na sua vez.\n"
         << "Comandos: tabuleiro, desfazer, sair. Confirme o lance antes de registra-lo.\n";

    auto rewriteLog = [&]() {
        log.close();
        log.open(logPath, ios::trunc);
        log << "# lance cor uci profundidade nos avaliacao_cp pv tempo_ms\n";
        for (const string &line : entries) log << line << '\n';
        log.flush();
    };

    auto command = [&](const string &s) {
        if (s == "tabuleiro") { printBoard(b); return true; }
        if (s == "desfazer") {
            if (positions.size() <= 1) cout << "Nenhum lance para desfazer.\n";
            else {
                positions.pop_back(); b = positions.back();
                hashes.pop_back(); entries.pop_back(); rewriteLog();
                cout << "Ultimo lance removido do estado e do log. Confira o tabuleiro fisico.\n";
            }
            return true;
        }
        return false;
    };

    while (true) {
        vector<Move> legal;
        genLegalMoves(b, legal);
        if (legal.empty()) {
            cout << (inCheck(b, b.whiteToMove) ? "Xeque-mate.\n" : "Afogamento.\n");
            break;
        }
        if (b.halfmoveClock >= 100 ||
            count(hashes.begin(), hashes.end(), computeHash(b)) >= 2) {
            cout << "Empate: 50 lances ou tripla repeticao. Confirme com o arbitro.\n";
            break;
        }

        bool ours = b.whiteToMove == engineWhite;
        if (ours) {
            long long remainingMs = 0, incrementMs = 10000;
            bool restartTurn = false;
            while (true) {
                cout << "Tempo RESTANTE no relogio (segundos; ex: 812.5), ou comando: " << flush;
                string input;
                if (!getline(cin, input) || input == "sair") return 0;
                if (command(input)) {
                    if (input == "desfazer") { restartTurn = true; break; }
                    continue;
                }
                istringstream stream(input);
                double seconds; char extra;
                if (stream >> seconds && !(stream >> extra) && isfinite(seconds) && seconds > 0 && seconds <= 3600) {
                    remainingMs = (long long)(seconds * 1000); break;
                }
                cout << "Tempo invalido. Use ponto decimal.\n";
            }
            if (restartTurn) continue;
            long long budget = allocateTime(remainingMs, incrementMs, b.fullmoveNumber,
                                            (int)legal.size(), inCheck(b, b.whiteToMove));
            cout << "Pensando por ate " << budget / 1000.0 << "s...\n";
            SearchResult result = search(b, budget, hashes);
            string uci = moveToStr(result.move);
            cout << ">>> ANUNCIE " << uci << " <<<  profundidade=" << result.depth
                 << " nos=" << result.nodes << " score=" << result.score
                 << " PV=" << pvText(result.pv) << '\n';
            cout << "Apos confirmacao verbal, movimento fisico e relogio, digite ok; "
                    "ou informe o lance real em UCI (ou sair): " << flush;
            string input;
            if (!getline(cin, input) || input == "sair") return 0;
            if (command(input)) continue;
            Move actual = result.move;
            bool suggested = (input == "ok");
            if (!suggested && !parseUserMove(b, input, actual)) {
                cout << "Nao registrado: comando/lance invalido. Insira o lance real agora.\n";
                while (true) {
                    cout << "Lance fisico UCI, ou sair: " << flush;
                    if (!getline(cin, input) || input == "sair") return 0;
                    if (parseUserMove(b, input, actual)) break;
                    cout << "Lance ilegal. Confira o tabuleiro.\n";
                }
            }
            int score = suggested ? result.score : evaluate(b);
            string pv = suggested ? pvText(result.pv) : moveToStr(actual);
            ostringstream line;
            line << b.fullmoveNumber << ' ' << (b.whiteToMove ? "brancas" : "pretas")
                 << ' ' << moveToStr(actual) << ' ' << (suggested ? result.depth : 0)
                 << ' ' << result.nodes << ' ' << score << " \"" << pv << "\" "
                 << result.elapsedMs;
            entries.push_back(line.str());
        } else {
            cout << "Lance adversario UCI (apos confirmacao no tabuleiro), ou comando: " << flush;
            string input;
            if (!getline(cin, input) || input == "sair") return 0;
            if (command(input)) continue;
            Move m;
            if (!parseUserMove(b, input, m)) { cout << "Lance ilegal. Nao registrado.\n"; continue; }
            ostringstream line;
            line << b.fullmoveNumber << ' ' << (b.whiteToMove ? "brancas" : "pretas")
                 << ' ' << moveToStr(m) << " 0 0 " << evaluate(b) << " \"" << moveToStr(m)
                 << "\" 0";
            entries.push_back(line.str());
            legal.clear(); legal.push_back(m);
        }

        Move m;
        // The logged UCI move is always resolved against the current legal position.
        istringstream line(entries.back());
        string number, color, uci;
        line >> number >> color >> uci;
        if (!parseUserMove(b, uci, m)) { cerr << "Erro interno: lance nao legal.\n"; return 1; }
        hashes.push_back(computeHash(b));
        b = makeMove(b, m);
        positions.push_back(b);
        log << entries.back() << '\n' << flush;
        printBoard(b);
    }
    return 0;
}
