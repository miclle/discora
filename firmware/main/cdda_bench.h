#pragma once
#include "probe_protocol.h"

typedef struct {
    void *context;
    const probe_toc_t *toc;
    size_t resume_index;
    uint32_t resume_lba;
    // Reply bytes are borrowed until the next read; the bench copies/hashes before reuse.
    bool (*read)(void *context, const probe_track_t *track, uint32_t lba,
                  uint8_t sectors, const uint8_t **data, size_t *size);
    // Called only by the USB client task. Service callbacks and report device loss/fault.
    bool (*service)(void *context, unsigned wait_ms);
} cdda_bench_source_t;

bool cdda_bench_run(const cdda_bench_source_t *source, unsigned seconds, bool include_seeks, bool include_full_track);
