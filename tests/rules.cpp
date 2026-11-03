#include "../xadrez.h"

#include <cassert>
#include <vector>

int main() {
    initZobrist();
    Board b{};
    b.castleRights = 0;
    b.sq[4] = WK;
    b.sq[63] = BK;
    b.sq[52] = WP;
    Move m;
    assert(parseUserMove(b, "e7e8q", m));
    assert(m.promo == WQ);
    assert(!parseUserMove(b, "e7e8", m));
    assert(!parseUserMove(b, "e7e8qgarbage", m));

    // A rook attacks e1 through a pinned e5 pawn: en passant would expose the king.
    b = Board{};
    b.castleRights = 0;
    b.sq[4] = WK;
    b.sq[56] = BK;
    b.sq[60] = BR;
    b.sq[36] = WP; // e5
    b.sq[35] = BP; // d5
    b.epSquare = 43; // d6
    assert(!parseUserMove(b, "e5d6", m));

    // Even a corrupt castling-rights field must not generate castling from d1.
    b = Board{};
    b.castleRights = 1;
    b.sq[3] = WK;
    b.sq[7] = WR;
    b.sq[60] = BK;
    assert(!parseUserMove(b, "d1g1", m));

    // Capturing a king is never a legal move.
    b = Board{};
    b.castleRights = 0;
    b.sq[0] = WK;
    b.sq[52] = WQ;
    b.sq[60] = BK;
    assert(!parseUserMove(b, "e7e8", m));

    // Cached king squares follow ordinary moves and castling.
    setStartPos(b);
    assert(findKing(b, true) == 4 && findKing(b, false) == 60);
    assert(parseUserMove(b, "e2e4", m)); b = makeMove(b, m);
    assert(parseUserMove(b, "e7e5", m)); b = makeMove(b, m);
    assert(parseUserMove(b, "g1f3", m)); b = makeMove(b, m);
    assert(parseUserMove(b, "b8c6", m)); b = makeMove(b, m);
    assert(parseUserMove(b, "f1c4", m)); b = makeMove(b, m);
    assert(parseUserMove(b, "g8f6", m)); b = makeMove(b, m);
    assert(parseUserMove(b, "e1g1", m)); b = makeMove(b, m);
    assert(b.kingSq[0] == 6 && findKing(b, true) == 6);
    assert(findKing(b, false) == 60);

    // Manually assembled boards without a cache still work.
    b = Board{};
    b.sq[12] = WK;
    b.sq[59] = BK;
    assert(findKing(b, true) == 12 && findKing(b, false) == 59);
}
