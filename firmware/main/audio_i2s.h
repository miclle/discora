#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdatomic.h>
#include "driver/i2s_std.h"

enum { AUDIO_BLOCK_FRAMES = 441, AUDIO_BLOCK_BYTES = 441 * 4,
       AUDIO_DMA_BLOCKS = 4, AUDIO_PRELOAD_BYTES = AUDIO_BLOCK_BYTES * AUDIO_DMA_BLOCKS };
typedef struct {
    i2s_chan_handle_t channel;
    bool running;
    int64_t drain_until;
    uint64_t submitted_pcm, padding_bytes;
    uint32_t opens, closes, write_errors;
    atomic_uint dma_blocks, event_overflows, unexpected_dma_sizes;
} audio_i2s_t;
// Zero-initialize the adapter; one task owns it. Pause/stop close and recreate it to discard stale DMA.
esp_err_t audio_i2s_open(audio_i2s_t *out, int bclk, int lrck, int data);
esp_err_t audio_i2s_start(audio_i2s_t *out, const uint8_t *pcm, size_t size);
esp_err_t audio_i2s_write(audio_i2s_t *out, const uint8_t *pcm, size_t size);
esp_err_t audio_i2s_close(audio_i2s_t *out);
// Short EOF preload is frame-aligned and padded with silence after the final PCM.
// Caller passes monotonic microseconds; this is a bounded policy, not a DMA completion measurement.
void audio_i2s_eof(audio_i2s_t *out, int64_t now);
bool audio_i2s_draining(const audio_i2s_t *out, int64_t now);
