#pragma once
#include "audio_core.h"
#include "probe_protocol.h"

typedef struct {
    probe_track_t track;
    uint32_t lba, generation, serial;
    uint8_t sectors;
} cd_player_read_t;
typedef struct {
    audio_core_t audio;
    probe_toc_t toc;
    size_t index, prefill;
    uint32_t next_lba, serial, completed_reads, stale_completions;
    bool media, eof, pending, continuous;
    cd_player_read_t request;
} cd_player_core_t;
// Caller serializes every operation. Requests contain values, never borrowed TOC pointers.
bool cd_player_init(cd_player_core_t *p, uint8_t *storage, size_t capacity, size_t prefill);
bool cd_player_media(cd_player_core_t *p, const probe_toc_t *toc);
void cd_player_lost(cd_player_core_t *p);
bool cd_player_select(cd_player_core_t *p, unsigned track);
bool cd_player_step(cd_player_core_t *p, int direction);
bool cd_player_play(cd_player_core_t *p);
// Restart the selected track, then advance at EOF without wrapping; boot/media never arms this.
bool cd_player_play_disc(cd_player_core_t *p);
// Output owner calls only after its adapter is fully closed. Core also requires drained EOF.
bool cd_player_advance(cd_player_core_t *p);
void cd_player_fault(cd_player_core_t *p);
bool cd_player_pause(cd_player_core_t *p);
void cd_player_stop(cd_player_core_t *p);
bool cd_player_request(cd_player_core_t *p, cd_player_read_t *request);
// False means stale/discarded or fault; caller must not copy bytes from a failed transfer.
bool cd_player_complete(cd_player_core_t *p, const cd_player_read_t *request,
                        bool ok, const uint8_t *data, size_t size);
size_t cd_player_take(cd_player_core_t *p, uint8_t *data, size_t wanted);
