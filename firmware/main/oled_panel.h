#pragma once
#include "cd_player_core.h"

enum { OLED_WIDTH = 128, OLED_HEIGHT = 64, OLED_FRAME_BYTES = 1024 };
typedef bool (*oled_write_fn)(void *context, const uint8_t *bytes, size_t size);

const char *oled_status_label(const cd_player_status_t *status);
void oled_render(uint8_t frame[OLED_FRAME_BYTES], const cd_player_status_t *status, bool i2s);
// SH1106 only. Caller supplies power-up delay, then waits 100 ms before display-on.
bool oled_panel_init(oled_write_fn write, void *context);
bool oled_panel_on(oled_write_fn write, void *context);
bool oled_panel_flush(oled_write_fn write, void *context, const uint8_t frame[OLED_FRAME_BYTES]);
