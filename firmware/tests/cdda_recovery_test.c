#include "cdda_recovery.h"
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
    puts("PASS: shared recovery flow, serviced wait loss, TUR failure, late loss, single replay and reconnect budget (scripted, not hardware)");
    return 0;
}
