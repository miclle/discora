#include "transfer_wait.h"
#include "cd_player_core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    int64_t now, callback_at, gone_at;
    bool owned, gone, cancellable, control_changes;
    unsigned expired, stops, selects;
    cd_player_core_t *player;
} fake_t;
static int64_t now(void *p) { return ((fake_t *)p)->now; }
static bool owned(void *p) { return ((fake_t *)p)->owned; }
static bool gone(void *p) { return ((fake_t *)p)->gone; }
static void events(void *p, unsigned wait)
{
    fake_t *f=p; assert(wait==20); f->now+=wait;
    if (f->control_changes && f->now==40) { cd_player_stop(f->player);++f->stops; }
    if (f->control_changes && f->now==60) { assert(cd_player_select(f->player,2));++f->selects; }
    if (f->gone_at>=0 && f->now>=f->gone_at) f->gone=true;
    if (f->callback_at>=0 && f->now>=f->callback_at) f->owned=false;
}
static void expired(void *p, bool disconnected, bool cancellable)
{ fake_t *f=p;assert(disconnected==f->gone);++f->expired;f->cancellable=cancellable; }
static transfer_wait_result_t run(fake_t *f, bool cancel)
{
    const transfer_wait_ops_t ops={f,now,events,owned,gone,expired};
    return transfer_wait(&ops,100,200,cancel);
}
int main(void)
{
    fake_t f={.owned=true,.callback_at=80,.gone_at=-1};
    assert(run(&f,true)==TRANSFER_WAIT_COMPLETE && !f.owned && !f.expired && f.now==80);
    f=(fake_t){.owned=true,.callback_at=160,.gone_at=-1};
    assert(run(&f,true)==TRANSFER_WAIT_TIMEOUT && !f.owned && f.expired==1 && f.cancellable && f.now==160);
    f=(fake_t){.owned=true,.callback_at=-1,.gone_at=-1};
    assert(run(&f,true)==TRANSFER_WAIT_TIMEOUT && f.owned && f.now==300); // quarantine; never clear ownership
    f.callback_at=340;events(&f,20);assert(f.owned);events(&f,20);assert(!f.owned); // late callback finally returns it
    f=(fake_t){.owned=true,.callback_at=-1,.gone_at=-1};
    assert(run(&f,false)==TRANSFER_WAIT_TIMEOUT && f.owned && !f.cancellable && f.now==300); // EP0 cannot cancel
    f=(fake_t){.owned=true,.callback_at=160,.gone_at=40};
    assert(run(&f,true)==TRANSFER_WAIT_DISCONNECTED && !f.owned && f.expired==1);
    f=(fake_t){.owned=true,.callback_at=40,.gone_at=40};
    assert(run(&f,true)==TRANSFER_WAIT_DISCONNECTED && !f.expired);

    f=(fake_t){.owned=true,.callback_at=-1,.gone_at=-1};
    const transfer_wait_ops_t long_ops={&f,now,events,owned,gone,expired};
    assert(transfer_wait(&long_ops,30000,2000,true)==TRANSFER_WAIT_TIMEOUT && f.now==32000 && f.owned);

    uint8_t storage[16*PROBE_CD_SECTOR_SIZE], data[8*PROBE_CD_SECTOR_SIZE];memset(data,0xa5,sizeof(data));
    probe_toc_t toc={.track_count=2,.tracks={{.number=1,.start_lba=0,.end_lba=100}, {.number=2,.start_lba=100,.end_lba=200}}};
    cd_player_core_t player;cd_player_read_t old,newer;
    assert(cd_player_init(&player,storage,sizeof(storage),sizeof(data)) && cd_player_media(&player,&toc));
    assert(cd_player_play(&player) && cd_player_request(&player,&old));
    f=(fake_t){.owned=true,.callback_at=5000,.gone_at=-1,.control_changes=true,.player=&player};
    const transfer_wait_ops_t ops={&f,now,events,owned,gone,expired};
    assert(transfer_wait(&ops,10000,200,true)==TRANSFER_WAIT_COMPLETE && f.stops==1 && f.selects==1);
    assert(player.audio.pcm.used==0 && cd_player_request(&player,&newer));
    assert(!cd_player_complete(&player,&old,true,data,sizeof(data)) && player.pending);
    assert(cd_player_complete(&player,&newer,true,data,sizeof(data)) && player.next_lba==108);
    puts("PASS: shared USB wait deadlines, cancellation/EP0 quarantine, late ownership return and stop/track during pending reply (scripted, no device)");
}
