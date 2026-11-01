#pragma once
#include "probe_protocol.h"

typedef struct { unsigned reserved, recovered; } cdda_recovery_t;
typedef struct {
    void *context;
    bool (*healthy)(void *context);
    bool (*wait)(void *context, unsigned ms);
    bool (*ready)(void *context);
    bool (*replay)(void *context);
} cdda_recovery_ops_t;
typedef enum {
    CDDA_RECOVERY_REJECTED, CDDA_RECOVERY_LOST, CDDA_RECOVERY_NOT_READY,
    CDDA_RECOVERY_FAILED, CDDA_RECOVERY_OK,
} cdda_recovery_result_t;
// The caller owns state for the entire boot, including reconnects. All callbacks are synchronous.
cdda_recovery_result_t cdda_recovery_attempt(cdda_recovery_t *state,
    const probe_sense_t *sense, const cdda_recovery_ops_t *ops);
