#include "cdda_recovery.h"
#include "cd_player_core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    cdda_recovery_t state;
    unsigned checks, fail_check, waits, ready_calls, replays;
    bool wait_ok, ready_ok, replay_ok;
    char order[8]; unsigned used;
} fixture_t;
static bool healthy(void *arg)
{
    fixture_t *f = arg;
    return ++f->checks != f->fail_check;
}
static bool wait_for_device(void *arg, unsigned ms)
{
    fixture_t *f = arg;
    assert(ms == 1000 && f->state.reserved == 1);
    ++f->waits; f->order[f->used++] = 'W'; return f->wait_ok;
}
static bool ready(void *arg)
{
    fixture_t *f = arg;
    ++f->ready_calls; f->order[f->used++] = 'T'; return f->ready_ok;
}
static bool replay(void *arg)
{
    fixture_t *f = arg;
    ++f->replays; f->order[f->used++] = 'R'; return f->replay_ok;
}
static cdda_recovery_result_t run(fixture_t *f, const probe_sense_t *sense)
{
    const cdda_recovery_ops_t ops = {f, healthy, wait_for_device, ready, replay};
    return cdda_recovery_attempt(&f->state, sense, &ops);
}
static fixture_t good(void) { return (fixture_t){.wait_ok=true,.ready_ok=true,.replay_ok=true}; }

typedef struct {
    cd_player_core_t player;
    cd_player_read_t read, newer;
    cdda_recovery_t recovery;
    unsigned cancel_stage, action, ready_calls, replays;
} player_fixture_t;
static void control(player_fixture_t *f)
{
    switch (f->action) {
    case 0: cd_player_stop(&f->player); break;
    case 1:
        assert(cd_player_step(&f->player, 1));
        assert(cd_player_request(&f->player, &f->newer));
        break;
    case 2: cd_player_fault(&f->player); break;
    case 3: cd_player_lost(&f->player); break;
    case 4: assert(cd_player_pause(&f->player)); break;
    default: assert(false);
    }
}
static bool current(void *arg)
{
    player_fixture_t *f = arg;
    return cd_player_read_current(&f->player, &f->read);
}
static bool player_wait(void *arg, unsigned ms)
{
    player_fixture_t *f = arg;
    assert(ms == 1000);
    if (f->cancel_stage == 1) control(f);
    return true;
}
static bool player_ready(void *arg)
{
    player_fixture_t *f = arg;
    ++f->ready_calls;
    if (f->cancel_stage == 2) control(f);
    return true;
}
static bool player_replay(void *arg)
{
    player_fixture_t *f = arg;
    assert(current(f));
    ++f->replays;
    return true;
}
static void recovery_controls(void)
{
    uint8_t storage[16 * PROBE_CD_SECTOR_SIZE];
    const probe_toc_t toc = {.track_count=2, .tracks={
        {.number=1, .start_lba=0, .end_lba=100},
        {.number=2, .start_lba=100, .end_lba=200}}};
    const probe_sense_t seek = {3,2,0};
    for (unsigned action=0; action<5; ++action) {
        for (unsigned stage=0; stage<3; ++stage) {
            player_fixture_t f = {.action=action, .cancel_stage=stage};
            assert(cd_player_init(&f.player, storage, sizeof(storage), 8*PROBE_CD_SECTOR_SIZE));
            assert(cd_player_media(&f.player, &toc) && cd_player_play(&f.player));
            assert(cd_player_request(&f.player, &f.read) && current(&f));
            cd_player_read_t wrong = f.read;
            ++wrong.serial; assert(!cd_player_read_current(&f.player, &wrong));
            if (!stage) control(&f);
            const cdda_recovery_ops_t ops = {&f, current, player_wait, player_ready, player_replay};
            cdda_recovery_result_t result = cdda_recovery_attempt(&f.recovery, &seek, &ops);
            if (action == 4) { // Pause preserves the already pending logical read.
                assert(result == CDDA_RECOVERY_OK && f.replays == 1 && f.player.audio.state == AUDIO_PAUSED);
            } else {
                assert(result == (stage ? CDDA_RECOVERY_LOST : CDDA_RECOVERY_REJECTED));
                assert(f.replays == 0 && f.ready_calls == (stage == 2 ? 1u : 0u));
                assert(f.recovery.reserved == (stage ? 1u : 0u));
                assert(!cd_player_complete(&f.player, &f.read, false, NULL, 0));
                if (action == 1) assert(cd_player_read_current(&f.player, &f.newer));
                if (stage) {
                    // A new request does not refund a consumed recovery budget.
                    assert(cd_player_media(&f.player, &toc) && cd_player_play(&f.player));
                    assert(cd_player_request(&f.player, &f.read));
                    assert(cdda_recovery_attempt(&f.recovery, &seek, &ops) == CDDA_RECOVERY_REJECTED);
                }
            }
        }
    }
}
int main(void)
{
    const probe_sense_t seek = {3,2,0}, changed = {6,0x28,0};
    fixture_t f = good();
    assert(run(&f, NULL) == CDDA_RECOVERY_REJECTED && f.waits == 0);
    assert(run(&f, &changed) == CDDA_RECOVERY_REJECTED && f.state.reserved == 0);
    f.fail_check = 1;
    assert(run(&f, &seek) == CDDA_RECOVERY_REJECTED && f.state.reserved == 0);
    f = good(); f.wait_ok = false;
    assert(run(&f, &seek) == CDDA_RECOVERY_LOST && f.ready_calls == 0 && f.replays == 0);
    f.wait_ok = true; // Reconnect must not refund a reservation.
    assert(run(&f, &seek) == CDDA_RECOVERY_REJECTED && f.waits == 1);
    f = good(); f.fail_check = 2;
    assert(run(&f, &seek) == CDDA_RECOVERY_LOST && f.ready_calls == 0);
    f = good(); f.ready_ok = false;
    assert(run(&f, &seek) == CDDA_RECOVERY_NOT_READY && !strcmp(f.order,"WT") && f.replays == 0);
    f = good(); f.fail_check = 3;
    assert(run(&f, &seek) == CDDA_RECOVERY_LOST && f.ready_calls == 1 && f.replays == 0);
    f = good(); f.replay_ok = false;
    assert(run(&f, &seek) == CDDA_RECOVERY_FAILED && !strcmp(f.order,"WTR") && f.state.recovered == 0);
    f.replay_ok = true;
    assert(run(&f, &seek) == CDDA_RECOVERY_REJECTED && f.replays == 1);
    f = good();
    assert(run(&f, &seek) == CDDA_RECOVERY_OK && !strcmp(f.order,"WTR") && f.state.recovered == 1);
    assert(run(&f, &seek) == CDDA_RECOVERY_REJECTED && f.replays == 1);
    assert(cdda_recovery_attempt(&f.state, &seek, NULL) == CDDA_RECOVERY_REJECTED);
    recovery_controls();
    puts("PASS: shared recovery flow, serviced wait loss, TUR failure, late loss, single replay and reconnect budget (scripted, not hardware)");
    return 0;
}
