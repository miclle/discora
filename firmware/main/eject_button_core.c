#include "eject_button_core.h"

enum { ENABLED = 1, PENDING = 2 };
void eject_button_init(eject_button_core_t *b, int64_t now_ms)
{
    b->candidate_pressed = true;
    b->armed = false;
    b->changed_ms = now_ms;
    atomic_init(&b->mailbox, 0);
}
bool eject_button_sample(eject_button_core_t *b, bool pressed, int64_t now_ms)
{
    if (pressed != b->candidate_pressed) {
        b->candidate_pressed = pressed;
        b->changed_ms = now_ms;
    }
    if (now_ms - b->changed_ms < EJECT_DEBOUNCE_MS) return false;
    if (!pressed) { b->armed = true; return false; }
    if (!b->armed) return false;
    b->armed = false;
    unsigned expected = ENABLED;
    return atomic_compare_exchange_strong(&b->mailbox, &expected, ENABLED | PENDING);
}
void eject_button_enable(eject_button_core_t *b, bool enabled)
{
    if (enabled) atomic_fetch_or(&b->mailbox, ENABLED);
    else atomic_store(&b->mailbox, 0);
}
bool eject_button_take(eject_button_core_t *b)
{
    return (atomic_fetch_and(&b->mailbox, ~PENDING) & PENDING) != 0;
}
