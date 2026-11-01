#include "usb_probe.h"

#include <inttypes.h>
#include <string.h>

#include "esp_app_desc.h"
#include "esp_err.h"
#include "esp_intr_alloc.h"
#include "esp_log.h"
#include "esp_system.h"
#include "sdkconfig.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/sha256.h"
#include "usb/usb_host.h"

#include "probe_protocol.h"
#include "cdda_recovery.h"
#include "cdda_bench.h"
#include "cd_player.h"
#include "transfer_wait.h"

#if CONFIG_ESP_CONSOLE_USB_CDC || CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG || CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG
#error "Discora Host requires an independent UART console; disable both primary and secondary USB consoles in menuconfig"
#endif

#if defined(CONFIG_DISCORA_CDDA_PROBE)
enum { CDDA_PROBE_ENABLED = 1 };
#else
enum { CDDA_PROBE_ENABLED = 0 };
#endif

enum { TRANSFER_TIMEOUT_MS = 3000, AUDIO_DATA_TIMEOUT_MS = 30000, CANCEL_TIMEOUT_MS = 2000, POLL_INTERVAL_MS = 5000 };
#if defined(CONFIG_DISCORA_SENSE_DATA_TIMEOUT_MS)
enum { SENSE_DATA_TIMEOUT_MS = CONFIG_DISCORA_SENSE_DATA_TIMEOUT_MS };
#else
enum { SENSE_DATA_TIMEOUT_MS = TRANSFER_TIMEOUT_MS };
#endif
static const char *TAG = "usb_probe";

typedef struct {
    uint8_t data[PROBE_MAX_DATA];
    size_t size;
} command_data_t;

typedef struct {
    const probe_track_t *track;
    uint32_t lba;
    uint8_t sectors;
} audio_read_t;

typedef struct {
    usb_host_client_handle_t client;
    usb_device_handle_t device;
    usb_transfer_t *transfer;
    probe_interface_t interface;
    bool pending[128];
    bool claimed;
    bool gone;
    bool in_flight;
    bool faulted;
    bool identified;
    bool toc_valid;
    bool audio_attempted;
    bool quiet_audio;
    unsigned read_failures;
    cdda_recovery_t recovery; // One budget per MCU boot; never reset on reconnect.
    size_t audio_resume_index;
    uint32_t audio_resume_lba;
    command_data_t result; // One shared reply buffer; only the serialized client owns it.
    unsigned toc_attempts;
    probe_toc_t toc;
    uint32_t tag;
    int64_t next_poll;
} probe_context_t;

typedef enum { COMMAND_PASSED, COMMAND_FAILED, COMMAND_TRANSPORT_ERROR } command_result_t;

static int64_t now_ms(void)
{
    return esp_timer_get_time() / 1000;
}

static void handle_events(probe_context_t *ctx, unsigned wait_ms)
{
    esp_err_t err = usb_host_client_handle_events(ctx->client, pdMS_TO_TICKS(wait_ms));
    if (err != ESP_OK && err != ESP_ERR_TIMEOUT) {
        ESP_LOGE(TAG, "client events: %s", esp_err_to_name(err));
        ctx->faulted = true;
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

static void client_event(const usb_host_client_event_msg_t *event, void *arg)
{
    probe_context_t *ctx = arg;
    if (event->event == USB_HOST_CLIENT_EVENT_NEW_DEV && event->new_dev.address < 128) {
        ctx->pending[event->new_dev.address] = true;
    } else if (event->event == USB_HOST_CLIENT_EVENT_DEV_GONE &&
               event->dev_gone.dev_hdl == ctx->device) {
        ctx->gone = true;
    }
}

static void transfer_done(usb_transfer_t *transfer)
{
    probe_context_t *ctx = transfer->context;
    ctx->in_flight = false;
}

static void log_usb_error(const char *operation, esp_err_t err)
{
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "%s: %s", operation, esp_err_to_name(err));
    }
}

static int64_t wait_now(void *arg) { (void)arg; return now_ms(); }
static void wait_events(void *arg, unsigned ms) { handle_events(arg, ms); }
static bool wait_owned(void *arg) { return ((probe_context_t *)arg)->in_flight; }
static bool wait_gone(void *arg) { return ((probe_context_t *)arg)->gone; }
static void wait_expired(void *arg, bool disconnected, bool cancellable)
{
    probe_context_t *ctx = arg;
    ESP_LOGW(TAG, "transfer %s ep=0x%02x; cancel and drain before reuse",
             disconnected ? "disconnected" : "deadline exceeded", ctx->transfer->bEndpointAddress);
    // EP0 cannot be cancelled by the IDF Host API. Never fabricate ownership return.
    if (cancellable) {
        log_usb_error("cancel halt", usb_host_endpoint_halt(ctx->device, ctx->transfer->bEndpointAddress));
        log_usb_error("cancel flush", usb_host_endpoint_flush(ctx->device, ctx->transfer->bEndpointAddress));
    }
}
static esp_err_t wait_transfer(probe_context_t *ctx, unsigned timeout_ms)
{
    const transfer_wait_ops_t ops = {ctx, wait_now, wait_events, wait_owned, wait_gone, wait_expired};
    transfer_wait_result_t result = transfer_wait(&ops, timeout_ms, CANCEL_TIMEOUT_MS,
                                                  ctx->transfer->bEndpointAddress != 0);
    if (result != TRANSFER_WAIT_COMPLETE) {
        if (ctx->in_flight) ESP_LOGE(TAG, "transfer still owned by USB stack; probe quarantined, unplug device");
        return result == TRANSFER_WAIT_DISCONNECTED ? ESP_ERR_INVALID_STATE : ESP_ERR_TIMEOUT;
    }
    if (ctx->transfer->status != USB_TRANSFER_STATUS_COMPLETED) {
        ESP_LOGW(TAG, "USB status=%d ep=0x%02x actual=%d",
                 ctx->transfer->status, ctx->transfer->bEndpointAddress,
                 ctx->transfer->actual_num_bytes);
        return ESP_FAIL;
    }
    return ESP_OK;
}

static esp_err_t submit_transfer(probe_context_t *ctx, bool control, unsigned timeout_ms)
{
    if (ctx->gone || ctx->in_flight) {
        return ESP_ERR_INVALID_STATE;
    }
    ctx->transfer->device_handle = ctx->device;
    ctx->transfer->callback = transfer_done;
    ctx->transfer->context = ctx;
    ctx->transfer->flags = 0; // BOT forbids a terminating OUT ZLP.
    ctx->in_flight = true;
    esp_err_t err = control ? usb_host_transfer_submit_control(ctx->client, ctx->transfer) :
                             usb_host_transfer_submit(ctx->transfer);
    if (err != ESP_OK) {
        ctx->in_flight = false;
        return err;
    }
    return wait_transfer(ctx, timeout_ms);
}

static esp_err_t bulk_transfer(probe_context_t *ctx, bool in, const uint8_t *out, size_t size,
                                unsigned timeout_ms)
{
    if (ctx->in_flight || ctx->gone) {
        return ESP_ERR_INVALID_STATE;
    }
    usb_transfer_t *t = ctx->transfer;
    size_t rounded = in ? ((size + ctx->interface.mps_in - 1) / ctx->interface.mps_in) *
                         ctx->interface.mps_in : size;
    if (rounded > t->data_buffer_size) {
        return ESP_ERR_INVALID_SIZE;
    }
    memset(t->data_buffer, 0, t->data_buffer_size);
    if (!in) {
        memcpy(t->data_buffer, out, size);
    }
    t->bEndpointAddress = in ? ctx->interface.ep_in : ctx->interface.ep_out;
    // IDF requires bulk IN lengths rounded to MPS. CBW/CDB retain the exact wire lengths.
    t->num_bytes = (int)rounded;
    return submit_transfer(ctx, false, timeout_ms);
}

static esp_err_t control_request(probe_context_t *ctx, uint8_t type, uint8_t request, uint16_t index)
{
    if (ctx->in_flight || ctx->gone) {
        return ESP_ERR_INVALID_STATE;
    }
    usb_transfer_t *t = ctx->transfer;
    memset(t->data_buffer, 0, t->data_buffer_size);
    t->data_buffer[0] = type;
    t->data_buffer[1] = request;
    t->data_buffer[4] = (uint8_t)index;
    t->data_buffer[5] = (uint8_t)(index >> 8);
    t->bEndpointAddress = 0;
    t->num_bytes = 8;
    return submit_transfer(ctx, true, TRANSFER_TIMEOUT_MS);
}

static esp_err_t clear_halt(probe_context_t *ctx, uint8_t endpoint)
{
    // CLEAR_FEATURE clears the device's halt/toggle; endpoint_clear only clears the host pipe.
    esp_err_t err = usb_host_endpoint_halt(ctx->device, endpoint);
    if (err != ESP_OK) {
        return err;
    }
    err = control_request(ctx, 0x02, 0x01, endpoint);
    if (err != ESP_OK) {
        return err;
    }
    return usb_host_endpoint_clear(ctx->device, endpoint);
}

static void reset_recovery(probe_context_t *ctx)
{
    if (ctx->gone || ctx->in_flight) {
        return;
    }
    ESP_LOGW(TAG, "BOT reset recovery (one attempt, no command replay)");
    esp_err_t err = control_request(ctx, 0x21, 0xff, ctx->interface.number);
    if (err == ESP_OK) {
        err = clear_halt(ctx, ctx->interface.ep_in);
    }
    if (err == ESP_OK) {
        err = clear_halt(ctx, ctx->interface.ep_out);
    }
    ESP_LOGW(TAG, "BOT recovery=%s; command probing stopped until reconnect", esp_err_to_name(err));
}

static command_result_t execute_command(probe_context_t *ctx, probe_command_t command,
                                         size_t requested, const audio_read_t *audio, command_data_t *result)
{
    uint8_t cbw[PROBE_CBW_SIZE];
    size_t received = 0;
    int64_t started = now_ms();
    result->size = 0;
    ++ctx->tag;
    bool valid = requested <= sizeof(result->data);
    if (command == PROBE_READ_CD) {
        valid = valid && audio && requested == (size_t)audio->sectors * PROBE_CD_SECTOR_SIZE &&
                probe_make_read_cd_cbw(ctx->interface.subclass, ctx->tag, audio->track,
                                       audio->lba, audio->sectors, cbw);
    } else {
        valid = valid && !audio &&
                probe_make_cbw(command, ctx->interface.subclass, ctx->tag, requested, cbw);
    }
    if (!valid) {
        ctx->faulted = true;
        return COMMAND_TRANSPORT_ERROR;
    }
    if (!ctx->quiet_audio || command != PROBE_READ_CD) ESP_LOGI(TAG, "command=%s tag=%" PRIu32 " requested=%u LUN=0",
             probe_command_name(command), ctx->tag, (unsigned)requested);
    esp_err_t err = bulk_transfer(ctx, false, cbw, sizeof(cbw), TRANSFER_TIMEOUT_MS);
    if (command == PROBE_REQUEST_SENSE) {
        ESP_LOGI(TAG, "sense phase=CBW result=%s elapsed_ms=%" PRIi64 " owned=%u",
                 esp_err_to_name(err), now_ms() - started, ctx->in_flight);
    }
    if (err != ESP_OK || ctx->transfer->actual_num_bytes != PROBE_CBW_SIZE) {
        goto transport_error;
    }
    if (requested) {
        unsigned data_timeout = command == PROBE_READ_CD ? AUDIO_DATA_TIMEOUT_MS :
                                command == PROBE_REQUEST_SENSE ? SENSE_DATA_TIMEOUT_MS : TRANSFER_TIMEOUT_MS;
        if (command == PROBE_REQUEST_SENSE) ESP_LOGI(TAG, "sense phase=DATA deadline_ms=%u", data_timeout);
        err = bulk_transfer(ctx, true, NULL, requested,
                            data_timeout);
        if (command == PROBE_REQUEST_SENSE) {
            ESP_LOGI(TAG, "sense phase=DATA result=%s elapsed_ms=%" PRIi64 " owned=%u",
                     esp_err_to_name(err), now_ms() - started, ctx->in_flight);
        }
        if (err != ESP_OK && !(err == ESP_FAIL && ctx->transfer->status == USB_TRANSFER_STATUS_STALL)) {
            goto transport_error;
        }
        int actual = ctx->transfer->actual_num_bytes;
        if (actual < 0 || (size_t)actual > requested) {
            err = ESP_ERR_INVALID_SIZE;
            goto transport_error;
        }
        received = (size_t)actual;
        memcpy(result->data, ctx->transfer->data_buffer, received);
        if (err != ESP_OK) {
            // A Data-In STALL does not imply command failure until CSW is obtained.
            err = clear_halt(ctx, ctx->interface.ep_in);
            if (err != ESP_OK) {
                goto transport_error;
            }
        }
    }
    err = bulk_transfer(ctx, true, NULL, PROBE_CSW_SIZE, TRANSFER_TIMEOUT_MS);
    if (command == PROBE_REQUEST_SENSE) {
        ESP_LOGI(TAG, "sense phase=CSW result=%s elapsed_ms=%" PRIi64,
                 esp_err_to_name(err), now_ms() - started);
    }
    if (err == ESP_FAIL && ctx->transfer->status == USB_TRANSFER_STATUS_STALL) {
        err = clear_halt(ctx, ctx->interface.ep_in);
        if (err == ESP_OK) {
            err = bulk_transfer(ctx, true, NULL, PROBE_CSW_SIZE, TRANSFER_TIMEOUT_MS);
        }
    }
    if (err != ESP_OK) {
        goto transport_error;
    }
    if (ctx->transfer->actual_num_bytes < 0 ||
        (size_t)ctx->transfer->actual_num_bytes > ctx->transfer->data_buffer_size) {
        err = ESP_ERR_INVALID_SIZE;
        goto transport_error;
    }
    probe_csw_t csw;
    if (!probe_parse_csw(ctx->transfer->data_buffer, ctx->transfer->actual_num_bytes,
                         ctx->tag, requested, received, &csw)) {
        ESP_LOGE(TAG, "invalid CSW / phase error (length, signature, tag, residue or status)");
        ESP_LOG_BUFFER_HEX_LEVEL(TAG, ctx->transfer->data_buffer,
                                 ctx->transfer->actual_num_bytes, ESP_LOG_WARN);
        err = ESP_ERR_INVALID_RESPONSE;
        goto transport_error;
    }
    result->size = csw.relevant_size;
    if (!ctx->quiet_audio || command != PROBE_READ_CD || csw.status != 0) ESP_LOGI(TAG, "command=%s CSW=%u received=%u residue=%" PRIu32 " elapsed_ms=%" PRIi64,
             probe_command_name(command), csw.status, (unsigned)received, csw.residue,
             now_ms() - started);
    if (result->size && command != PROBE_READ_CD) {
        ESP_LOG_BUFFER_HEX_LEVEL(TAG, result->data, result->size, ESP_LOG_INFO);
    }
    return csw.status == 0 ? COMMAND_PASSED : COMMAND_FAILED;

transport_error:
    ESP_LOGE(TAG, "command=%s transport error=%s elapsed_ms=%" PRIi64,
             probe_command_name(command), esp_err_to_name(err == ESP_OK ? ESP_FAIL : err),
             now_ms() - started);
    ctx->faulted = true;
    reset_recovery(ctx);
    return COMMAND_TRANSPORT_ERROR;
}

static bool request_sense(probe_context_t *ctx, probe_sense_t *sense)
{
    command_data_t *result = &ctx->result;
    if (execute_command(ctx, PROBE_REQUEST_SENSE, probe_data_size(PROBE_REQUEST_SENSE), NULL, result) != COMMAND_PASSED ||
        !probe_parse_sense(result->data, result->size, sense)) {
        ESP_LOGE(TAG, "REQUEST SENSE failed or malformed; no readiness conclusion");
        ctx->faulted = true;
        return false;
    }
    ESP_LOGI(TAG, "sense key=0x%02x ASC=0x%02x ASCQ=0x%02x", sense->key, sense->asc, sense->ascq);
    if (sense->key == 2 && sense->asc == 0x3a) {
        ESP_LOGI(TAG, "medium not present (valid device response)");
    }
    return true;
}

static void identify_drive(probe_context_t *ctx)
{
    for (unsigned attempt = 1; attempt <= 3 && !ctx->gone; ++attempt) {
        command_data_t *result = &ctx->result;
        command_result_t status = execute_command(ctx, PROBE_INQUIRY, probe_data_size(PROBE_INQUIRY), NULL, result);
        if (status == COMMAND_TRANSPORT_ERROR) {
            return;
        }
        if (status == COMMAND_PASSED) {
            probe_inquiry_t identity;
            if (!probe_parse_inquiry(result->data, result->size, &identity)) {
                ESP_LOGE(TAG, "short/malformed standard INQUIRY; stop probing");
                break;
            }
            ESP_LOGI(TAG, "INQUIRY vendor=[%s] product=[%s] revision=[%s] PDT=0x%02x qualifier=%u",
                     identity.vendor, identity.product, identity.revision,
                     identity.peripheral_type, identity.qualifier);
            if (identity.peripheral_type != 5 || identity.qualifier != 0) {
                ESP_LOGW(TAG, "LUN 0 is not an available CD/DVD device; stop probing");
                break;
            }
            ctx->identified = true;
            return;
        }
        probe_sense_t sense;
        if (!request_sense(ctx, &sense) || (sense.key != 2 && sense.key != 6)) {
            break;
        }
        ESP_LOGW(TAG, "INQUIRY transient sense; attempt=%u/3", attempt);
        int64_t deadline = now_ms() + 500;
        while (!ctx->gone && now_ms() < deadline) {
            handle_events(ctx, 20);
        }
    }
    ctx->faulted = true;
    ESP_LOGW(TAG, "identity not confirmed; reconnect to run a new probe");
}

static void read_toc(probe_context_t *ctx)
{
    command_data_t *result = &ctx->result;
    ++ctx->toc_attempts;
    ESP_LOGI(TAG, "TOC attempt=%u/3 format=0 MSF=0", ctx->toc_attempts);
    command_result_t status = execute_command(ctx, PROBE_READ_TOC, PROBE_TOC_HEADER_SIZE, NULL, result);
    if (status != COMMAND_PASSED) {
        if (status == COMMAND_FAILED) {
            probe_sense_t sense;
            request_sense(ctx, &sense);
        }
        return;
    }
    size_t total_size;
    if (!probe_toc_size_from_header(result->data, result->size, &total_size)) {
        ESP_LOGE(TAG, "invalid TOC header; no track metadata published");
        return;
    }
    uint8_t header[PROBE_TOC_HEADER_SIZE];
    memcpy(header, result->data, sizeof(header));
    ESP_LOGI(TAG, "TOC header first=%u last=%u total_bytes=%u", header[2], header[3], (unsigned)total_size);
    status = execute_command(ctx, PROBE_READ_TOC, total_size, NULL, result);
    if (status != COMMAND_PASSED) {
        if (status == COMMAND_FAILED) {
            probe_sense_t sense;
            request_sense(ctx, &sense);
        }
        return;
    }
    if (result->size < sizeof(header) || memcmp(header, result->data, sizeof(header)) != 0 ||
        !probe_parse_toc(result->data, result->size, &ctx->toc)) {
        ESP_LOGE(TAG, "TOC truncated, changed or malformed; no track metadata published");
        return;
    }
    ctx->toc_valid = true;
#if defined(CONFIG_DISCORA_CD_PLAYER)
    discora_cd_player_media(&ctx->toc);
#endif
    ESP_LOGI(TAG, "TOC validated first=%u last=%u tracks=%u audio=%u data=%u lead_out_lba=%" PRIu32,
             ctx->toc.first_track, ctx->toc.last_track, ctx->toc.track_count,
             ctx->toc.audio_tracks, ctx->toc.data_tracks, ctx->toc.lead_out_lba);
    for (size_t i = 0; i < ctx->toc.track_count; ++i) {
        const probe_track_t *track = &ctx->toc.tracks[i];
        uint32_t sectors = track->end_lba - track->start_lba;
        ESP_LOGI(TAG, "TOC track=%u type=%s start_lba=%" PRIu32 " end_lba=%" PRIu32
                 " sectors=%" PRIu32 " duration=%02" PRIu32 ":%02" PRIu32 ":%02" PRIu32 " control=0x%02x",
                 track->number, track->control & 0x04 ? "data" : "audio",
                 track->start_lba, track->end_lba, sectors,
                 sectors / (75 * 60), sectors / 75 % 60, sectors % 75, track->control);
    }
    ESP_LOGI(TAG, "TOC metadata only; PCM audio not read");
}

#if defined(CONFIG_DISCORA_CDDA_SEEK_RECOVERY)
typedef struct { probe_context_t *ctx; audio_read_t audio; size_t expected; } recovery_call_t;
static bool recovery_healthy(void *arg)
{
    probe_context_t *ctx = ((recovery_call_t *)arg)->ctx;
    return !ctx->gone && !ctx->faulted && !ctx->in_flight && ctx->toc_valid;
}
static bool recovery_wait(void *arg, unsigned ms)
{
    recovery_call_t *call = arg;
    probe_context_t *ctx = call->ctx;
    ESP_LOGW(TAG, "seek recovery reserved=%u/1 lba=%" PRIu32 " wait_ms=%u; original failure retained",
             ctx->recovery.reserved, call->audio.lba, ms);
    int64_t until = now_ms() + ms;
    while (recovery_healthy(arg) && now_ms() < until) handle_events(ctx, 20);
    return recovery_healthy(arg);
}
static bool recovery_ready(void *arg)
{
    probe_context_t *ctx = ((recovery_call_t *)arg)->ctx;
    bool ok = execute_command(ctx, PROBE_TEST_UNIT_READY, 0, NULL, &ctx->result) == COMMAND_PASSED;
    if (!ok) ctx->toc_valid = false;
    return ok;
}
static bool recovery_replay(void *arg)
{
    recovery_call_t *call = arg;
    probe_context_t *ctx = call->ctx;
    ESP_LOGW(TAG, "seek recovery replay=1/1 track=%u lba=%" PRIu32 " sectors=%u",
             call->audio.track->number, call->audio.lba, call->audio.sectors);
    command_result_t status = execute_command(ctx, PROBE_READ_CD, call->expected, &call->audio, &ctx->result);
    if (status == COMMAND_PASSED && ctx->result.size == call->expected) return true;
    ++ctx->read_failures;
    if (status == COMMAND_FAILED) { probe_sense_t sense; request_sense(ctx, &sense); }
    return false;
}
#endif

static bool read_audio(probe_context_t *ctx, const probe_track_t *track,
                       uint32_t lba, uint8_t sectors)
{
    audio_read_t audio = {.track = track, .lba = lba, .sectors = sectors};
    size_t expected = (size_t)sectors * PROBE_CD_SECTOR_SIZE;
    if (!ctx->quiet_audio) ESP_LOGI(TAG, "CDDA read track=%u lba=%" PRIu32 " sectors=%u bytes=%u",
             track->number, lba, sectors, (unsigned)expected);
    command_result_t status = execute_command(ctx, PROBE_READ_CD, expected, &audio, &ctx->result);
    if (status != COMMAND_PASSED) {
        ++ctx->read_failures;
        ESP_LOGW(TAG, "CDDA first failure track=%u lba=%" PRIu32 " sectors=%u result=%d failures=%u",
                 track->number, lba, sectors, status, ctx->read_failures);
        probe_sense_t sense = {0};
        bool sense_ok = status == COMMAND_FAILED && request_sense(ctx, &sense);
#if defined(CONFIG_DISCORA_CDDA_SEEK_RECOVERY)
        recovery_call_t call = {.ctx = ctx, .audio = audio, .expected = expected};
        const cdda_recovery_ops_t ops = {.context = &call, .healthy = recovery_healthy,
            .wait = recovery_wait, .ready = recovery_ready, .replay = recovery_replay};
        cdda_recovery_result_t recovered = cdda_recovery_attempt(&ctx->recovery, sense_ok ? &sense : NULL, &ops);
        if (recovered == CDDA_RECOVERY_OK) {
            ESP_LOGW(TAG, "seek recovery succeeded; recovered read, not a clean first attempt");
            return true;
        }
        if (recovered == CDDA_RECOVERY_LOST) ESP_LOGW(TAG, "seek recovery aborted: device lost/faulted; no replay");
        if (recovered == CDDA_RECOVERY_NOT_READY) ESP_LOGW(TAG, "seek recovery aborted: not ready; TOC invalidated, no replay");
        if (recovered == CDDA_RECOVERY_FAILED) ESP_LOGW(TAG, "seek recovery failed; budget exhausted");
#else
        (void)sense_ok;
#endif
        ESP_LOGW(TAG, "CDDA probe stopped; no further read retry");
        return false;
    }
    if (ctx->result.size != expected) {
        ESP_LOGE(TAG, "CDDA incomplete reply expected=%u relevant=%u; probe stopped",
                 (unsigned)expected, (unsigned)ctx->result.size);
        return false;
    }
    return true;
}

static bool audio_digest(probe_context_t *ctx, size_t size, uint8_t digest[32])
{
    if (mbedtls_sha256(ctx->result.data, size, digest, 0) != 0) {
        ESP_LOGE(TAG, "CDDA SHA256 failed; probe stopped");
        return false;
    }
    return true;
}

static void log_audio_digest(const char *name, const uint8_t digest[32])
{
    static const char hex[] = "0123456789abcdef";
    char text[65];
    for (size_t i = 0; i < 32; ++i) {
        text[2 * i] = hex[digest[i] >> 4];
        text[2 * i + 1] = hex[digest[i] & 15];
    }
    text[64] = '\0';
    ESP_LOGI(TAG, "CDDA %s SHA256=%s", name, text);
}

static bool probe_audio(probe_context_t *ctx)
{
    // One bounded attempt per MCU boot. Re-enumeration must never re-arm a failed read.
    ctx->audio_attempted = true;
    const probe_track_t *track = NULL;
    for (size_t i = 0; i < ctx->toc.track_count; ++i) {
        const probe_track_t *candidate = &ctx->toc.tracks[i];
        if (!(candidate->control & 0x0c) &&
            candidate->end_lba - candidate->start_lba >= PROBE_MAX_READ_SECTORS) {
            track = candidate;
            break;
        }
    }
    if (!track) {
        ESP_LOGW(TAG, "CDDA probe skipped: no suitable two-channel audio track");
        return false;
    }
    uint32_t lba = track->start_lba;
    if (track->end_lba - lba >= 150 + PROBE_MAX_READ_SECTORS) {
        lba += 150; // Avoid the initial two seconds of silence when the track is long enough.
    }
    ESP_LOGI(TAG, "CDDA bounded probe start control=0x%02x; PCM bytes never logged", track->control);
    uint8_t single[32], first[32], chunk[32], repeated[32];
    if (!read_audio(ctx, track, lba, 1) ||
        !audio_digest(ctx, PROBE_CD_SECTOR_SIZE, single)) {
        return false;
    }
    log_audio_digest("single-sector", single);
    if (!read_audio(ctx, track, lba, PROBE_MAX_READ_SECTORS) ||
        !audio_digest(ctx, PROBE_CD_SECTOR_SIZE, first) ||
        !audio_digest(ctx, ctx->result.size, chunk)) {
        return false;
    }
    if (memcmp(single, first, sizeof(single)) != 0) {
        ESP_LOGE(TAG, "CDDA single-vs-batch mismatch; stop before burst test");
        return false;
    }
    if (!read_audio(ctx, track, lba, PROBE_MAX_READ_SECTORS) ||
        !audio_digest(ctx, ctx->result.size, repeated)) {
        return false;
    }
    log_audio_digest("eight-sector", chunk);
    if (memcmp(chunk, repeated, sizeof(chunk)) != 0) {
        ESP_LOGE(TAG, "CDDA repeat mismatch; stop before burst test");
        return false;
    }
    ESP_LOGI(TAG, "CDDA single-vs-batch=match repeated-eight=match (not independent reference validation)");

    uint32_t next_lba = lba + PROBE_MAX_READ_SECTORS;
    unsigned batches = (track->end_lba - next_lba) / PROBE_MAX_READ_SECTORS;
    if (batches > 32) {
        batches = 32;
    }
    if (!batches) {
        ESP_LOGI(TAG, "CDDA burst skipped: insufficient remaining track sectors");
        return false;
    }
    size_t bytes = 0, nonzero = 0;
    int64_t started = esp_timer_get_time(), longest_us = 0;
    for (unsigned i = 0; i < batches; ++i) {
        int64_t command_started = esp_timer_get_time();
        if (!read_audio(ctx, track, next_lba, PROBE_MAX_READ_SECTORS)) {
            ESP_LOGW(TAG, "CDDA burst incomplete completed_batches=%u/%u", i, batches);
            return false;
        }
        int64_t elapsed = esp_timer_get_time() - command_started;
        if (elapsed > longest_us) {
            longest_us = elapsed;
        }
        for (size_t j = 0; j < ctx->result.size; ++j) {
            nonzero += ctx->result.data[j] != 0;
        }
        bytes += ctx->result.size;
        next_lba += PROBE_MAX_READ_SECTORS;
    }
    int64_t elapsed_us = esp_timer_get_time() - started;
    ESP_LOGI(TAG, "CDDA burst complete start_lba=%" PRIu32 " end_lba=%" PRIu32
             " batches=%u sectors=%u bytes=%u nonzero_bytes=%u elapsed_us=%" PRIi64
             " bytes_per_sec=%" PRIi64 " longest_read_us=%" PRIi64,
             lba + PROBE_MAX_READ_SECTORS, next_lba, batches, batches * PROBE_MAX_READ_SECTORS,
             (unsigned)bytes, (unsigned)nonzero, elapsed_us,
             elapsed_us > 0 ? (int64_t)bytes * 1000000 / elapsed_us : 0, longest_us);
    ESP_LOGI(TAG, "CDDA bounded probe complete; short burst includes logging, no PCM/reference/I2S qualification");
    ESP_LOGI(TAG, "main task stack minimum free=%u bytes", (unsigned)uxTaskGetStackHighWaterMark(NULL));
    ctx->audio_resume_index = (size_t)(track - ctx->toc.tracks);
    ctx->audio_resume_lba = next_lba;
    return true;
}

#if defined(CONFIG_DISCORA_CDDA_SOAK)
static bool bench_read(void *arg, const probe_track_t *track, uint32_t lba,
                        uint8_t sectors, const uint8_t **data, size_t *size)
{
    probe_context_t *ctx = arg;
    if (!read_audio(ctx, track, lba, sectors)) return false;
    *data = ctx->result.data;
    *size = ctx->result.size;
    return true;
}

static bool bench_service(void *arg, unsigned wait_ms)
{
    probe_context_t *ctx = arg;
    handle_events(ctx, wait_ms);
    // IDF defaults to 10 ms ticks: a 5 ms wait rounds to zero, so yield at least one tick.
    if (wait_ms && pdMS_TO_TICKS(wait_ms) == 0) vTaskDelay(1);
    return !ctx->gone && !ctx->faulted;
}

#endif

static void poll_ready(probe_context_t *ctx)
{
    command_data_t *result = &ctx->result;
    command_result_t status = execute_command(ctx, PROBE_TEST_UNIT_READY, probe_data_size(PROBE_TEST_UNIT_READY), NULL, result);
    if (status == COMMAND_PASSED) {
        ESP_LOGI(TAG, "medium ready (not playback verification)");
        if (!ctx->toc_valid && ctx->toc_attempts < 3) {
            read_toc(ctx);
            if (!ctx->toc_valid && ctx->toc_attempts == 3) {
                ESP_LOGW(TAG, "TOC attempts exhausted; wait for medium-state change or reconnect");
            }
        }
        if (CDDA_PROBE_ENABLED && ctx->toc_valid && !ctx->faulted && !ctx->audio_attempted) {
            bool sampled = probe_audio(ctx);
#if defined(CONFIG_DISCORA_CDDA_SOAK)
            if (sampled) {
                const cdda_bench_source_t source = {
                    .context = ctx, .toc = &ctx->toc, .read = bench_read, .service = bench_service,
                    .resume_index = ctx->audio_resume_index, .resume_lba = ctx->audio_resume_lba,
                };
                ctx->quiet_audio = true;
                #if defined(CONFIG_DISCORA_CDDA_SEEK_BENCH)
                const bool seeks = true;
#else
                const bool seeks = false;
#endif
#if defined(CONFIG_DISCORA_CDDA_FULL_TRACK_BENCH)
                const bool full_track = true;
#else
                const bool full_track = false;
#endif
                cdda_bench_run(&source, CONFIG_DISCORA_CDDA_SOAK_SECONDS, seeks, full_track);
                ctx->quiet_audio = false;
                ESP_LOGI(TAG, "read outcome failures=%u recovery_reserved=%u recovered=%u",
                         ctx->read_failures, ctx->recovery.reserved, ctx->recovery.recovered);
            }
#else
            (void)sampled;
#endif
        }
    } else if (status == COMMAND_FAILED) {
        ctx->toc_valid = false;
#if defined(CONFIG_DISCORA_CD_PLAYER)
        discora_cd_player_unavailable();
#endif
        ctx->toc_attempts = 0;
        probe_sense_t sense;
        request_sense(ctx, &sense);
    }
    ctx->next_poll = now_ms() + POLL_INTERVAL_MS;
}

static void close_device(probe_context_t *ctx)
{
    if (ctx->in_flight) {
        return;
    }
    if (ctx->claimed) {
        esp_err_t err = usb_host_interface_release(ctx->client, ctx->device, ctx->interface.number);
        if (err != ESP_OK) {
            log_usb_error("release interface (retaining handle)", err);
            ctx->faulted = true;
            return;
        }
        ctx->claimed = false;
    }
    esp_err_t err = usb_host_device_close(ctx->client, ctx->device);
    if (err != ESP_OK) {
        log_usb_error("close device (retaining handle)", err);
        ctx->faulted = true;
        return;
    }
    ctx->device = NULL;
    ctx->gone = false;
    ctx->identified = false;
    ctx->toc_valid = false;
    ctx->toc_attempts = 0;
    ctx->faulted = false;
    ESP_LOGI(TAG, "device closed; free internal heap=%" PRIu32, esp_get_free_internal_heap_size());
}

static void open_device(probe_context_t *ctx, uint8_t address)
{
    ctx->gone = false;
    ctx->faulted = false;
    ctx->identified = false;
    ctx->toc_valid = false;
    ctx->toc_attempts = 0;
    esp_err_t err = usb_host_device_open(ctx->client, address, &ctx->device);
    if (err != ESP_OK) {
        ctx->device = NULL;
        log_usb_error("open device", err);
        return;
    }
    usb_device_info_t info;
    const usb_device_desc_t *device_desc;
    const usb_config_desc_t *config;
    if ((err = usb_host_device_info(ctx->device, &info)) != ESP_OK ||
        (err = usb_host_get_device_descriptor(ctx->device, &device_desc)) != ESP_OK ||
        (err = usb_host_get_active_config_descriptor(ctx->device, &config)) != ESP_OK) {
        log_usb_error("cached descriptors", err);
        close_device(ctx);
        return;
    }
    ESP_LOGI(TAG, "USB address=%u VID:PID=%04x:%04x speed=%s config=%u device_class=0x%02x",
             address, device_desc->idVendor, device_desc->idProduct,
             info.speed == USB_SPEED_FULL ? "Full-Speed" : "other", info.bConfigurationValue,
             device_desc->bDeviceClass);
    // Preserve interface class/subclass/protocol in logs, including unsupported UAS devices.
    const uint8_t *raw = (const uint8_t *)config;
    for (size_t offset = config->bLength; offset + 2 <= config->wTotalLength;) {
        const uint8_t *d = raw + offset;
        if (d[0] < 2 || d[0] > config->wTotalLength - offset) {
            break;
        }
        if (d[1] == 4 && d[0] >= 9) {
            ESP_LOGI(TAG, "interface=%u alt=%u class=0x%02x subclass=0x%02x protocol=0x%02x",
                     d[2], d[3], d[5], d[6], d[7]);
        }
        offset += d[0];
    }
    if (info.speed != USB_SPEED_FULL ||
        !probe_find_interface(raw, config->wTotalLength, &ctx->interface)) {
        ESP_LOGW(TAG, "no supported Full-Speed BOT interface (hub/UAS/other/malformed); skipped");
        close_device(ctx);
        return;
    }
    err = usb_host_interface_claim(ctx->client, ctx->device, ctx->interface.number, 0);
    if (err != ESP_OK) {
        log_usb_error("claim BOT interface", err);
        close_device(ctx);
        return;
    }
    ctx->claimed = true;
    ESP_LOGI(TAG, "BOT interface=%u IN=0x%02x MPS=%u OUT=0x%02x MPS=%u LUN=0",
             ctx->interface.number, ctx->interface.ep_in, ctx->interface.mps_in,
             ctx->interface.ep_out, ctx->interface.mps_out);
    identify_drive(ctx);
    ctx->next_poll = 0;
}

static void host_daemon(void *arg)
{
    (void)arg;
    for (;;) {
        uint32_t flags;
        esp_err_t err = usb_host_lib_handle_events(portMAX_DELAY, &flags);
        if (err != ESP_OK) {
            log_usb_error("host daemon", err);
            vTaskDelay(pdMS_TO_TICKS(20));
        }
    }
}

void discora_usb_probe_run(void)
{
    const esp_app_desc_t *app = esp_app_get_description();
    ESP_LOGI(TAG, "Discora M2 CD-DA read-only probe version=%s IDF=%s", app->version, app->idf_ver);
    ESP_LOGI(TAG, "Application ELF SHA256:");
    ESP_LOG_BUFFER_HEX_LEVEL(TAG, app->app_elf_sha256, sizeof(app->app_elf_sha256), ESP_LOG_INFO);
    ESP_LOGI(TAG, "Only INQUIRY / TEST UNIT READY / REQUEST SENSE / READ TOC / bounded READ CD; no media writes or eject");
    ESP_LOGI(TAG, "CDDA probe enabled=%u; max once per MCU boot, reconnect does not re-arm", CDDA_PROBE_ENABLED);
#if defined(CONFIG_DISCORA_CD_PLAYER)
    if (!discora_cd_player_start()) { ESP_LOGE(TAG, "CD player initialization failed"); return; }
#endif
    ESP_LOGW(TAG, "Native USB PHY is now Host; use independent UART0 for logs. External 5V VBUS required.");
    const usb_host_config_t host_config = {
        .skip_phy_setup = false,
        .intr_flags = ESP_INTR_FLAG_LEVEL1,
    };
    ESP_ERROR_CHECK(usb_host_install(&host_config));
    if (xTaskCreate(host_daemon, "usb_daemon", 4096, NULL, 2, NULL) != pdPASS) {
        ESP_ERROR_CHECK(usb_host_uninstall());
        ESP_LOGE(TAG, "cannot allocate USB daemon");
        return;
    }

    // Replies can be 18,816 bytes; keep them off the task stack, in internal DRAM.
    static probe_context_t ctx;
    const usb_host_client_config_t client_config = {
        .is_synchronous = false,
        .max_num_event_msg = 16,
        .async = {.client_event_callback = client_event, .callback_arg = &ctx},
    };
    ESP_ERROR_CHECK(usb_host_client_register(&client_config, &ctx.client));
    ESP_ERROR_CHECK(usb_host_transfer_alloc((PROBE_MAX_DATA + 63) / 64 * 64, 0, &ctx.transfer));
    uint8_t addresses[128];
    int count;
    ESP_ERROR_CHECK(usb_host_device_addr_list_fill(sizeof(addresses), addresses, &count));
    for (int i = 0; i < count; ++i) {
        ctx.pending[addresses[i]] = true;
    }
    ESP_LOGI(TAG, "Waiting for USB optical drive; readiness polling interval=%d ms", POLL_INTERVAL_MS);
    for (;;) {
#if defined(CONFIG_DISCORA_CD_PLAYER)
        handle_events(&ctx, 0);
#else
        handle_events(&ctx, 100);
#endif
        if (ctx.device) {
            if (ctx.gone) {
                close_device(&ctx);
            } else if (!ctx.faulted && ctx.identified && now_ms() >= ctx.next_poll) {
                poll_ready(&ctx);
            }
#if defined(CONFIG_DISCORA_CD_PLAYER)
            if (!ctx.device || ctx.gone || ctx.faulted || !ctx.toc_valid) {
                discora_cd_player_unavailable();
            } else {
                cd_player_read_t request;
                if (discora_cd_player_request(&request)) {
                    ctx.quiet_audio = true;
                    bool ok = read_audio(&ctx, &request.track, request.lba, request.sectors);
                    ctx.quiet_audio = false;
                    discora_cd_player_complete(&request, ok, ok ? ctx.result.data : NULL, ok ? ctx.result.size : 0);
                    if (ctx.gone || ctx.faulted || !ctx.toc_valid) discora_cd_player_unavailable();
                }
            }
#endif
        } else {
            for (unsigned address = 1; address < 128; ++address) {
                if (ctx.pending[address]) {
                    ctx.pending[address] = false;
                    open_device(&ctx, address);
                    break;
                }
            }
        }
#if defined(CONFIG_DISCORA_CD_PLAYER)
        vTaskDelay(1);
#endif
    }
}
