#include "cd_player_core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint32_t rng;
static uint32_t random32(void) { rng ^= rng<<13; rng ^= rng>>17; rng ^= rng<<5; return rng; }
static uint8_t storage[16*2352], expected[16*2352], data[8*2352], output[8*2352];
static unsigned accepted, discarded, takes, eof_stops, faults, underruns;
static void payload(const cd_player_read_t *r)
{
    for (size_t i=0;i<(size_t)r->sectors*2352;++i) data[i]=(uint8_t)(((uint64_t)r->lba*2352+i)%251);
}
int main(void)
{
    const probe_toc_t toc={.track_count=3,.tracks={
        {.number=1,.start_lba=0,.end_lba=17}, {.number=2,.control=4,.start_lba=17,.end_lba=30},
        {.number=3,.start_lba=30,.end_lba=47}}};
    for (unsigned seed=1;seed<=100;++seed) {
        rng=seed; cd_player_core_t p;size_t used=0;
        cd_player_read_t requests[8],duplicate={0}; bool occupied[8]={0}, have_duplicate=false;
        assert(cd_player_init(&p,storage,sizeof(storage),sizeof(data)) && cd_player_media(&p,&toc));
        for (unsigned step=0;step<5000;++step) {
            uint32_t gen=p.audio.generation;audio_state_t state=p.audio.state;
            unsigned roll=random32()%100;
            unsigned action=roll<20?5:roll<50?6:roll<75?8:random32()%12;
            switch(action) {
            case 0: cd_player_play(&p);break;
            case 1: cd_player_pause(&p);break;
            case 2: cd_player_stop(&p);break;
            case 3: cd_player_select(&p,1+random32()%3);break;
            case 4: cd_player_step(&p,(random32()&1)?1:-1);break;
            case 5:
                for(unsigned i=0;i<8;++i) if(!occupied[i]) { occupied[i]=cd_player_request(&p,&requests[i]);break; }
                break;
            case 6: case 7: {
                unsigned i=random32()%8;
                unsigned scan=0;
                while(!occupied[i] && scan++<8) i=(i+1)%8;
                if(!occupied[i]) break;
                cd_player_read_t r=requests[i];occupied[i]=false;duplicate=r;have_duplicate=true;payload(&r);
                bool ok=random32()%10!=0;
                size_t n=(size_t)r.sectors*2352;if(random32()%20==0) n-=4;
                uint32_t serial=p.request.serial;bool pending=p.pending;
                bool current=pending && r.generation==gen && r.serial==serial;
                bool result=cd_player_complete(&p,&r,ok,ok?data:NULL,n);
                if(result) { assert(current && ok && n==(size_t)r.sectors*2352 && used+n<=sizeof(expected));memcpy(expected+used,data,n);used+=n;++accepted; }
                else { ++discarded;if(!current) assert(p.pending==pending && p.request.serial==serial); }
                break;
            }
            case 8: {
                size_t n=cd_player_take(&p,output,(random32()&1)?1764:7056);
                assert(n<=used && !memcmp(output,expected,n));
                if(n) { memmove(expected,expected+n,used-n);used-=n;++takes; }
                if(state==AUDIO_PLAYING && p.audio.state==AUDIO_STOPPED) { assert(p.eof && !used);++eof_stops; }
                break;
            }
            case 9: if(random32()&1) cd_player_lost(&p);else assert(cd_player_media(&p,&toc));break;
            case 10:
                if(have_duplicate) {
                    payload(&duplicate);assert(!cd_player_complete(&p,&duplicate,true,data,(size_t)duplicate.sectors*2352));++discarded;
                }
                break;
            case 11: assert(!cd_player_select(&p,99));break;
            }
            if(p.audio.generation!=gen) used=0;
            assert(p.audio.pcm.used==used && used<=sizeof(storage) && used%4==0 && p.audio.generation);
            if(p.media) { assert(p.toc.tracks[p.index].number!=2);assert(p.next_lba>=p.toc.tracks[p.index].start_lba && p.next_lba<=p.toc.tracks[p.index].end_lba); }
            if(p.pending) assert(p.request.generation==p.audio.generation && p.request.sectors>=1 && p.request.sectors<=8 && p.request.lba+p.request.sectors<=p.request.track.end_lba);
            if(p.audio.state==AUDIO_FAULT && state!=AUDIO_FAULT) ++faults;
            if(p.audio.state==AUDIO_UNDERRUN && state!=AUDIO_UNDERRUN) ++underruns;
        }
    }
    assert(accepted && discarded && takes && eof_stops && faults && underruns);
    printf("PASS: 100 fixed seeds / 500000 player actions; accepted=%u stale/failure=%u takes=%u EOF=%u faults=%u underruns=%u (synthetic independent FIFO oracle)\n",accepted,discarded,takes,eof_stops,faults,underruns);
}
