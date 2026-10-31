#pragma once
#include "probe_protocol.h"

typedef struct {
    const probe_toc_t *toc;
    size_t index;
    uint32_t lba;
    uint32_t remaining;
} cdda_cursor_t;

// Plan one continuous stereo-audio interval; reject gaps, data/four-channel tracks and EOF.
bool cdda_cursor_init(cdda_cursor_t *cursor, const probe_toc_t *toc, size_t index,
                       uint32_t lba, uint32_t sectors);
bool cdda_cursor_next(const cdda_cursor_t *cursor, const probe_track_t **track,
                       uint32_t *lba, uint8_t *sectors);
bool cdda_cursor_advance(cdda_cursor_t *cursor, uint8_t sectors);
