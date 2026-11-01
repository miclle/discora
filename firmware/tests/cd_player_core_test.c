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
int main(void)
{
    cd_player_read_t r, old, newer;
    init(); assert(!cd_player_request(&p,&r) && cd_player_play(&p));
    size_t delivered=0;
    for (unsigned guard=0; guard<100 && p.audio.state!=AUDIO_STOPPED; ++guard) {
        if (cd_player_request(&p,&r)) { assert(r.lba+r.sectors<=18); complete(&r); }
        size_t n=cd_player_take(&p,out,1764);
        for (size_t i=0;i<n;++i) assert(out[i]==(uint8_t)((delivered+i)%251));
        delivered+=n;
    }
    assert(delivered==18*PROBE_CD_SECTOR_SIZE && p.eof && p.audio.state==AUDIO_STOPPED && p.audio.underruns==0);
    assert(cd_player_play(&p) && p.next_lba==0);
    assert(cd_player_request(&p,&old));
    assert(cd_player_select(&p,3) && cd_player_request(&p,&newer));
    fill(&old); assert(!cd_player_complete(&p,&old,true,data,sizeof(data)) && p.pending);
    assert(p.audio.pcm.used==0 && newer.lba==30); complete(&newer);
    assert(p.audio.pcm.used==sizeof(data) && p.stale_completions==1);
    uint32_t gen=p.audio.generation;
    assert(!cd_player_select(&p,2) && !cd_player_step(&p,1) && p.audio.generation==gen);
    assert(cd_player_step(&p,-1) && p.index==0);
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
    puts("PASS: real player core ordering/EOF, partial tail, pause, stop/track stale reads, data-track rejection, explicit underrun restart and media loss (synthetic PCM, no device)");
    return 0;
}
