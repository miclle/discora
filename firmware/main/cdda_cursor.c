#include "cdda_cursor.h"

bool cdda_cursor_init(cdda_cursor_t *out, const probe_toc_t *toc, size_t index,
                       uint32_t lba, uint32_t sectors)
{
    if (!out || !toc || !sectors || !toc->track_count ||
        toc->track_count > PROBE_MAX_TRACKS || index >= toc->track_count) {
        return false;
    }
    cdda_cursor_t cursor = {.toc = toc, .index = index, .lba = lba, .remaining = sectors};
    while (sectors) {
        const probe_track_t *track = &toc->tracks[index];
        if ((track->control & 0x0c) || !track->number || track->number > 99 ||
            track->start_lba >= track->end_lba || track->end_lba > INT32_MAX ||
            lba < track->start_lba || lba >= track->end_lba) {
            return false;
        }
        uint32_t available = track->end_lba - lba;
        if (sectors <= available) {
            *out = cursor;
            return true;
        }
        sectors -= available;
        if (++index >= toc->track_count || toc->tracks[index].start_lba != track->end_lba ||
            toc->tracks[index].number != track->number + 1) {
            return false;
        }
        lba = toc->tracks[index].start_lba;
    }
    return false;
}

bool cdda_cursor_next(const cdda_cursor_t *cursor, const probe_track_t **track,
                       uint32_t *lba, uint8_t *sectors)
{
    if (!cursor || !cursor->toc || !track || !lba || !sectors || !cursor->remaining ||
        cursor->index >= cursor->toc->track_count) {
        return false;
    }
    const probe_track_t *t = &cursor->toc->tracks[cursor->index];
    if (cursor->lba < t->start_lba || cursor->lba >= t->end_lba) {
        return false;
    }
    uint32_t count = t->end_lba - cursor->lba;
    if (count > cursor->remaining) count = cursor->remaining;
    if (count > PROBE_MAX_READ_SECTORS) count = PROBE_MAX_READ_SECTORS;
    *track = t;
    *lba = cursor->lba;
    *sectors = (uint8_t)count;
    return true;
}

bool cdda_cursor_advance(cdda_cursor_t *cursor, uint8_t sectors)
{
    const probe_track_t *track;
    uint32_t lba;
    uint8_t available;
    if (!cdda_cursor_next(cursor, &track, &lba, &available) || !sectors || sectors > available) {
        return false;
    }
    cursor->lba += sectors;
    cursor->remaining -= sectors;
    if (cursor->remaining && cursor->lba == track->end_lba) {
        ++cursor->index;
    }
    return true;
}
