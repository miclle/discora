#include "cd_player_core.h"
#include <string.h>

cd_player_status_t cd_player_snapshot(const cd_player_core_t *p)
{
    cd_player_status_t status = {.media = p->media,
        .track = p->media ? p->toc.tracks[p->index].number : 0,
        .state = p->audio.state};
    if (p->media) {
        const probe_track_t *track = &p->toc.tracks[p->index];
        status.duration_sectors = track->end_lba - track->start_lba;
        uint64_t position = p->audio.dequeued_bytes / PROBE_CD_SECTOR_SIZE;
        status.position_sectors = position < status.duration_sectors ?
                                  (uint32_t)position : status.duration_sectors;
    }
    return status;
}

static bool eligible(const probe_track_t *t)
{
    return t->number && t->number <= 99 && !(t->control & 0x0c) &&
           t->end_lba <= INT32_MAX && t->start_lba < t->end_lba &&
           t->end_lba - t->start_lba >= PROBE_MAX_READ_SECTORS;
}
bool cd_player_init(cd_player_core_t *p, uint8_t *storage, size_t capacity, size_t prefill)
{
    if (!p || capacity < PROBE_MAX_READ_SECTORS * PROBE_CD_SECTOR_SIZE) return false;
    memset(p, 0, sizeof(*p));
    p->prefill = prefill;
    return audio_core_init(&p->audio, storage, capacity, prefill);
}
void cd_player_stop(cd_player_core_t *p)
{
    audio_core_stop(&p->audio);
    p->pending = p->eof = p->continuous = p->rebuffering = false;
    if (p->media) p->next_lba = p->toc.tracks[p->index].start_lba;
}
void cd_player_fault(cd_player_core_t *p)
{
    p->continuous = p->rebuffering = false;
    audio_core_fault(&p->audio);
}
void cd_player_lost(cd_player_core_t *p)
{
    cd_player_stop(p);
    p->media = false;
    cd_player_fault(p);
}
static void select_index(cd_player_core_t *p, size_t index)
{
    p->index = index;
    cd_player_stop(p);
    uint64_t bytes = (uint64_t)(p->toc.tracks[index].end_lba - p->next_lba) * PROBE_CD_SECTOR_SIZE;
    p->audio.prefill = bytes < p->prefill ? (size_t)bytes : p->prefill;
}
bool cd_player_media(cd_player_core_t *p, const probe_toc_t *toc)
{
    if (!p || !toc || !toc->track_count || toc->track_count > PROBE_MAX_TRACKS) return false;
    size_t first = toc->track_count;
    for (size_t i = 0; i < toc->track_count; ++i) if (eligible(&toc->tracks[i])) { first = i; break; }
    if (first == toc->track_count) { cd_player_lost(p); return false; }
    p->toc = *toc;
    p->media = true;
    select_index(p, first); // New media never starts playback automatically.
    return true;
}
bool cd_player_select(cd_player_core_t *p, unsigned track)
{
    if (!p->media || p->audio.state == AUDIO_FAULT) return false;
    for (size_t i = 0; i < p->toc.track_count; ++i) {
        if (p->toc.tracks[i].number == track && eligible(&p->toc.tracks[i])) {
            select_index(p, i);
            return audio_core_play(&p->audio);
        }
    }
    return false;
}
bool cd_player_step(cd_player_core_t *p, int direction)
{
    if (!p->media || (direction != -1 && direction != 1)) return false;
    bool paused = p->audio.state == AUDIO_PAUSED;
    size_t i = p->index;
    // Manual navigation wraps once, skips unsupported tracks, and never reselects self.
    for (size_t visited = 1; visited < p->toc.track_count; ++visited) {
        i = direction > 0 ? (i + 1) % p->toc.track_count :
                            (i ? i - 1 : (size_t)p->toc.track_count - 1);
        if (!eligible(&p->toc.tracks[i])) continue;
        if (!cd_player_select(p, p->toc.tracks[i].number)) return false;
        p->continuous = true;
        if (paused) cd_player_pause(p);
        return true;
    }
    return false;
}
static void recovered(cd_player_core_t *p)
{
    if (p->rebuffering && p->audio.state == AUDIO_PLAYING) {
        ++p->auto_recoveries;
        p->rebuffering = false;
    }
}
bool cd_player_rebuffer(cd_player_core_t *p)
{
    if (!p->auto_recover || !p->media || p->audio.state != AUDIO_UNDERRUN) return false;
    p->rebuffering = true;
    bool ok = audio_core_play(&p->audio);
    if (ok && p->eof && p->audio.pcm.used) p->audio.state = AUDIO_PLAYING;
    recovered(p);
    return ok;
}
bool cd_player_play(cd_player_core_t *p)
{
    if (!p->media || p->audio.state == AUDIO_FAULT) return false;
    if (p->continuous && p->eof && !p->audio.pcm.used && p->audio.state == AUDIO_PAUSED) {
        // Re-enter take(0) so the owner can finish verification before advancing.
        p->audio.state = AUDIO_PLAYING;
        return true;
    }
    if (p->eof && !p->audio.pcm.used) select_index(p, p->index);
    bool ok = audio_core_play(&p->audio);
    // EOF has no producer left to reach the normal prefill threshold.
    if (ok && p->eof && p->audio.pcm.used) p->audio.state = AUDIO_PLAYING;
    return ok;
}
bool cd_player_play_disc(cd_player_core_t *p)
{
    if (!p->media || p->audio.state == AUDIO_FAULT) return false;
    select_index(p, p->index);
    p->continuous = audio_core_play(&p->audio);
    return p->continuous;
}
bool cd_player_toggle(cd_player_core_t *p)
{
    if (!p->media || p->audio.state == AUDIO_FAULT) return false;
    if (p->audio.state == AUDIO_PAUSED) return cd_player_play(p);
    // STOPPED during continuous EOF drain is still an active sequence: pause it.
    if (p->audio.state == AUDIO_STOPPED && !p->continuous) return cd_player_play_disc(p);
    return cd_player_pause(p);
}
bool cd_player_advance(cd_player_core_t *p)
{
    if (!p->continuous || !p->media || !p->eof || p->pending || p->audio.pcm.used ||
        p->audio.state != AUDIO_STOPPED) return false;
    for (size_t i=p->index+1; i<p->toc.track_count; ++i) {
        if (eligible(&p->toc.tracks[i])) {
            select_index(p,i);
            p->continuous = audio_core_play(&p->audio);
            return p->continuous;
        }
    }
    // Natural disc end: output owner has drained/closed and recorded the last EOF.
    // Select the first playable track without arming playback or issuing a read.
    for (size_t i = 0; i < p->toc.track_count; ++i) {
        if (eligible(&p->toc.tracks[i])) {
            select_index(p, i);
            return false;
        }
    }
    cd_player_fault(p); // A valid published TOC always has a playable track.
    return false;
}
bool cd_player_pause(cd_player_core_t *p)
{
    if (p->continuous && p->eof && p->audio.state == AUDIO_STOPPED) {
        p->audio.state = AUDIO_PAUSED; // Also allow pause during the owner's EOF drain.
        return true;
    }
    bool ok = audio_core_pause(&p->audio);
    if (ok) p->rebuffering = false; // Explicit pause cancels automatic recovery.
    return ok;
}
bool cd_player_request(cd_player_core_t *p, cd_player_read_t *out)
{
    if (!p->media || p->pending || p->eof ||
        (p->audio.state != AUDIO_PREFILL && p->audio.state != AUDIO_PLAYING)) return false;
    const probe_track_t *track = &p->toc.tracks[p->index];
    uint32_t sectors = track->end_lba - p->next_lba;
    if (sectors > PROBE_MAX_READ_SECTORS) sectors = PROBE_MAX_READ_SECTORS;
    if (!sectors || p->audio.pcm.capacity - p->audio.pcm.used < (size_t)sectors * PROBE_CD_SECTOR_SIZE) return false;
    if (++p->serial == 0) ++p->serial;
    p->request = (cd_player_read_t){.track = *track, .lba = p->next_lba, .sectors = sectors,
        .generation = p->audio.generation, .serial = p->serial};
    p->pending = true;
    *out = p->request;
    return true;
}
bool cd_player_read_current(const cd_player_core_t *p, const cd_player_read_t *r)
{
    return r && p->pending && r->generation == p->audio.generation && r->serial == p->request.serial;
}
bool cd_player_complete(cd_player_core_t *p, const cd_player_read_t *r,
                        bool ok, const uint8_t *data, size_t size)
{
    if (!cd_player_read_current(p, r)) {
        ++p->stale_completions; return false;
    }
    p->pending = false;
    if (!ok || !data || size != (size_t)p->request.sectors * PROBE_CD_SECTOR_SIZE ||
        !audio_core_push(&p->audio, r->generation, data, size)) {
        cd_player_fault(p);
        return false;
    }
    ++p->completed_reads;
    p->next_lba += p->request.sectors;
    p->eof = p->next_lba == p->request.track.end_lba;
    if (p->eof && p->audio.state == AUDIO_PREFILL) p->audio.state = AUDIO_PLAYING;
    recovered(p);
    return true;
}
size_t cd_player_take(cd_player_core_t *p, uint8_t *data, size_t wanted)
{
    if (p->audio.state != AUDIO_PLAYING) return 0;
    if (p->eof && !p->audio.pcm.used) { p->audio.state = AUDIO_STOPPED; return 0; }
    if (p->eof && wanted > p->audio.pcm.used) wanted = p->audio.pcm.used;
    bool ok = audio_core_take(&p->audio, data, wanted);
    if ((p->audio.state == AUDIO_UNDERRUN && !p->auto_recover) || p->audio.state == AUDIO_FAULT)
        p->continuous = false;
    return ok ? wanted : 0;
}
