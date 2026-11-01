#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stdatomic.h>

enum { BUTTON_DEBOUNCE_MS = 30 };
typedef struct {
    bool candidate_pressed, armed;
    int64_t changed_ms;
    atomic_uint mailbox;
} button_core_t;
void button_init(button_core_t *button, int64_t now_ms);
// Input task only. Starts disarmed; a stable release is required before a press.
bool button_sample(button_core_t *button, bool pressed, int64_t now_ms);
// Consumer only. Disabling also discards pending requests (disconnect/busy/fault).
void button_enable(button_core_t *button, bool enabled);
bool button_take(button_core_t *button);
