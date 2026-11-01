#include "cdda_recovery.h"
#include "cdda_retry.h"

cdda_recovery_result_t cdda_recovery_attempt(cdda_recovery_t *state,
    const probe_sense_t *sense, const cdda_recovery_ops_t *ops)
{
    if (!state || !ops || !ops->healthy || !ops->wait || !ops->ready || !ops->replay ||
        !cdda_retry_allowed(sense, state->reserved, true) || !ops->healthy(ops->context))
        return CDDA_RECOVERY_REJECTED;
    ++state->reserved; // Consume before waiting; loss or a failed TUR does not refund the budget.
    if (!ops->wait(ops->context, 1000) || !ops->healthy(ops->context)) return CDDA_RECOVERY_LOST;
    if (!ops->ready(ops->context)) return CDDA_RECOVERY_NOT_READY;
    if (!ops->healthy(ops->context)) return CDDA_RECOVERY_LOST;
    if (!ops->replay(ops->context)) return CDDA_RECOVERY_FAILED;
    ++state->recovered;
    return CDDA_RECOVERY_OK;
}
