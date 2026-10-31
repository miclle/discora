#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum { TONE_LEFT, TONE_RIGHT, TONE_STEREO, TONE_SILENCE } test_tone_mode_t;
typedef struct { test_tone_mode_t mode; unsigned phase; } test_tone_t;
// Explicit diagnostic PCM16LE L/R interleaving, never optical drive data.
// At 44100 Hz: left=441 Hz, right=882 Hz, peak=4096 (about -18 dBFS).
bool test_tone_init(test_tone_t *tone, test_tone_mode_t mode);
bool test_tone_render(test_tone_t *tone, uint8_t *pcm, size_t size);
const char *test_tone_name(test_tone_mode_t mode);
