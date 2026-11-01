#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stdatomic.h>

enum { EJECT_BUTTON_GPIO = 7, EJECT_DEBOUNCE_MS = 30 };
typedef struct {
    bool candidate_pressed, armed;
    int64_t changed_ms;
    atomic_uint mailbox;
} eject_button_core_t;
void eject_button_init(eject_button_core_t *button, int64_t now_ms);
// Input task only. Starts disarmed; a stable release is required before a press.
bool eject_button_sample(eject_button_core_t *button, bool pressed, int64_t now_ms);
// USB owner only. Disabling also discards pending requests (disconnect/busy/fault).
void eject_button_enable(eject_button_core_t *button, bool enabled);
bool eject_button_take(eject_button_core_t *button);
