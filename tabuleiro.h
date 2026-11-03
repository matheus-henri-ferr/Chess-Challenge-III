#pragma once

#include <array>
#include <cstdint>
#include <vector>

enum Piece : int8_t {
    EMPTY = 0,
    WP = 1, WN = 2, WB = 3, WR = 4, WQ = 5, WK = 6,
    BP = -1, BN = -2, BB = -3, BR = -4, BQ = -5, BK = -6
};

inline int pieceType(int8_t p) { return p < 0 ? -p : p; }
inline bool isWhite(int8_t p) { return p > 0; }
inline bool isBlack(int8_t p) { return p < 0; }

struct Move {
    int8_t from = -1, to = -1;
    int8_t promo = EMPTY;
    bool capture = false;
    bool ep = false;
    bool castle = false;
    bool doublePush = false;
    bool operator==(const Move &o) const {
        return from == o.from && to == o.to && promo == o.promo;
    }
};

struct Board {
    std::array<int8_t, 64> sq{};
    // -1 means unknown; manually assembled positions may leave this cache unset.
    int8_t kingSq[2] = {-1, -1}; // [0] white, [1] black
    bool whiteToMove = true;
    // bits: 1=WK, 2=WQ (lado das damas), 4=BK, 8=BQ
    uint8_t castleRights = 15;
    int8_t epSquare = -1;
    int halfmoveClock = 0;
    int fullmoveNumber = 1;
};

inline int fileOf(int s) { return s % 8; }
inline int rankOf(int s) { return s / 8; }
inline int sqOf(int f, int r) { return r * 8 + f; }
inline bool onBoard(int f, int r) { return f >= 0 && f < 8 && r >= 0 && r < 8; }

void setStartPos(Board &b);

bool isSquareAttacked(const Board &b, int s, bool byWhite);
int findKing(const Board &b, bool white);
bool inCheck(const Board &b, bool white);

void genPseudoMoves(const Board &b, std::vector<Move> &moves);
Board makeMove(const Board &b, const Move &m);
void genLegalMoves(const Board &b, std::vector<Move> &legal);

char pieceChar(int8_t p);
