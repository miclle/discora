#pragma once
#include "esp_err.h"

// Single audio-owner task; two PCNT units retained for diagnostic lifetime.
// Counts the MCU GPIO input paths, not the DAC input or analog output.
esp_err_t audio_clock_probe_begin(int bclk, int lrck);
void audio_clock_probe_poll(void);
void audio_clock_probe_cancel(void);
