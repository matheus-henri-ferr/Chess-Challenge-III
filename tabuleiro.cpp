#include "tabuleiro.h"

using namespace std;

// ---------------------------------------------------------------------------
// Posicao inicial
// ---------------------------------------------------------------------------

void setStartPos(Board &b) {
    static const int8_t backRank[8] = {WR, WN, WB, WQ, WK, WB, WN, WR};
    for (int f = 0; f < 8; f++) {
        b.sq[sqOf(f, 0)] = backRank[f];
        b.sq[sqOf(f, 1)] = WP;
        b.sq[sqOf(f, 6)] = BP;
        b.sq[sqOf(f, 7)] = (int8_t)(-backRank[f]);
        for (int r = 2; r < 6; r++) b.sq[sqOf(f, r)] = EMPTY;
    }
    b.whiteToMove = true;
    b.castleRights = 15;
    b.epSquare = -1;
    b.halfmoveClock = 0;
    b.fullmoveNumber = 1;
    b.kingSq[0] = 4;
    b.kingSq[1] = 60;
}

// ---------------------------------------------------------------------------
// Deteccao de casa atacada
// ---------------------------------------------------------------------------

static const int knightOff[8][2] = {{1, 2}, {2, 1}, {2, -1}, {1, -2}, {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}};
static const int kingOff[8][2]   = {{1, 0}, {1, 1}, {0, 1}, {-1, 1}, {-1, 0}, {-1, -1}, {0, -1}, {1, -1}};
static const int bishopDir[4][2] = {{1, 1}, {1, -1}, {-1, 1}, {-1, -1}};
static const int rookDir[4][2]   = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};

bool isSquareAttacked(const Board &b, int s, bool byWhite) {
    int f = fileOf(s), r = rankOf(s);

    // Peoes
    int pawnDir = byWhite ? -1 : 1;
    for (int df : {-1, 1}) {
        int nf = f + df, nr = r + pawnDir;
        if (onBoard(nf, nr)) {
            int8_t p = b.sq[sqOf(nf, nr)];
            if (byWhite && p == WP) return true;
            if (!byWhite && p == BP) return true;
        }
    }
    // Cavalos
    for (auto &o : knightOff) {
        int nf = f + o[0], nr = r + o[1];
        if (onBoard(nf, nr)) {
            int8_t p = b.sq[sqOf(nf, nr)];
            if (byWhite && p == WN) return true;
            if (!byWhite && p == BN) return true;
        }
    }
    // Rei
    for (auto &o : kingOff) {
        int nf = f + o[0], nr = r + o[1];
        if (onBoard(nf, nr)) {
            int8_t p = b.sq[sqOf(nf, nr)];
            if (byWhite && p == WK) return true;
            if (!byWhite && p == BK) return true;
        }
    }
    // Bispo / Dama (diagonais)
    for (auto &d : bishopDir) {
        int nf = f + d[0], nr = r + d[1];
        while (onBoard(nf, nr)) {
            int8_t p = b.sq[sqOf(nf, nr)];
            if (p != EMPTY) {
                if (byWhite && (p == WB || p == WQ)) return true;
                if (!byWhite && (p == BB || p == BQ)) return true;
                break;
            }
            nf += d[0]; nr += d[1];
        }
    }
    // Torre / Dama (retas)
    for (auto &d : rookDir) {
        int nf = f + d[0], nr = r + d[1];
        while (onBoard(nf, nr)) {
            int8_t p = b.sq[sqOf(nf, nr)];
            if (p != EMPTY) {
                if (byWhite && (p == WR || p == WQ)) return true;
                if (!byWhite && (p == BR || p == BQ)) return true;
                break;
            }
            nf += d[0]; nr += d[1];
        }
    }
    return false;
}

int findKing(const Board &b, bool white) {
    int8_t target = white ? WK : BK;
    int cached = b.kingSq[white ? 0 : 1];
    if (cached >= 0 && cached < 64 && b.sq[cached] == target) return cached;
    for (int s = 0; s < 64; s++) if (b.sq[s] == target) return s;
    return -1;
}

bool inCheck(const Board &b, bool white) {
    int k = findKing(b, white);
    if (k < 0) return false;
    return isSquareAttacked(b, k, !white);
}

// ---------------------------------------------------------------------------
// Geracao de lances pseudo-legais
// ---------------------------------------------------------------------------

static void addPromotions(vector<Move> &moves, int from, int to, bool capture, bool white) {
    for (int pt : {WQ, WR, WB, WN}) {
        Move m; m.from = from; m.to = to; m.capture = capture;
        m.promo = white ? (int8_t)pt : (int8_t)(-pt);
        moves.push_back(m);
    }
}

void genPseudoMoves(const Board &b, vector<Move> &moves) {
    moves.clear();
    bool white = b.whiteToMove;
    for (int s = 0; s < 64; s++) {
        int8_t p = b.sq[s];
        if (p == EMPTY) continue;
        if (white != isWhite(p)) continue;
        int f = fileOf(s), r = rankOf(s);
        int pt = pieceType(p);

        if (pt == 1) { // peao
            int dir = white ? 1 : -1;
            int startRank = white ? 1 : 6;
            int promoRank = white ? 7 : 0;
            int nr = r + dir;
            // avanco simples
            if (onBoard(f, nr) && b.sq[sqOf(f, nr)] == EMPTY) {
                if (nr == promoRank) addPromotions(moves, s, sqOf(f, nr), false, white);
                else {
                    Move m; m.from = s; m.to = sqOf(f, nr); moves.push_back(m);
                    // avanco duplo
                    if (r == startRank) {
                        int nr2 = r + 2 * dir;
                        if (b.sq[sqOf(f, nr2)] == EMPTY) {
                            Move m2; m2.from = s; m2.to = sqOf(f, nr2); m2.doublePush = true;
                            moves.push_back(m2);
                        }
                    }
                }
            }
            // capturas
            for (int df : {-1, 1}) {
                int nf = f + df;
                if (!onBoard(nf, nr)) continue;
                int to = sqOf(nf, nr);
                int8_t target = b.sq[to];
                if (target != EMPTY && pieceType(target) != 6 && isWhite(target) != white) {
                    if (nr == promoRank) addPromotions(moves, s, to, true, white);
                    else { Move m; m.from = s; m.to = to; m.capture = true; moves.push_back(m); }
                } else if (to == b.epSquare) {
                    Move m; m.from = s; m.to = to; m.capture = true; m.ep = true; moves.push_back(m);
                }
            }
        }
        else if (pt == 2) { // cavalo
            for (auto &o : knightOff) {
                int nf = f + o[0], nr = r + o[1];
                if (!onBoard(nf, nr)) continue;
                int to = sqOf(nf, nr);
                int8_t target = b.sq[to];
                if (target == EMPTY) { Move m; m.from = s; m.to = to; moves.push_back(m); }
                else if (pieceType(target) != 6 && isWhite(target) != white) { Move m; m.from = s; m.to = to; m.capture = true; moves.push_back(m); }
            }
        }
        else if (pt == 6) { // rei
            for (auto &o : kingOff) {
                int nf = f + o[0], nr = r + o[1];
                if (!onBoard(nf, nr)) continue;
                int to = sqOf(nf, nr);
                int8_t target = b.sq[to];
                if (target == EMPTY) { Move m; m.from = s; m.to = to; moves.push_back(m); }
                else if (pieceType(target) != 6 && isWhite(target) != white) { Move m; m.from = s; m.to = to; m.capture = true; moves.push_back(m); }
            }
            // Roque
            bool inChk = isSquareAttacked(b, s, !white);
            if (!inChk && s == (white ? 4 : 60)) {
                if (white) {
                    if ((b.castleRights & 1) && b.sq[5] == EMPTY && b.sq[6] == EMPTY &&
                        !isSquareAttacked(b, 5, false) && !isSquareAttacked(b, 6, false) && b.sq[7] == WR) {
                        Move m; m.from = s; m.to = 6; m.castle = true; moves.push_back(m);
                    }
                    if ((b.castleRights & 2) && b.sq[1] == EMPTY && b.sq[2] == EMPTY && b.sq[3] == EMPTY &&
                        !isSquareAttacked(b, 3, false) && !isSquareAttacked(b, 2, false) && b.sq[0] == WR) {
                        Move m; m.from = s; m.to = 2; m.castle = true; moves.push_back(m);
                    }
                } else {
                    if ((b.castleRights & 4) && b.sq[61] == EMPTY && b.sq[62] == EMPTY &&
                        !isSquareAttacked(b, 61, true) && !isSquareAttacked(b, 62, true) && b.sq[63] == BR) {
                        Move m; m.from = s; m.to = 62; m.castle = true; moves.push_back(m);
                    }
                    if ((b.castleRights & 8) && b.sq[57] == EMPTY && b.sq[58] == EMPTY && b.sq[59] == EMPTY &&
                        !isSquareAttacked(b, 59, true) && !isSquareAttacked(b, 58, true) && b.sq[56] == BR) {
                        Move m; m.from = s; m.to = 58; m.castle = true; moves.push_back(m);
                    }
                }
            }
        }
        else { // deslizantes: bispo(3), torre(4), dama(5)
            const int (*dirs)[2]; int ndirs;
            if (pt == 3) { dirs = bishopDir; ndirs = 4; }
            else if (pt == 4) { dirs = rookDir; ndirs = 4; }
            else { // dama: combina os dois
                for (auto &d : bishopDir) {
                    int nf = f + d[0], nr = r + d[1];
                    while (onBoard(nf, nr)) {
                        int to = sqOf(nf, nr); int8_t target = b.sq[to];
                        if (target == EMPTY) { Move m; m.from = s; m.to = to; moves.push_back(m); }
                        else { if (pieceType(target) != 6 && isWhite(target) != white) { Move m; m.from = s; m.to = to; m.capture = true; moves.push_back(m); } break; }
                        nf += d[0]; nr += d[1];
                    }
                }
                for (auto &d : rookDir) {
                    int nf = f + d[0], nr = r + d[1];
                    while (onBoard(nf, nr)) {
                        int to = sqOf(nf, nr); int8_t target = b.sq[to];
                        if (target == EMPTY) { Move m; m.from = s; m.to = to; moves.push_back(m); }
                        else { if (pieceType(target) != 6 && isWhite(target) != white) { Move m; m.from = s; m.to = to; m.capture = true; moves.push_back(m); } break; }
                        nf += d[0]; nr += d[1];
                    }
                }
                continue;
            }
            for (int i = 0; i < ndirs; i++) {
                int nf = f + dirs[i][0], nr = r + dirs[i][1];
                while (onBoard(nf, nr)) {
                    int to = sqOf(nf, nr); int8_t target = b.sq[to];
                    if (target == EMPTY) { Move m; m.from = s; m.to = to; moves.push_back(m); }
                    else { if (pieceType(target) != 6 && isWhite(target) != white) { Move m; m.from = s; m.to = to; m.capture = true; moves.push_back(m); } break; }
                    nf += dirs[i][0]; nr += dirs[i][1];
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Aplicar lance (retorna novo tabuleiro por copia)
// ---------------------------------------------------------------------------

Board makeMove(const Board &b, const Move &m) {
    Board nb = b;
    bool white = b.whiteToMove;
    int8_t moving = nb.sq[m.from];

    nb.epSquare = -1;
    nb.halfmoveClock++;

    if (pieceType(moving) == 1 || m.capture) nb.halfmoveClock = 0;

    if (m.ep) {
        int capSq = white ? m.to - 8 : m.to + 8;
        nb.sq[capSq] = EMPTY;
    }

    nb.sq[m.to] = (m.promo != EMPTY) ? m.promo : moving;
    nb.sq[m.from] = EMPTY;
    if (pieceType(moving) == 6) nb.kingSq[white ? 0 : 1] = m.to;

    if (m.castle) {
        if (m.to == 6)  { nb.sq[5] = nb.sq[7];   nb.sq[7] = EMPTY; }   // O-O branco
        if (m.to == 2)  { nb.sq[3] = nb.sq[0];   nb.sq[0] = EMPTY; }   // O-O-O branco
        if (m.to == 62) { nb.sq[61] = nb.sq[63]; nb.sq[63] = EMPTY; }  // O-O preto
        if (m.to == 58) { nb.sq[59] = nb.sq[56]; nb.sq[56] = EMPTY; }  // O-O-O preto
    }

    if (m.doublePush) {
        nb.epSquare = white ? m.from + 8 : m.from - 8;
    }

    // Atualiza direitos de roque
    auto clearRight = [&](int sq) {
        if (sq == 4) nb.castleRights &= ~(1 | 2);
        if (sq == 0) nb.castleRights &= ~2;
        if (sq == 7) nb.castleRights &= ~1;
        if (sq == 60) nb.castleRights &= ~(4 | 8);
        if (sq == 56) nb.castleRights &= ~8;
        if (sq == 63) nb.castleRights &= ~4;
    };
    clearRight(m.from);
    clearRight(m.to);

    nb.whiteToMove = !white;
    if (white == false) nb.fullmoveNumber++;
    return nb;
}

// Gera apenas lances LEGAIS (filtra os que deixam o proprio rei em xeque)
void genLegalMoves(const Board &b, vector<Move> &legal) {
    vector<Move> pseudo;
    genPseudoMoves(b, pseudo);
    legal.clear();
    for (auto &m : pseudo) {
        Board nb = makeMove(b, m);
        if (!inCheck(nb, b.whiteToMove)) legal.push_back(m);
    }
}

// ---------------------------------------------------------------------------
// Representacao textual das pecas
// ---------------------------------------------------------------------------

char pieceChar(int8_t p) {
    switch (p) {
        case WP: return 'P'; case WN: return 'N'; case WB: return 'B';
        case WR: return 'R'; case WQ: return 'Q'; case WK: return 'K';
        case BP: return 'p'; case BN: return 'n'; case BB: return 'b';
        case BR: return 'r'; case BQ: return 'q'; case BK: return 'k';
        default: return '.';
    }
}
