// Execute the production speed/TOC flow with synthetic transport responses.
#include "probe_protocol.h"
#include <assert.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#define CONFIG_DISCORA_CD_READ_SPEED_TEST 1
#define CONFIG_DISCORA_CD_READ_SPEED_X 4
#define CONFIG_DISCORA_CD_PLAYER 1
typedef enum { COMMAND_PASSED, COMMAND_FAILED, COMMAND_TRANSPORT_ERROR } command_result_t;
typedef struct { uint8_t data[PROBE_MAX_DATA]; size_t size; } command_data_t;
typedef struct {
    command_data_t result;
    probe_toc_t toc;
    bool toc_valid, faulted, gone;
    unsigned toc_attempts, toc_reads, speed_calls, senses;
    command_result_t speed_result;
    probe_sense_t sense;
    bool sense_failed, disconnect_speed, disconnect_sense, malformed_toc;
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
    memset(ctx->result.data, 0xa5, sizeof(ctx->result.data));
    if (ctx->sense_failed) { ctx->faulted = true; return false; }
    if (ctx->disconnect_sense) ctx->gone = true;
    *sense = ctx->sense;
    return true;
}
static command_result_t execute_command(probe_context_t *ctx, probe_command_t command,
                                        size_t requested, const void *audio, command_data_t *result)
{
    assert(!audio && !published && !ctx->toc_valid);
    result->size = 0;
    if (command == PROBE_READ_TOC) {
        static const uint8_t toc[] = {0,18,1,1, 0,0x10,1,0,0,0,0,0, 0,0x10,0xaa,0,0,0,0,150};
        assert(requested == (++ctx->toc_reads == 1 ? 4 : sizeof(toc)));
        memcpy(result->data, toc, requested);
        result->size = requested;
        if (ctx->malformed_toc) result->data[1] = 0;
        return COMMAND_PASSED;
    }
    assert(command == PROBE_SET_CD_SPEED && requested == 0 && ctx->toc_reads == 2);
    assert(++ctx->speed_calls == 1);
    if (ctx->disconnect_speed) ctx->gone = true;
    if (ctx->speed_result == COMMAND_TRANSPORT_ERROR) ctx->faulted = true;
    return ctx->speed_result;
}

#include "usb_speed_under_test.inc"

static void run(probe_context_t ctx, bool available, unsigned calls, unsigned senses)
{
    published = 0;
    read_toc(&ctx);
    assert(ctx.toc_attempts == 1);
    assert(ctx.toc_valid == available && published == (unsigned)available);
    assert(ctx.speed_calls == calls && ctx.senses == senses);
}
int main(void)
{
    run((probe_context_t){0}, true, 1, 0);
    run((probe_context_t){.malformed_toc = true}, false, 0, 0);
    run((probe_context_t){.speed_result = COMMAND_TRANSPORT_ERROR}, false, 1, 0);
    run((probe_context_t){.disconnect_speed = true}, false, 1, 0);
    const probe_sense_t fallback[] = {{5,0x20,0}, {5,0x24,0}};
    for (size_t i = 0; i < sizeof(fallback) / sizeof(fallback[0]); ++i) {
        probe_context_t ctx = {.speed_result = COMMAND_FAILED, .sense = fallback[i]};
        run(ctx, true, 1, 1);
        ctx.disconnect_sense = true;
        run(ctx, false, 1, 1);
        ctx.disconnect_sense = false;
        ctx.sense_failed = true;
        run(ctx, false, 1, 1);
    }
    const probe_sense_t rejected[] = {{2,0x3a,0}, {2,4,1}, {6,0x28,0}, {6,0x29,0},
                                     {3,2,0}, {5,0x24,1}, {5,0x21,0}, {0,0,0}};
    for (size_t i = 0; i < sizeof(rejected) / sizeof(rejected[0]); ++i)
        run((probe_context_t){.speed_result = COMMAND_FAILED, .sense = rejected[i]}, false, 1, 1);
    puts("PASS: speed acceptance, unsupported fallback, source failure and TOC publication guards (synthetic)");
    return 0;
}
