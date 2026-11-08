#include "cd_player_core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint8_t storage[16 * PROBE_CD_SECTOR_SIZE], data[8 * PROBE_CD_SECTOR_SIZE], out[8 * PROBE_CD_SECTOR_SIZE];
static probe_toc_t toc;
static cd_player_core_t p;
static void init(void)
{
    memset(&toc, 0, sizeof(toc)); toc.track_count = 3;
    toc.tracks[0] = (probe_track_t){.number=1,.start_lba=0,.end_lba=18};
    toc.tracks[1] = (probe_track_t){.number=2,.control=4,.start_lba=18,.end_lba=30};
    toc.tracks[2] = (probe_track_t){.number=3,.start_lba=30,.end_lba=46};
    assert(cd_player_init(&p,storage,sizeof(storage),sizeof(data)));
    assert(cd_player_media(&p,&toc) && p.audio.state == AUDIO_STOPPED);
}
static void fill(const cd_player_read_t *r)
{
    for (size_t i=0; i<(size_t)r->sectors*PROBE_CD_SECTOR_SIZE; ++i)
        data[i]=(uint8_t)(((uint64_t)r->lba*PROBE_CD_SECTOR_SIZE+i)%251);
}
static void complete(cd_player_read_t *r)
{
    fill(r); assert(cd_player_complete(&p,r,true,data,(size_t)r->sectors*PROBE_CD_SECTOR_SIZE));
}
static void drain_track(void)
{
    probe_track_t track=p.toc.tracks[p.index];
    size_t delivered=0;
    for (unsigned guard=0; guard<100 && p.audio.state!=AUDIO_STOPPED; ++guard) {
        cd_player_read_t r;
        if (cd_player_request(&p,&r)) {
            assert(r.lba>=track.start_lba && r.lba+r.sectors<=track.end_lba);
            complete(&r);
        }
        size_t n=cd_player_take(&p,out,1764);
        for (size_t i=0;i<n;++i)
            assert(out[i]==(uint8_t)(((uint64_t)track.start_lba*PROBE_CD_SECTOR_SIZE+delivered+i)%251));
        delivered+=n;
    }
    assert(p.eof && !p.pending && !p.audio.pcm.used && p.audio.state==AUDIO_STOPPED);
    assert(delivered==(track.end_lba-track.start_lba)*PROBE_CD_SECTOR_SIZE);
}
static void disc_sequence(void)
{
    cd_player_read_t r,old,newer;
    init(); assert(!p.continuous && !cd_player_advance(&p));
    assert(cd_player_play_disc(&p) && p.continuous && !cd_player_advance(&p));
    assert(cd_player_pause(&p) && p.continuous && !cd_player_advance(&p));
    assert(cd_player_play(&p) && p.continuous); drain_track();
    uint32_t gen=p.audio.generation;
    // Pause at the EOF/drain boundary must prevent an automatic next track.
    assert(cd_player_pause(&p) && !cd_player_advance(&p));
    assert(cd_player_play(&p) && p.audio.state==AUDIO_PLAYING && p.audio.generation==gen);
    assert(cd_player_take(&p,out,1764)==0 && p.audio.state==AUDIO_STOPPED);
    assert(cd_player_advance(&p) && p.continuous && p.index==2 && p.audio.generation!=gen);
    drain_track(); assert(!cd_player_advance(&p) && !p.continuous && p.index==0);
    assert(!cd_player_request(&p,&r)); assert(cd_player_play(&p) && !p.continuous);

    init(); assert(cd_player_play_disc(&p) && cd_player_request(&p,&old));
    cd_player_stop(&p); assert(!p.continuous && cd_player_play_disc(&p) && cd_player_request(&p,&newer));
    fill(&old); assert(!cd_player_complete(&p,&old,true,data,sizeof(data)) && p.pending && p.continuous);
    complete(&newer); assert(!cd_player_select(&p,2) && p.continuous);
    assert(cd_player_select(&p,3) && !p.continuous); // Manual navigation disarms the sequence.
    assert(cd_player_play_disc(&p) && cd_player_request(&p,&r));
    assert(!cd_player_complete(&p,&r,false,NULL,0) && !p.continuous && p.audio.state==AUDIO_FAULT);
    assert(!cd_player_play_disc(&p));
    cd_player_stop(&p); assert(cd_player_play_disc(&p)); cd_player_lost(&p);
    assert(!p.continuous && cd_player_media(&p,&toc) && !p.continuous && p.audio.state==AUDIO_STOPPED);

    init(); assert(cd_player_play_disc(&p) && cd_player_request(&p,&r)); complete(&r);
    assert(cd_player_take(&p,out,sizeof(data))==sizeof(data));
    assert(!cd_player_take(&p,out,4) && p.audio.state==AUDIO_UNDERRUN && !p.continuous);
    assert(cd_player_play(&p) && !p.continuous);
    cd_player_stop(&p); assert(cd_player_play_disc(&p)); cd_player_fault(&p);
    assert(!p.continuous && !cd_player_advance(&p));

    init(); assert(cd_player_play_disc(&p)); drain_track();
    p.audio.state=AUDIO_PLAYING; // Last PCM consumed, before owner's first take(0).
    assert(cd_player_pause(&p) && cd_player_play(&p));
    assert(!cd_player_take(&p,out,1764) && cd_player_advance(&p) && p.index==2);
}
static void front_panel(void)
{
    cd_player_read_t old, r;
    init();
    assert(cd_player_toggle(&p) && p.continuous && p.audio.state == AUDIO_PREFILL);
    assert(cd_player_request(&p, &old));
    uint32_t gen = p.audio.generation;
    assert(cd_player_toggle(&p) && p.audio.state == AUDIO_PAUSED);
    complete(&old); // An in-flight reply is retained, but never consumed while paused.
    assert(p.audio.state == AUDIO_PAUSED && !cd_player_request(&p, &r));
    assert(!cd_player_take(&p, out, 1764));
    assert(cd_player_toggle(&p) && p.audio.state == AUDIO_PLAYING && p.audio.generation == gen);
    assert(cd_player_take(&p, out, 1764) == 1764);
    for (size_t i = 0; i < 1764; ++i) assert(out[i] == (uint8_t)(i % 251));
    assert(cd_player_toggle(&p));
    size_t used = p.audio.pcm.used;
    uint32_t lba = p.next_lba;
    assert(cd_player_toggle(&p) && p.audio.pcm.used == used && p.next_lba == lba);
    assert(cd_player_request(&p, &r)); complete(&r); // Resume refills below the threshold.
    assert(cd_player_take(&p, out, 3528) == 3528);
    for (size_t i = 0; i < 3528; ++i) assert(out[i] == (uint8_t)((i + 1764) % 251));

    assert(cd_player_request(&p, &old));
    assert(cd_player_toggle(&p) && cd_player_step(&p, 1));
    assert(p.index == 2 && p.continuous && p.audio.state == AUDIO_PAUSED);
    assert(p.next_lba == 30 && !p.audio.pcm.used && !cd_player_request(&p, &r));
    fill(&old); assert(!cd_player_complete(&p, &old, true, data, sizeof(data)));
    gen = p.audio.generation;
    assert(cd_player_step(&p, 1) && p.index == 0 && p.audio.generation != gen && p.audio.state == AUDIO_PAUSED);
    assert(cd_player_step(&p, -1) && p.index == 2 && p.audio.state == AUDIO_PAUSED);
    assert(cd_player_toggle(&p)); drain_track();
    // Toggle during EOF drain pauses the sequence; it must not restart the track.
    gen = p.audio.generation;
    assert(cd_player_toggle(&p) && p.audio.state == AUDIO_PAUSED && !cd_player_advance(&p));
    assert(cd_player_toggle(&p) && p.audio.generation == gen);
    assert(!cd_player_take(&p, out, 1764) && !cd_player_advance(&p) && !p.continuous);
    assert(cd_player_toggle(&p) && p.next_lba == 0 && p.continuous);

    init(); p.auto_recover = true;
    assert(cd_player_toggle(&p) && cd_player_request(&p, &r)); complete(&r);
    assert(cd_player_take(&p, out, sizeof(data)) == sizeof(data));
    assert(!cd_player_take(&p, out, 4) && p.audio.state == AUDIO_UNDERRUN);
    assert(cd_player_toggle(&p) && !cd_player_rebuffer(&p));
    assert(p.audio.state == AUDIO_PAUSED && p.continuous);
    assert(cd_player_toggle(&p) && cd_player_request(&p, &r)); complete(&r);
    assert(cd_player_take(&p, out, sizeof(data)) == sizeof(data));
    assert(!cd_player_take(&p, out, 4) && cd_player_rebuffer(&p) && p.rebuffering);
    assert(cd_player_toggle(&p) && !p.rebuffering && !cd_player_rebuffer(&p));
    cd_player_fault(&p); gen = p.audio.generation;
    assert(!cd_player_toggle(&p) && !cd_player_step(&p, 1) && p.audio.generation == gen);
    cd_player_lost(&p); assert(!cd_player_toggle(&p));

    init(); toc.track_count = 1;
    assert(cd_player_media(&p, &toc));
    assert(!cd_player_step(&p, -1) && !cd_player_step(&p, 1));
    assert(cd_player_toggle(&p)); drain_track();
    assert(!cd_player_advance(&p) && !p.continuous); // Single-track discs can start and stop.
}
static void manual_wrap(void)
{
    cd_player_read_t old, next;
    init();
    // Unsupported tracks at both ends and between the two playable tracks.
    probe_toc_t mixed = {.track_count=5,.tracks={
        {.number=1,.control=4,.start_lba=0,.end_lba=16},
        {.number=2,.start_lba=16,.end_lba=32},
        {.number=3,.control=8,.start_lba=32,.end_lba=48},
        {.number=4,.start_lba=48,.end_lba=64},
        {.number=5,.start_lba=64,.end_lba=66},
    }};
    assert(cd_player_media(&p, &mixed) && p.index == 1);
    assert(cd_player_step(&p, -1) && p.index == 3 && p.continuous);
    assert(cd_player_request(&p, &old));
    uint32_t gen = p.audio.generation;
    assert(cd_player_step(&p, 1) && p.index == 1 && p.audio.generation != gen);
    assert(cd_player_request(&p, &next) && next.lba == 16);
    fill(&old); assert(!cd_player_complete(&p, &old, true, data, sizeof(data)) && p.pending);
    complete(&next);
    assert(p.audio.state == AUDIO_PLAYING && cd_player_step(&p, -1) && p.index == 3);
    assert(cd_player_pause(&p) && cd_player_step(&p, 1) && p.index == 1);
    assert(p.audio.state == AUDIO_PAUSED && !cd_player_request(&p, &next));
    assert(cd_player_step(&p, -1) && p.index == 3 && p.audio.state == AUDIO_PAUSED);
    assert(cd_player_toggle(&p) && cd_player_request(&p, &next) && next.lba == 48);
    // Only one eligible track: navigation is a no-op, even with other TOC entries.
    mixed.tracks[3].control = 4;
    assert(cd_player_media(&p, &mixed) && cd_player_toggle(&p));
    assert(cd_player_request(&p, &next)); complete(&next);
    gen = p.audio.generation; size_t used = p.audio.pcm.used;
    assert(!cd_player_step(&p, -1) && !cd_player_step(&p, 1));
    assert(p.index == 1 && p.audio.state == AUDIO_PLAYING && p.audio.generation == gen && p.audio.pcm.used == used);
}
static void disc_end_rewind(void)
{
    cd_player_read_t r, old;
    init();
    // A data track may precede the first playable track; use its actual TOC number.
    toc.tracks[0].control = 4;
    toc.tracks[1] = (probe_track_t){.number=2,.start_lba=18,.end_lba=30};
    assert(cd_player_media(&p, &toc));
    assert(cd_player_step(&p, 1) && p.index == 2 && p.continuous);
    assert(cd_player_request(&p, &old));
    complete(&old);
    // Final reset cannot happen with queued data or an outstanding read.
    assert(!cd_player_advance(&p) && p.index == 2);
    cd_player_stop(&p);
    assert(p.index == 2 && !cd_player_advance(&p)); // Manual stop retains selection.
    assert(cd_player_toggle(&p)); drain_track();
    uint32_t gen = p.audio.generation, reads = p.completed_reads;
    assert(cd_player_pause(&p) && !cd_player_advance(&p) && p.index == 2);
    assert(cd_player_toggle(&p) && !cd_player_take(&p, out, 1764));
    assert(!cd_player_advance(&p)); // Owner calls only after output drains/closes.
    assert(p.index == 1 && p.next_lba == 18 && p.audio.state == AUDIO_STOPPED);
    assert(!p.continuous && !p.eof && !p.pending && !p.audio.pcm.used && !p.audio.dequeued_bytes);
    assert(p.audio.generation != gen && p.completed_reads == reads);
    cd_player_status_t snapshot = cd_player_snapshot(&p);
    assert(snapshot.media && snapshot.track == 2 && snapshot.state == AUDIO_STOPPED);
    assert(!cd_player_request(&p, &r) && !cd_player_advance(&p));
    fill(&old); assert(!cd_player_complete(&p, &old, true, data, sizeof(data)));
    assert(cd_player_toggle(&p) && p.continuous && cd_player_request(&p, &r));
    assert(r.track.number == 2 && r.lba == 18);

    // Fault/media loss and diagnostic single-track EOF never trigger disc rewind.
    init(); assert(cd_player_select(&p, 3)); drain_track();
    assert(!cd_player_advance(&p) && p.index == 2 && p.eof);
    assert(cd_player_play_disc(&p)); cd_player_fault(&p);
    assert(!cd_player_advance(&p) && p.index == 2 && p.audio.state == AUDIO_FAULT);
    cd_player_lost(&p); assert(!cd_player_advance(&p) && !p.media);

    init(); toc.track_count = 1; assert(cd_player_media(&p, &toc));
    assert(cd_player_toggle(&p)); drain_track(); gen = p.audio.generation;
    assert(!cd_player_advance(&p) && p.index == 0 && !p.eof && !p.continuous);
    assert(p.audio.generation != gen && !cd_player_request(&p, &r));
    assert(cd_player_toggle(&p) && cd_player_request(&p, &r) && r.lba == 0);
}
int main(void)
{
    cd_player_read_t r, old, newer;
    init(); assert(!cd_player_request(&p,&r) && cd_player_play(&p));
    // 17 sectors produces a 1176-byte final output block (18 sectors did not).
    p.toc.tracks[0].end_lba=17;
    size_t delivered=0, tail=0;
    for (unsigned guard=0; guard<100 && p.audio.state!=AUDIO_STOPPED; ++guard) {
        if (cd_player_request(&p,&r)) { assert(r.lba+r.sectors<=17); complete(&r); }
        size_t n=cd_player_take(&p,out,1764);
        for (size_t i=0;i<n;++i) assert(out[i]==(uint8_t)((delivered+i)%251));
        delivered+=n; if (n) tail=n;
    }
    assert(delivered==17*PROBE_CD_SECTOR_SIZE && p.eof && p.audio.state==AUDIO_STOPPED && p.audio.underruns==0);
    assert(tail==1176 && !cd_player_request(&p,&r));
    assert(cd_player_play(&p) && p.next_lba==0);
    assert(cd_player_request(&p,&old));
    assert(cd_player_select(&p,3) && cd_player_request(&p,&newer));
    fill(&old); assert(!cd_player_complete(&p,&old,true,data,sizeof(data)) && p.pending);
    assert(p.audio.pcm.used==0 && newer.lba==30); complete(&newer);
    assert(p.audio.pcm.used==sizeof(data) && p.stale_completions==1);
    uint32_t gen=p.audio.generation;
    assert(!cd_player_select(&p,2) && p.audio.generation==gen);
    assert(cd_player_step(&p,1) && p.index==0 && p.audio.generation!=gen);
    assert(cd_player_request(&p,&old)); cd_player_stop(&p);
    assert(!cd_player_complete(&p,&old,false,NULL,0) && p.audio.state==AUDIO_STOPPED);
    assert(cd_player_play(&p) && cd_player_request(&p,&r));
    assert(cd_player_pause(&p)); complete(&r);
    assert(p.audio.state==AUDIO_PAUSED && cd_player_take(&p,out,1764)==0 && !cd_player_request(&p,&r));
    assert(cd_player_play(&p) && cd_player_take(&p,out,sizeof(data))==sizeof(data));
    assert(cd_player_take(&p,out,4)==0 && p.audio.state==AUDIO_UNDERRUN && p.audio.underruns==1);
    assert(!cd_player_request(&p,&r));
    assert(cd_player_play(&p) && cd_player_request(&p,&r)); complete(&r);
    assert(p.audio.state==AUDIO_PLAYING);
    cd_player_stop(&p); assert(cd_player_play(&p) && cd_player_request(&p,&r));
    assert(!cd_player_complete(&p,&r,true,data,4) && p.audio.state==AUDIO_FAULT);
    assert(!cd_player_play(&p) && !cd_player_select(&p,3));
    cd_player_stop(&p); assert(cd_player_play(&p) && cd_player_request(&p,&old));
    cd_player_lost(&p); assert(!p.media && !cd_player_complete(&p,&old,true,data,sizeof(data)));
    assert(!cd_player_play(&p)); assert(cd_player_media(&p,&toc) && p.audio.state==AUDIO_STOPPED);
    init(); p.toc.tracks[0].end_lba=17; assert(cd_player_play(&p));
    for (unsigned guard=0; !p.eof && guard<100; ++guard) {
        if (cd_player_request(&p,&r)) complete(&r);
        if (!p.eof) cd_player_take(&p,out,1764);
    }
    assert(p.eof);
    while (p.audio.pcm.used>1764) cd_player_take(&p,out,1764);
    assert(p.audio.pcm.used==1176 && cd_player_pause(&p));
    assert(cd_player_play(&p) && p.audio.state==AUDIO_PLAYING);
    assert(cd_player_take(&p,out,7056)==1176);
    assert(cd_player_take(&p,out,1764)==0 && p.audio.state==AUDIO_STOPPED);
    disc_sequence();
    front_panel();
    disc_end_rewind();
    manual_wrap();
    puts("PASS: disc EOF rewind/manual wrap/data-track skip and cancellation, real player core ordering/EOF, partial tail, pause, stop/track stale reads, data-track rejection, explicit underrun restart and media loss (synthetic PCM, no device)");
    return 0;
}
