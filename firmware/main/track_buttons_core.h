#pragma once
#include "button_core.h"

typedef struct {
    button_core_t prev, next, play;
    bool chord;
} track_buttons_core_t;
void track_buttons_init(track_buttons_core_t *buttons, int64_t now_ms);
enum { PLAYER_BUTTON_NONE = 0, PLAYER_BUTTON_PREV = -1, PLAYER_BUTTON_NEXT = 1, PLAYER_BUTTON_TOGGLE = 2 };
// Serialized by the player lock. One action per stable press.
// Unavailable media/fault discards gestures; all three buttons release after a chord.
int track_buttons_sample(track_buttons_core_t *buttons, bool available,
                         bool prev_pressed, bool next_pressed, bool play_pressed, int64_t now_ms);
