#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    void *context;
    int64_t (*now_ms)(void *);
    void (*events)(void *, unsigned);
    bool (*owned)(void *);
    bool (*gone)(void *);
    void (*expired)(void *, bool disconnected, bool cancellable);
} transfer_wait_ops_t;
typedef enum { TRANSFER_WAIT_COMPLETE, TRANSFER_WAIT_TIMEOUT, TRANSFER_WAIT_DISCONNECTED } transfer_wait_result_t;
// The callback alone returns ownership. Expiry never fabricates completion or success.
// Events must service callbacks and allow monotonic time to advance while waiting.
transfer_wait_result_t transfer_wait(const transfer_wait_ops_t *ops, unsigned timeout_ms,
                                    unsigned drain_ms, bool cancellable);
