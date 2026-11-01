#pragma once
#include "button_core.h"

typedef struct {
    button_core_t prev, next;
    bool chord;
} track_buttons_core_t;
void track_buttons_init(track_buttons_core_t *buttons, int64_t now_ms);
// Serialized by the player lock. Returns -1 / +1 once per stable press, else 0.
// Unavailable media/fault discards gestures; both buttons must release after a chord.
int track_buttons_sample(track_buttons_core_t *buttons, bool available,
                         bool prev_pressed, bool next_pressed, int64_t now_ms);
