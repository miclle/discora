#include "cd_player_core.h"
#include "cd_read_stats.h"
#include "pcm_gain.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint8_t storage[16 * PROBE_CD_SECTOR_SIZE];
static uint8_t data[8 * PROBE_CD_SECTOR_SIZE], out[sizeof(data)];
static cd_player_core_t p;
static probe_toc_t toc;
static void init(unsigned sectors)
{
    memset(&toc, 0, sizeof(toc)); toc.track_count = 2;
    toc.tracks[0] = (probe_track_t){.number=1,.start_lba=0,.end_lba=sectors};
    toc.tracks[1] = (probe_track_t){.number=2,.start_lba=sectors,.end_lba=sectors+16};
    assert(cd_player_init(&p, storage, sizeof(storage), sizeof(data)));
    p.auto_recover = true;
    assert(cd_player_media(&p, &toc) && cd_player_play_disc(&p));
}
static void complete(const cd_player_read_t *r)
{
    size_t n = r->sectors * PROBE_CD_SECTOR_SIZE;
    for (size_t i=0; i<n; ++i) data[i]=(uint8_t)(((uint64_t)r->lba*PROBE_CD_SECTOR_SIZE+i)%251);
    assert(cd_player_complete(&p, r, true, data, n));
}
static void consume(unsigned sectors, unsigned from)
{
    size_t n = sectors * PROBE_CD_SECTOR_SIZE;
    assert(cd_player_take(&p,out,n)==n);
    for (size_t i=0; i<n; ++i) assert(out[i]==(uint8_t)(((uint64_t)from*PROBE_CD_SECTOR_SIZE+i)%251));
}
static cd_player_read_t starve(void)
{
    cd_player_read_t r;
    assert(cd_player_request(&p,&r)); complete(&r); consume(8,0);
    assert(cd_player_request(&p,&r) && r.lba==8);
    assert(!cd_player_take(&p,out,1764));
    assert(p.audio.state==AUDIO_UNDERRUN && p.audio.underruns==1 && p.continuous && p.pending);
    return r;
}
static void recovery_orderings(void)
{
    init(64); cd_player_read_t r=starve(); uint32_t gen=p.audio.generation;
    assert(cd_player_rebuffer(&p) && p.rebuffering && p.audio.state==AUDIO_PREFILL);
    assert(!cd_player_request(&p,&(cd_player_read_t){0})); // Original request remains owned.
    complete(&r);
    assert(p.audio.state==AUDIO_PLAYING && !p.rebuffering && p.auto_recoveries==1);
    assert(p.audio.generation==gen && p.next_lba==16 && p.continuous);
    consume(8,8); // Exact following PCM, no restart/duplication/skipped source bytes.
    assert(cd_player_request(&p,&r) && r.lba==16);
    assert(!cd_player_take(&p,out,1764));
    assert(cd_player_rebuffer(&p)); complete(&r); consume(8,16);
    assert(p.auto_recoveries==2 && p.audio.underruns==2 && p.audio.generation==gen);

    init(64); r=starve(); gen=p.audio.generation;
    complete(&r); // USB returns before output owner closes/rebuffers.
    assert(p.audio.state==AUDIO_UNDERRUN && p.auto_recoveries==0);
    assert(cd_player_rebuffer(&p) && p.audio.state==AUDIO_PLAYING && p.auto_recoveries==1);
    assert(p.audio.generation==gen && p.continuous); consume(8,8);
}
static void cancellations(void)
{
    init(64); cd_player_read_t r=starve();
    assert(cd_player_rebuffer(&p) && cd_player_pause(&p));
    complete(&r);
    assert(p.audio.state==AUDIO_PAUSED && !p.rebuffering && p.auto_recoveries==0);
    assert(!cd_player_rebuffer(&p) && cd_player_play(&p)); consume(8,8);

    init(64); r=starve();
    assert(cd_player_pause(&p) && !cd_player_rebuffer(&p)); complete(&r);
    assert(p.audio.state==AUDIO_PAUSED && p.auto_recoveries==0);

    init(64); r=starve(); assert(cd_player_rebuffer(&p)); cd_player_stop(&p);
    assert(!cd_player_complete(&p,&r,true,data,sizeof(data)));
    assert(p.audio.state==AUDIO_STOPPED && !p.continuous && !p.rebuffering && !cd_player_rebuffer(&p));

    init(64); r=starve(); assert(cd_player_rebuffer(&p));
    assert(cd_player_select(&p,2)); cd_player_read_t newer;
    assert(cd_player_request(&p,&newer));
    assert(!cd_player_complete(&p,&r,true,data,sizeof(data)) && p.pending && !p.rebuffering);
    complete(&newer); consume(8,64);

    init(64); r=starve(); assert(cd_player_rebuffer(&p)); cd_player_lost(&p);
    assert(!cd_player_complete(&p,&r,true,data,sizeof(data)) && p.audio.state==AUDIO_FAULT);
    assert(!cd_player_rebuffer(&p) && cd_player_media(&p,&toc) && p.audio.state==AUDIO_STOPPED);

    init(64); r=starve(); assert(cd_player_rebuffer(&p));
    assert(!cd_player_complete(&p,&r,false,NULL,0));
    assert(p.audio.state==AUDIO_FAULT && !p.continuous && !p.rebuffering && !cd_player_rebuffer(&p));
    init(64); r=starve(); (void)r; cd_player_fault(&p); // Output-close failure.
    assert(!cd_player_rebuffer(&p) && !p.continuous);
}
static void short_eof(void)
{
    init(17); cd_player_read_t r;
    for (unsigned i=0;i<2;++i) { assert(cd_player_request(&p,&r)); complete(&r); consume(8,8*i); }
    assert(cd_player_request(&p,&r) && r.sectors==1);
    assert(!cd_player_take(&p,out,1764) && cd_player_rebuffer(&p));
    complete(&r);
    assert(p.eof && p.audio.state==AUDIO_PLAYING && p.auto_recoveries==1);
    assert(cd_player_take(&p,out,7056)==PROBE_CD_SECTOR_SIZE);
    for (size_t i=0;i<PROBE_CD_SECTOR_SIZE;++i) assert(out[i]==(uint8_t)((16*PROBE_CD_SECTOR_SIZE+i)%251));
    assert(!cd_player_take(&p,out,1764) && p.audio.state==AUDIO_STOPPED);
    assert(cd_player_advance(&p) && p.index==1 && p.continuous && !p.rebuffering);
}
static void metrics_and_gain(void)
{
    cd_read_stats_t s={0};
    cd_read_stats_record(&s,8,99999,true,true);
    cd_read_stats_record(&s,16,100000,true,false);
    cd_read_stats_record(&s,24,500000,false,false);
    cd_read_stats_record(&s,32,2000000,true,true);
    assert(s.count==4 && s.total_us==2699999 && s.last_us==2000000 && s.max_us==2000000);
    assert(s.last_lba==32 && s.max_lba==32 && s.failed==1 && s.rejected==2);
    assert(s.over_100ms==3 && s.over_500ms==2 && s.over_1s==1);
    const uint8_t original[]={0xff,0x7f,0x00,0x80,0xff,0xff,0x01,0x00};
    uint8_t pcm[sizeof(original)]; memcpy(pcm,original,sizeof(pcm));
    pcm_gain(pcm,sizeof(pcm),100); assert(!memcmp(pcm,original,sizeof(pcm)));
    pcm_gain(pcm,sizeof(pcm),25);
    const uint8_t quarter[]={0xff,0x1f,0x00,0xe0,0x00,0x00,0x00,0x00};
    assert(!memcmp(pcm,quarter,sizeof(pcm)));
}
int main(void)
{
    recovery_orderings(); cancellations(); short_eof(); metrics_and_gain();
    puts("PASS: automatic rebuffer preserves PCM/cursor/sequence, cancels on controls/fault/loss, handles short EOF; timing thresholds and stereo gain (offline)");
}
