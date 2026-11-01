#include "transfer_wait.h"

transfer_wait_result_t transfer_wait(const transfer_wait_ops_t *o, unsigned timeout_ms,
                                    unsigned drain_ms, bool cancellable)
{
    void *c = o->context;
    int64_t deadline = o->now_ms(c) + timeout_ms;
    while (o->owned(c) && !o->gone(c) && o->now_ms(c) < deadline) o->events(c, 20);
    if (o->owned(c)) {
        bool disconnected = o->gone(c);
        o->expired(c, disconnected, cancellable);
        deadline = o->now_ms(c) + drain_ms;
        while (o->owned(c) && o->now_ms(c) < deadline) o->events(c, 20);
        return disconnected ? TRANSFER_WAIT_DISCONNECTED : TRANSFER_WAIT_TIMEOUT;
    }
    return o->gone(c) ? TRANSFER_WAIT_DISCONNECTED : TRANSFER_WAIT_COMPLETE;
}
