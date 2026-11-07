#pragma once
#include <stdbool.h>
#include <stdint.h>

// End-to-end read_audio latency, including any configured recovery, not raw USB timing.
typedef struct {
    uint64_t count, total_us, last_us, max_us;
    uint64_t failed, rejected, over_100ms, over_500ms, over_1s;
    uint32_t last_lba, max_lba;
} cd_read_stats_t;

static inline void cd_read_stats_record(cd_read_stats_t *s, uint32_t lba,
                                       uint64_t us, bool ok, bool accepted)
{
    ++s->count;
    s->total_us += us;
    s->last_us = us;
    s->last_lba = lba;
    if (us > s->max_us) { s->max_us = us; s->max_lba = lba; }
    if (!ok) ++s->failed;
    if (!accepted) ++s->rejected;
    if (us >= 100000) ++s->over_100ms;
    if (us >= 500000) ++s->over_500ms;
    if (us >= 1000000) ++s->over_1s;
}
