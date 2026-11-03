#include "xadrez.h"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstring>
#include <iostream>
#include <random>
#include <utility>
#include <vector>

using namespace std;
using namespace std::chrono;

static const int MATE_VALUE = 1000000;
static const int INF_SCORE  = 2000000;

// ---------------------------------------------------------------------------
// Zobrist hashing (para tabela de transposicao)
// ---------------------------------------------------------------------------

static uint64_t zobristPiece[13][64]; // indice piece+6 -> 0..12
static uint64_t zobristSide;
static uint64_t zobristCastle[16];
static uint64_t zobristEpFile[8];

void initZobrist() {
    mt19937_64 rng(0x1234567890ABCDEFULL);
    for (int p = 0; p < 13; p++)
        for (int s = 0; s < 64; s++)
            zobristPiece[p][s] = rng();
    zobristSide = rng();
    for (int i = 0; i < 16; i++) zobristCastle[i] = rng();
    for (int i = 0; i < 8; i++) zobristEpFile[i] = rng();
}

uint64_t computeHash(const Board &b) {
    uint64_t h = 0;
    for (int s = 0; s < 64; s++) {
        int8_t p = b.sq[s];
        if (p != EMPTY) h ^= zobristPiece[p + 6][s];
    }
    if (b.whiteToMove) h ^= zobristSide;
    h ^= zobristCastle[b.castleRights & 15];
    if (b.epSquare >= 0) h ^= zobristEpFile[fileOf(b.epSquare)];
    return h;
}

// ---------------------------------------------------------------------------
// Avaliacao
// ---------------------------------------------------------------------------

static const int pieceValue[7] = {0, 100, 320, 330, 500, 900, 20000};

// Piece-square tables (do ponto de vista das brancas; casa 0=a1 ... 63=h8)
static const int pstPawn[64] = {
  0,  0,  0,  0,  0,  0,  0,  0,
 50, 50, 50, 50, 50, 50, 50, 50,
 10, 10, 20, 30, 30, 20, 10, 10,
  5,  5, 10, 25, 25, 10,  5,  5,
  0,  0,  0, 55, 55,  0,  0,  0,
  5, -5,-10,  0,  0,-10, -5,  5,
  5, 10, 10,-20,-20, 10, 10,  5,
  0,  0,  0,  0,  0,  0,  0,  0
};
static const int pstKnight[64] = {
 -50,-40,-30,-30,-30,-30,-40,-50,
 -40,-20,  0,  0,  0,  0,-20,-40,
 -30,  0, 10, 15, 15, 10,  0,-30,
 -30,  5, 15, 20, 20, 15,  5,-30,
 -30,  0, 15, 20, 20, 15,  0,-30,
 -30,  5, 10, 15, 15, 10,  5,-30,
 -40,-20,  0,  5,  5,  0,-20,-40,
 -50, -0,-30,-30,-30, -0,-30,-50
};
static const int pstBishop[64] = {
 -20,-10,-10,-10,-10,-10,-10,-20,
 -10,  0,  0,  0,  0,  0,  0,-10,
 -10,  0,  5, 10, 10,  5,  0,-10,
 -10,  5,  5, 10, 10,  5,  5,-10,
 -10,  0, 10, 10, 10, 10,  0,-10,
 -10, 10, 10, 10, 10, 10, 10,-10,
 -10,  5,  0,  0,  0,  0,  5,-10,
 -20,-10,-10,-10,-10,-10,-10,-20
};
static const int pstRook[64] = {
  0,  0,  0,  0,  0,  0,  0,  0,
  5, 10, 10, 10, 10, 10, 10,  5,
 -5,  0,  0,  0,  0,  0,  0, -5,
 -5,  0,  0,  0,  0,  0,  0, -5,
 -5,  0,  0,  0,  0,  0,  0, -5,
 -5,  0,  0,  0,  0,  0,  0, -5,
 -5,  0,  0,  0,  0,  0,  0, -5,
  0,  0,  0,  5,  5,  0,  0,  0
};
static const int pstQueen[64] = {
 -20,-10,-10, -5, -5,-10,-10,-20,
 -10,  0,  0,  0,  0,  0,  0,-10,
 -10,  0,  5,  5,  5,  5,  0,-10,
  -5,  0,  5,  5,  5,  5,  0, -5,
   0,  0,  5,  5,  5,  5,  0, -5,
 -10,  5,  5,  5,  5,  5,  0,-10,
 -10,  0,  5,  0,  0,  0,  0,-10,
 -20,-10,-10, -5, -5,-10,-10,-20
};
static const int pstKing[64] = {
 -30,-40,-40,-50,-50,-40,-40,-30,
 -30,-40,-40,-50,-50,-40,-40,-30,
 -30,-40,-40,-50,-50,-40,-40,-30,
 -30,-40,-40,-50,-50,-40,-40,-30,
 -20,-30,-30,-40,-40,-30,-30,-20,
 -10,-20,-20,-20,-20,-20,-20,-10,
  20, 20,  0,  0,  0,  0, 20, 20,
  20, 30, 10,  0,  0, 10, 30, 20
};

static int mirror(int s) {
    int f = fileOf(s), r = rankOf(s);
    return sqOf(f, 7 - r);
}

static int pstValue(int pt, int s, bool white) {
    int idx = white ? s : mirror(s);
    switch (pt) {
        case 1: return pstPawn[idx];
        case 2: return pstKnight[idx];
        case 3: return pstBishop[idx];
        case 4: return pstRook[idx];
        case 5: return pstQueen[idx];
        case 6: return pstKing[idx];
    }
    return 0;
}

int evaluate(const Board &b) {
    int score = 0;
    for (int s = 0; s < 64; s++) {
        int8_t p = b.sq[s];
        if (p == EMPTY) continue;
        int pt = pieceType(p);
        int val = pieceValue[pt] + pstValue(pt, s, isWhite(p));
        score += isWhite(p) ? val : -val;
    }
    // retorna da perspectiva de quem tem o lance (convencao negamax)
    return b.whiteToMove ? score : -score;
}

// ---------------------------------------------------------------------------
// Tabela de transposicao
// ---------------------------------------------------------------------------

enum TTFlag { TT_EXACT, TT_LOWER, TT_UPPER };

struct TTEntry {
    uint64_t key = 0;
    int depth = -1;
    int score = 0;
    TTFlag flag = TT_EXACT;
    Move best;
    bool valid = false;
};

static const size_t TT_SIZE = 1 << 20; // ~1M entradas
static vector<TTEntry> tt(TT_SIZE);

static TTEntry* ttProbe(uint64_t key) {
    TTEntry &e = tt[key & (TT_SIZE - 1)];
    if (e.valid && e.key == key) return &e;
    return nullptr;
}

static void ttStore(uint64_t key, int depth, int score, TTFlag flag, const Move &best) {
    TTEntry &e = tt[key & (TT_SIZE - 1)];
    if (!e.valid || depth >= e.depth) {
        e.key = key; e.depth = depth; e.score = score; e.flag = flag; e.best = best; e.valid = true;
    }
}

// ---------------------------------------------------------------------------
// Busca: Negamax + Alpha-Beta + Quiescence + Iterative Deepening
// ---------------------------------------------------------------------------

struct TimeUp {};

static steady_clock::time_point searchStart;
static long long timeLimitMs;
static long long nodeCount = 0;
static vector<uint64_t> positionHistory;

static bool repeated(const Board &b, uint64_t key) {
    // No irreversible move can precede a repetition of this position.
    int start = max(0, (int)positionHistory.size() - b.halfmoveClock);
    for (int i = (int)positionHistory.size() - 1; i >= start; --i)
        if (positionHistory[i] == key) return true;
    return false;
}

static int scoreToTT(int score, int ply) {
    if (score > MATE_VALUE - 1000) return score + ply;
    if (score < -MATE_VALUE + 1000) return score - ply;
    return score;
}
static int scoreFromTT(int score, int ply) {
    if (score > MATE_VALUE - 1000) return score - ply;
    if (score < -MATE_VALUE + 1000) return score + ply;
    return score;
}

static inline void checkTime() {
    if ((nodeCount & 2047) == 0) {
        auto elapsed = duration_cast<milliseconds>(steady_clock::now() - searchStart).count();
        if (elapsed > timeLimitMs) throw TimeUp{};
    }
}

static Move killers[128][2];
static int history[64][64];

static int mvvLva(const Board &b, const Move &m) {
    if (!m.capture) return 0;
    int victim = m.ep ? 1 : pieceType(b.sq[m.to]);
    int attacker = pieceType(b.sq[m.from]);
    return pieceValue[victim] * 10 - pieceValue[attacker];
}

static void orderMoves(vector<Move> &moves, const Board &b, int ply, const Move *ttMove) {
    vector<pair<int, int>> scored(moves.size());
    for (size_t i = 0; i < moves.size(); i++) {
        int s = 0;
        if (ttMove && moves[i] == *ttMove) s = 1000000;
        else if (moves[i].capture) s = 100000 + mvvLva(b, moves[i]);
        else if (moves[i] == killers[ply][0]) s = 90000;
        else if (moves[i] == killers[ply][1]) s = 89000;
        else s = history[moves[i].from][moves[i].to];
        scored[i] = {s, (int)i};
    }
    sort(scored.begin(), scored.end(), [](auto &a, auto &b) { return a.first > b.first; });
    vector<Move> ordered(moves.size());
    for (size_t i = 0; i < moves.size(); i++) ordered[i] = moves[scored[i].second];
    moves = ordered;
}

static int quiescence(const Board &b, int alpha, int beta, int ply) {
    nodeCount++; checkTime();
    if (b.halfmoveClock >= 100 || repeated(b, computeHash(b))) return 0;
    bool checked = inCheck(b, b.whiteToMove);
    if (ply >= 96) return evaluate(b);

    vector<Move> moves;
    genLegalMoves(b, moves);
    if (moves.empty()) return checked ? -(MATE_VALUE - ply) : 0;
    if (!checked) {
        int standPat = evaluate(b);
        if (standPat >= beta) return standPat;
        if (alpha < standPat) alpha = standPat;
    }
    vector<Move> caps;
    for (auto &m : moves) if (checked || m.capture || m.promo != EMPTY) caps.push_back(m);
    orderMoves(caps, b, min(ply, 127), nullptr);

    for (auto &m : caps) {
        Board nb = makeMove(b, m);
        positionHistory.push_back(computeHash(b));
        int score = -quiescence(nb, -beta, -alpha, ply + 1);
        positionHistory.pop_back();
        if (score >= beta) return score;
        if (score > alpha) alpha = score;
    }
    return alpha;
}

static int negamax(Board &b, int depth, int alpha, int beta, int ply, Move &outBest) {
    nodeCount++; checkTime();

    uint64_t key = computeHash(b);
    if (b.halfmoveClock >= 100 || repeated(b, key)) return 0;
    if (ply >= 96) return evaluate(b);
    if (depth <= 0) return quiescence(b, alpha, beta, ply);
    Move ttMoveStorage; const Move* ttMovePtr = nullptr;
    int origAlpha = alpha;

    TTEntry* e = ttProbe(key);
    if (e && e->depth >= depth && ply > 0) {
        int ttScore = scoreFromTT(e->score, ply);
        if (e->flag == TT_EXACT) return ttScore;
        if (e->flag == TT_LOWER && ttScore > alpha) alpha = ttScore;
        if (e->flag == TT_UPPER && ttScore < beta) beta = ttScore;
        if (alpha >= beta) return ttScore;
    }
    if (e && e->valid) { ttMoveStorage = e->best; ttMovePtr = &ttMoveStorage; }

    vector<Move> moves;
    genLegalMoves(b, moves);

    if (moves.empty()) {
        if (inCheck(b, b.whiteToMove)) return -(MATE_VALUE - ply); // xeque-mate
        return 0; // afogamento
    }

    orderMoves(moves, b, min(ply, 127), ttMovePtr);

    int best = -INF_SCORE;
    Move bestMove = moves[0];

    for (auto &m : moves) {
        Board nb = makeMove(b, m);
        Move dummy;
        positionHistory.push_back(key);
        int score = -negamax(nb, depth - 1, -beta, -alpha, ply + 1, dummy);
        positionHistory.pop_back();

        if (score > best) { best = score; bestMove = m; }
        if (best > alpha) alpha = best;
        if (alpha >= beta) {
            if (!m.capture) {
                killers[min(ply, 127)][1] = killers[min(ply, 127)][0];
                killers[min(ply, 127)][0] = m;
                history[m.from][m.to] += depth * depth;
            }
            break;
        }
    }

    TTFlag flag = (best <= origAlpha) ? TT_UPPER : (best >= beta) ? TT_LOWER : TT_EXACT;
    ttStore(key, depth, scoreToTT(best, ply), flag, bestMove);

    outBest = bestMove;
    return best;
}

// Busca com aprofundamento iterativo, respeitando um limite de tempo (ms)
SearchResult search(Board &b, long long timeMs, const vector<uint64_t> &previous, int maxDepth) {
    searchStart = steady_clock::now();
    timeLimitMs = max(1LL, timeMs);
    nodeCount = 0;
    positionHistory = previous;
    memset(killers, 0, sizeof(killers));
    memset(history, 0, sizeof(history));

    vector<Move> rootMoves;
    genLegalMoves(b, rootMoves);
    SearchResult result;
    if (rootMoves.empty()) return result;
    result.move = rootMoves[0];
    result.pv.push_back(result.move);
    if (rootMoves.size() == 1) {
        result.depth = 1;
        result.score = -evaluate(makeMove(b, result.move));
        result.elapsedMs = duration_cast<milliseconds>(steady_clock::now() - searchStart).count();
        return result;
    }

    Move bestMove = rootMoves[0];
    int bestScore = -INF_SCORE;

    try {
        for (int depth = 1; depth <= maxDepth; depth++) {
            Move ttMoveStorage = bestMove; const Move* ttMovePtr = &ttMoveStorage;
            orderMoves(rootMoves, b, 0, ttMovePtr);

            int alpha = -INF_SCORE, beta = INF_SCORE;
            Move iterBest = rootMoves[0];
            int iterBestScore = -INF_SCORE;

            for (auto &m : rootMoves) {
                Board nb = makeMove(b, m);
                Move dummy;
                positionHistory.push_back(computeHash(b));
                int score = -negamax(nb, depth - 1, -beta, -alpha, 1, dummy);
                positionHistory.pop_back();
                if (score > iterBestScore) { iterBestScore = score; iterBest = m; }
                if (score > alpha) alpha = score;
            }
            bestMove = iterBest;
            bestScore = iterBestScore;
            result.move = bestMove;
            result.score = bestScore;
            result.depth = depth;
            ttStore(computeHash(b), depth, scoreToTT(bestScore, 0), TT_EXACT, bestMove);

            result.pv.clear();
            Board line = b;
            for (int i = 0; i < depth; ++i) {
                TTEntry *entry = ttProbe(computeHash(line));
                if (!entry) break;
                vector<Move> legal;
                genLegalMoves(line, legal);
                auto it = find(legal.begin(), legal.end(), entry->best);
                if (it == legal.end()) break;
                result.pv.push_back(*it);
                line = makeMove(line, *it);
            }
            if (result.pv.empty()) result.pv.push_back(bestMove);

            auto elapsed = duration_cast<milliseconds>(steady_clock::now() - searchStart).count();
            cerr << "[info] profundidade=" << depth << " score=" << bestScore
                 << " nos=" << nodeCount << " tempo=" << elapsed << "ms\n";
            if (abs(bestScore) > MATE_VALUE - 1000) break; // mate encontrado
            if (elapsed > timeLimitMs / 2) break; // sem tempo para outra iteracao completa
        }
    } catch (TimeUp&) {
        // usa o melhor resultado da ultima iteracao completa
    }
    positionHistory = previous;
    result.nodes = nodeCount;
    result.elapsedMs = duration_cast<milliseconds>(steady_clock::now() - searchStart).count();
    return result;
}

Move searchBestMove(Board &b, long long timeMs, int maxDepth) {
    return search(b, timeMs, {}, maxDepth).move;
}

// ---------------------------------------------------------------------------
// Notacao coordenada (ex: e2e4, e7e8q) <-> Move
// ---------------------------------------------------------------------------

string squareName(int s) {
    string r;
    r += char('a' + fileOf(s));
    r += char('1' + rankOf(s));
    return r;
}

int parseSquare(const string &s) {
    if (s.size() < 2) return -1;
    int f = s[0] - 'a', r = s[1] - '1';
    if (!onBoard(f, r)) return -1;
    return sqOf(f, r);
}

string moveToStr(const Move &m) {
    string s = squareName(m.from) + squareName(m.to);
    if (m.promo != EMPTY) {
        int pt = pieceType(m.promo);
        char c = (pt == 5 ? 'q' : pt == 4 ? 'r' : pt == 3 ? 'b' : pt == 2 ? 'n' : '?');
        s += c;
    }
    return s;
}

// Converte texto do usuario em um Move legal (ou retorna false se invalido)
bool parseUserMove(const Board &b, const string &text, Move &out) {
    if (text.size() != 4 && text.size() != 5) return false;
    int from = parseSquare(text.substr(0, 2));
    int to   = parseSquare(text.substr(2, 2));
    if (from < 0 || to < 0) return false;
    char promoChar = (text.size() >= 5) ? tolower(text[4]) : 0;

    vector<Move> legal;
    genLegalMoves(b, legal);
    for (auto &m : legal) {
        if (m.from == from && m.to == to) {
            if (m.promo == EMPTY && text.size() == 4) { out = m; return true; }
            int pt = pieceType(m.promo);
            char c = (pt == 5 ? 'q' : pt == 4 ? 'r' : pt == 3 ? 'b' : pt == 2 ? 'n' : '?');
            if (c == promoChar) { out = m; return true; }
        }
    }
    return false;
}

// ---------------------------------------------------------------------------
// Perft (teste de corretude do gerador de lances)
// ---------------------------------------------------------------------------

long long perft(Board &b, int depth) {
    if (depth == 0) return 1;
    vector<Move> moves;
    genLegalMoves(b, moves);
    if (depth == 1) return moves.size();
    long long total = 0;
    for (auto &m : moves) {
        Board nb = makeMove(b, m);
        total += perft(nb, depth - 1);
    }
    return total;
}
