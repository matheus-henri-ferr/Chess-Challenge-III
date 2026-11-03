#pragma once

#include "tabuleiro.h"

void printBoard(const Board &b);
void playLoop();
void selfPlay(long long timeMs, int maxPlies, bool showBoard);
int tournamentLoop(bool engineWhite, const char *logPath);
