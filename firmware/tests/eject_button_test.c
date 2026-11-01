#include "button_core.h"
#include <assert.h>
#include <stdio.h>

static void release(button_core_t *b, int64_t t)
{
    assert(!button_sample(b, false, t));
    assert(!button_sample(b, false, t + 30));
}
static bool press(button_core_t *b, int64_t t)
{
    assert(!button_sample(b, true, t));
    assert(!button_sample(b, true, t + 29));
    return button_sample(b, true, t + 30);
}
int main(void)
{
    button_core_t b;
    button_init(&b, 0);
    button_enable(&b, true);
    assert(!button_sample(&b, true, 5000)); // Held during boot.
    assert(!button_take(&b));
    release(&b, 5010);
    assert(!button_sample(&b, true, 5050));
    assert(!button_sample(&b, false, 5060));
    assert(!button_sample(&b, true, 5070));
    assert(!button_sample(&b, true, 5099));
    assert(button_sample(&b, true, 5100));
    button_enable(&b, true); // USB readiness polling cannot erase a press.
    assert(button_take(&b));
    assert(!button_take(&b));
    assert(!button_sample(&b, true, 20000)); // Long hold: no repeat.
    assert(!button_sample(&b, false, 20010));
    assert(!button_sample(&b, true, 20020));
    assert(!button_sample(&b, true, 20100)); // Release bounce did not rearm.
    release(&b, 20200);
    assert(press(&b, 20300));
    release(&b, 20400);
    assert(!press(&b, 20500)); // Single-slot mailbox coalesces pending presses.
    button_enable(&b, false); // Disconnect discards an already queued request.
    button_enable(&b, true);
    assert(!button_take(&b));
    assert(!button_sample(&b, true, 21000)); // Reconnect while held: no replay.
    button_enable(&b, false);
    release(&b, 21100);
    assert(!press(&b, 21200)); // Unidentified/faulted/busy: no deferred request.
    button_enable(&b, true);
    assert(!button_sample(&b, true, 21300));
    assert(!button_take(&b));
    release(&b, 21400);
    assert(press(&b, 21500));
    assert(button_take(&b));
    puts("PASS: eject debounce, boot-held, release bounce, long hold, coalescing, disconnect/busy discard (offline)");
}
