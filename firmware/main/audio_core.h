#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "pcm_buffer.h"

typedef enum {
    AUDIO_STOPPED, AUDIO_PREFILL, AUDIO_PLAYING, AUDIO_PAUSED, AUDIO_UNDERRUN, AUDIO_FAULT,
} audio_state_t;

// No device calls or locking. One owner (or an externally serialized caller) is required.
typedef struct {
    pcm_buffer_t pcm;
    audio_state_t state;
    size_t prefill;
    uint32_t generation;
    uint32_t underruns;
    uint64_t dequeued_bytes; // Delivered to the output adapter, not confirmed audible frames.
} audio_core_t;

bool audio_core_init(audio_core_t *core, uint8_t *storage, size_t capacity, size_t prefill);
bool audio_core_play(audio_core_t *core);
bool audio_core_pause(audio_core_t *core);
void audio_core_stop(audio_core_t *core);
void audio_core_fault(audio_core_t *core);
bool audio_core_push(audio_core_t *core, uint32_t generation, const uint8_t *data, size_t size);
bool audio_core_take(audio_core_t *core, uint8_t *data, size_t size);
const char *audio_state_name(audio_state_t state);
