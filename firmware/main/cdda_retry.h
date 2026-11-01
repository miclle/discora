#pragma once
#include "probe_protocol.h"

// A missing/invalid sense is represented by NULL. Budget survives reconnects.
static inline bool cdda_retry_allowed(const probe_sense_t *sense,
                                      unsigned reservations, bool healthy)
{
    return healthy && reservations == 0 && sense &&
           sense->key == 3 && sense->asc == 2 && sense->ascq == 0;
}
