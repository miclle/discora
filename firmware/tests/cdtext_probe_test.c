// run_host_tests.py includes the actual USB client's CD-Text/TOC functions.
// Only transport, sense retrieval, logging and player publication are fakes.
#include "probe_protocol.h"
#include <assert.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#define CONFIG_DISCORA_CDTEXT_PROBE 1
#define CONFIG_DISCORA_CD_PLAYER 1
typedef enum { COMMAND_PASSED, COMMAND_FAILED, COMMAND_TRANSPORT_ERROR } command_result_t;
typedef struct { uint8_t data[PROBE_MAX_DATA]; size_t size; } command_data_t;
typedef enum { FULL, EMPTY, BAD_HEADER, OVERSIZED, SHORT_DATA, CHANGED_HEADER,
               FAILED, TRANSPORT, DISCONNECTED } scenario_t;
typedef struct {
    command_data_t result;
    probe_toc_t toc;
    bool toc_valid, faulted, gone;
    unsigned toc_attempts, toc_reads, text_reads, senses, fail_phase;
    scenario_t scenario;
    probe_sense_t sense;
    bool sense_failed;
} probe_context_t;
static const char *TAG = "test";
static unsigned published;
static void log_message(const char *tag, const char *format, ...) { (void)tag; (void)format; }
#define ESP_LOGI log_message
#define ESP_LOGW log_message
#define ESP_LOGE log_message

static void discora_cd_player_media(const probe_toc_t *toc)
{
    assert(toc->track_count == 1 && toc->tracks[0].number == 1);
    ++published;
}
static bool request_sense(probe_context_t *ctx, probe_sense_t *sense)
{
    ++ctx->senses;
    // Same shared reply buffer as the real transport: failure handling must not
    // subsequently interpret REQUEST SENSE bytes as CD-Text or the old TOC.
    memset(ctx->result.data, 0xa5, sizeof(ctx->result.data));
    if (ctx->sense_failed) { ctx->faulted = true; return false; }
    *sense = ctx->sense;
    return true;
}
static command_result_t execute_command(probe_context_t *ctx, probe_command_t command,
                                        size_t requested, const void *audio, command_data_t *result)
{
    assert(!audio);
    result->size = 0;
    if (command == PROBE_READ_TOC) {
        static const uint8_t toc[] = {0,18,1,1, 0,0x10,1,0,0,0,0,0, 0,0x10,0xaa,0,0,0,0,150};
        assert(requested == (++ctx->toc_reads == 1 ? 4 : sizeof(toc)));
        memcpy(result->data, toc, requested);
        result->size = requested;
        return COMMAND_PASSED;
    }
    assert(command == PROBE_READ_CDTEXT);
    unsigned phase = ++ctx->text_reads;
    assert(phase <= 2 && requested == (phase == 1 ? 4 : 22));
    if (phase == ctx->fail_phase) {
        if (ctx->scenario == FAILED) return COMMAND_FAILED;
        if (ctx->scenario == TRANSPORT) { ctx->faulted = true; return COMMAND_TRANSPORT_ERROR; }
        if (ctx->scenario == DISCONNECTED) ctx->gone = true;
    }
    memset(result->data, 0, requested);
    result->data[1] = ctx->scenario == EMPTY ? 2 : 20;
    result->size = requested;
    if (ctx->scenario == BAD_HEADER) result->data[1] = 3;
    if (ctx->scenario == OVERSIZED) result->data[0] = 0xff;
    if (phase == 2 && ctx->scenario == SHORT_DATA) result->size = 5;
    if (phase == 2 && ctx->scenario == CHANGED_HEADER) result->data[1] = 38;
    return COMMAND_PASSED;
}

#include "usb_cdtext_under_test.inc"

static void run(probe_context_t *ctx, bool available, unsigned reads, unsigned senses)
{
    published = 0;
    read_toc(ctx);
    assert(ctx->toc_attempts == 1 && ctx->toc_reads == 2);
    assert(ctx->toc_valid == available && published == (unsigned)available);
    assert(ctx->text_reads == reads && ctx->senses == senses);
}
int main(void)
{
    for (scenario_t s = FULL; s <= CHANGED_HEADER; ++s) {
        probe_context_t ctx = {.scenario = s};
        run(&ctx, true, s == EMPTY || s == BAD_HEADER || s == OVERSIZED ? 1 : 2, 0);
    }
    for (unsigned phase = 1; phase <= 2; ++phase) {
        // Optional unsupported command/field must still publish a valid TOC.
        probe_context_t ctx = {.scenario = FAILED, .fail_phase = phase, .sense = {5,0x24,0}};
        run(&ctx, true, phase, 1);
        const probe_sense_t invalidated[] = {{2,0x3a,0}, {2,4,1}, {6,0x28,0}, {6,0x29,0}};
        for (size_t i = 0; i < sizeof(invalidated) / sizeof(invalidated[0]); ++i) {
            ctx = (probe_context_t){.scenario = FAILED, .fail_phase = phase, .sense = invalidated[i]};
            run(&ctx, false, phase, 1); // Never publish stale media after sense is consumed.
            assert(!ctx.faulted); // A fresh TOC may be queried on the next poll.
        }
        ctx = (probe_context_t){.scenario = FAILED, .fail_phase = phase, .sense_failed = true};
        run(&ctx, false, phase, 1);
        ctx = (probe_context_t){.scenario = TRANSPORT, .fail_phase = phase};
        run(&ctx, false, phase, 0);
        ctx = (probe_context_t){.scenario = DISCONNECTED, .fail_phase = phase};
        run(&ctx, false, phase, 0);
    }
    puts("PASS: production CD-Text/TOC flow, bounded reads, metadata fallback, not-ready/change/loss blocks publication (fake transport)");
}
