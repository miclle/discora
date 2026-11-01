#pragma once
#include "audio_i2s.h"
#include "audio_report.h"
#include <inttypes.h>
// Only call from the task owning the adapter; ISR counters are independent snapshots.
static inline void audio_i2s_report(const char *tag, const audio_i2s_t *out)
{
    audio_report(tag,"i2s tx=%s handle=%u pcm_submitted=%" PRIu64 " padding=%" PRIu64
             " dma_blocks=%u event_overflows=%u bad_dma_sizes=%u write_errors=%" PRIu32 " opens=%" PRIu32 " closes=%" PRIu32,
             out->running ? "running" : "closed", out->channel != NULL, out->submitted_pcm, out->padding_bytes,
             atomic_load_explicit(&out->dma_blocks,memory_order_relaxed),
             atomic_load_explicit(&out->event_overflows,memory_order_relaxed),
             atomic_load_explicit(&out->unexpected_dma_sizes,memory_order_relaxed), out->write_errors, out->opens, out->closes);
}
