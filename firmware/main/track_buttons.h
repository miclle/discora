#pragma once
#include "sdkconfig.h"
#include <stdbool.h>

#if defined(CONFIG_DISCORA_TRACK_BUTTONS) || defined(CONFIG_DISCORA_PLAY_PAUSE_BUTTON)
bool discora_track_buttons_start(void);
// Player mutex must protect reset and poll; only the output owner polls GPIO.
void discora_track_buttons_reset(void);
int discora_track_buttons_poll(bool available);
#else
static inline bool discora_track_buttons_start(void) { return true; }
static inline void discora_track_buttons_reset(void) {}
static inline int discora_track_buttons_poll(bool available) { (void)available; return 0; }
#endif
