#include "eject_button_core.h"
#include <assert.h>
#include <stdio.h>

static void release(eject_button_core_t *b, int64_t t)
{
    assert(!eject_button_sample(b, false, t));
    assert(!eject_button_sample(b, false, t + 30));
}
static bool press(eject_button_core_t *b, int64_t t)
{
    assert(!eject_button_sample(b, true, t));
    assert(!eject_button_sample(b, true, t + 29));
    return eject_button_sample(b, true, t + 30);
}
int main(void)
{
    eject_button_core_t b;
    eject_button_init(&b, 0);
    eject_button_enable(&b, true);
    assert(!eject_button_sample(&b, true, 5000)); // Held during boot.
    assert(!eject_button_take(&b));
    release(&b, 5010);
    assert(!eject_button_sample(&b, true, 5050));
    assert(!eject_button_sample(&b, false, 5060));
    assert(!eject_button_sample(&b, true, 5070));
    assert(!eject_button_sample(&b, true, 5099));
    assert(eject_button_sample(&b, true, 5100));
    eject_button_enable(&b, true); // USB readiness polling cannot erase a press.
    assert(eject_button_take(&b));
    assert(!eject_button_take(&b));
    assert(!eject_button_sample(&b, true, 20000)); // Long hold: no repeat.
    assert(!eject_button_sample(&b, false, 20010));
    assert(!eject_button_sample(&b, true, 20020));
    assert(!eject_button_sample(&b, true, 20100)); // Release bounce did not rearm.
    release(&b, 20200);
    assert(press(&b, 20300));
    release(&b, 20400);
    assert(!press(&b, 20500)); // Single-slot mailbox coalesces pending presses.
    eject_button_enable(&b, false); // Disconnect discards an already queued request.
    eject_button_enable(&b, true);
    assert(!eject_button_take(&b));
    assert(!eject_button_sample(&b, true, 21000)); // Reconnect while held: no replay.
    eject_button_enable(&b, false);
    release(&b, 21100);
    assert(!press(&b, 21200)); // Unidentified/faulted/busy: no deferred request.
    eject_button_enable(&b, true);
    assert(!eject_button_sample(&b, true, 21300));
    assert(!eject_button_take(&b));
    release(&b, 21400);
    assert(press(&b, 21500));
    assert(eject_button_take(&b));
    puts("PASS: eject debounce, boot-held, release bounce, long hold, coalescing, disconnect/busy discard (offline)");
}
