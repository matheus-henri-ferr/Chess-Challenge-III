#pragma once

#include "tabuleiro.h"

#include <cstdint>
#include <string>
#include <vector>

void initZobrist();
uint64_t computeHash(const Board &b);

int evaluate(const Board &b);

struct SearchResult {
    Move move;
    int depth = 0;
    long long nodes = 0;
    int score = 0; // centipawns from the side to move; mate scores near +/-1000000
    long long elapsedMs = 0;
    std::vector<Move> pv;
};

SearchResult search(Board &b, long long timeMs, const std::vector<uint64_t> &previous = {}, int maxDepth = 64);
Move searchBestMove(Board &b, long long timeMs, int maxDepth = 64);
long long perft(Board &b, int depth);

std::string squareName(int s);
int parseSquare(const std::string &s);
std::string moveToStr(const Move &m);
bool parseUserMove(const Board &b, const std::string &text, Move &out);
