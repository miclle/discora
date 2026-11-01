#include "track_buttons_core.h"

void track_buttons_init(track_buttons_core_t *b, int64_t now_ms)
{
    button_init(&b->prev, now_ms);
    button_init(&b->next, now_ms);
    b->chord = false;
}
int track_buttons_sample(track_buttons_core_t *b, bool available,
                         bool prev_pressed, bool next_pressed, int64_t now_ms)
{
    if (!available) { track_buttons_init(b, now_ms); return 0; }
    if (prev_pressed && next_pressed) b->chord = true;
    button_enable(&b->prev, !b->chord);
    button_enable(&b->next, !b->chord);
    button_sample(&b->prev, prev_pressed, now_ms);
    button_sample(&b->next, next_pressed, now_ms);
    bool prev = button_take(&b->prev), next = button_take(&b->next);
    if (b->chord) {
        if (!prev_pressed && !next_pressed &&
            now_ms - b->prev.changed_ms >= BUTTON_DEBOUNCE_MS &&
            now_ms - b->next.changed_ms >= BUTTON_DEBOUNCE_MS) b->chord = false;
        return 0;
    }
    return prev ? -1 : next ? 1 : 0;
}
