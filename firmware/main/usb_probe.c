#include "usb_probe.h"

#include <inttypes.h>
#include <string.h>

#include "esp_app_desc.h"
#include "esp_err.h"
#include "esp_intr_alloc.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "usb/usb_host.h"

#include "probe_protocol.h"

#if CONFIG_ESP_CONSOLE_USB_CDC || CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG || CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG
#error "Discora Host requires an independent UART console; disable both primary and secondary USB consoles in menuconfig"
#endif

enum { TRANSFER_TIMEOUT_MS = 3000, CANCEL_TIMEOUT_MS = 2000, POLL_INTERVAL_MS = 5000 };
static const char *TAG = "usb_probe";

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
    unsigned toc_attempts;
    probe_toc_t toc;
    uint32_t tag;
    int64_t next_poll;
} probe_context_t;

typedef enum { COMMAND_PASSED, COMMAND_FAILED, COMMAND_TRANSPORT_ERROR } command_result_t;

typedef struct {
    uint8_t data[PROBE_MAX_DATA];
    size_t size;
} command_data_t;

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

static esp_err_t wait_transfer(probe_context_t *ctx)
{
    int64_t deadline = now_ms() + TRANSFER_TIMEOUT_MS;
    while (ctx->in_flight && !ctx->gone && now_ms() < deadline) {
        handle_events(ctx, 20);
    }
    if (ctx->in_flight) {
        bool disconnected = ctx->gone;
        ESP_LOGW(TAG, "transfer %s ep=0x%02x; cancel and drain before reuse",
                 disconnected ? "disconnected" : "deadline exceeded", ctx->transfer->bEndpointAddress);
        // EP0 cancellation is not exposed by the IDF Host API. Preserve ownership on a
        // control timeout until unplug returns its callback; never free an in-flight URB.
        if (ctx->transfer->bEndpointAddress != 0) {
            esp_err_t err = usb_host_endpoint_halt(ctx->device, ctx->transfer->bEndpointAddress);
            log_usb_error("cancel halt", err);
            err = usb_host_endpoint_flush(ctx->device, ctx->transfer->bEndpointAddress);
            log_usb_error("cancel flush", err);
        }
        deadline = now_ms() + CANCEL_TIMEOUT_MS;
        while (ctx->in_flight && now_ms() < deadline) {
            handle_events(ctx, 20);
        }
        if (ctx->in_flight) {
            ESP_LOGE(TAG, "transfer still owned by USB stack; probe quarantined, unplug device");
        }
        return disconnected ? ESP_ERR_INVALID_STATE : ESP_ERR_TIMEOUT;
    }
    if (ctx->gone) {
        return ESP_ERR_INVALID_STATE;
    }
    if (ctx->transfer->status != USB_TRANSFER_STATUS_COMPLETED) {
        ESP_LOGW(TAG, "USB status=%d ep=0x%02x actual=%d",
                 ctx->transfer->status, ctx->transfer->bEndpointAddress,
                 ctx->transfer->actual_num_bytes);
        return ESP_FAIL;
    }
    return ESP_OK;
}

static esp_err_t submit_transfer(probe_context_t *ctx, bool control)
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
    return wait_transfer(ctx);
}

static esp_err_t bulk_transfer(probe_context_t *ctx, bool in, const uint8_t *out, size_t size)
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
    return submit_transfer(ctx, false);
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
    return submit_transfer(ctx, true);
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
                                         size_t requested, command_data_t *result)
{
    uint8_t cbw[PROBE_CBW_SIZE];
    size_t received = 0;
    int64_t started = now_ms();
    result->size = 0;
    ++ctx->tag;
    if (!probe_make_cbw(command, ctx->interface.subclass, ctx->tag, requested, cbw)) {
        ctx->faulted = true;
        return COMMAND_TRANSPORT_ERROR;
    }
    ESP_LOGI(TAG, "command=%s tag=%" PRIu32 " requested=%u LUN=0",
             probe_command_name(command), ctx->tag, (unsigned)requested);
    esp_err_t err = bulk_transfer(ctx, false, cbw, sizeof(cbw));
    if (err != ESP_OK || ctx->transfer->actual_num_bytes != PROBE_CBW_SIZE) {
        goto transport_error;
    }
    if (requested) {
        err = bulk_transfer(ctx, true, NULL, requested);
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
    err = bulk_transfer(ctx, true, NULL, PROBE_CSW_SIZE);
    if (err == ESP_FAIL && ctx->transfer->status == USB_TRANSFER_STATUS_STALL) {
        err = clear_halt(ctx, ctx->interface.ep_in);
        if (err == ESP_OK) {
            err = bulk_transfer(ctx, true, NULL, PROBE_CSW_SIZE);
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
    ESP_LOGI(TAG, "command=%s CSW=%u received=%u residue=%" PRIu32 " elapsed_ms=%" PRIi64,
             probe_command_name(command), csw.status, (unsigned)received, csw.residue,
             now_ms() - started);
    if (result->size) {
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
    command_data_t result;
    if (execute_command(ctx, PROBE_REQUEST_SENSE, probe_data_size(PROBE_REQUEST_SENSE), &result) != COMMAND_PASSED ||
        !probe_parse_sense(result.data, result.size, sense)) {
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
        command_data_t result;
        command_result_t status = execute_command(ctx, PROBE_INQUIRY, probe_data_size(PROBE_INQUIRY), &result);
        if (status == COMMAND_TRANSPORT_ERROR) {
            return;
        }
        if (status == COMMAND_PASSED) {
            probe_inquiry_t identity;
            if (!probe_parse_inquiry(result.data, result.size, &identity)) {
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
    command_data_t result;
    ++ctx->toc_attempts;
    ESP_LOGI(TAG, "TOC attempt=%u/3 format=0 MSF=0", ctx->toc_attempts);
    command_result_t status = execute_command(ctx, PROBE_READ_TOC, PROBE_TOC_HEADER_SIZE, &result);
    if (status != COMMAND_PASSED) {
        if (status == COMMAND_FAILED) {
            probe_sense_t sense;
            request_sense(ctx, &sense);
        }
        return;
    }
    size_t total_size;
    if (!probe_toc_size_from_header(result.data, result.size, &total_size)) {
        ESP_LOGE(TAG, "invalid TOC header; no track metadata published");
        return;
    }
    uint8_t header[PROBE_TOC_HEADER_SIZE];
    memcpy(header, result.data, sizeof(header));
    ESP_LOGI(TAG, "TOC header first=%u last=%u total_bytes=%u", header[2], header[3], (unsigned)total_size);
    status = execute_command(ctx, PROBE_READ_TOC, total_size, &result);
    if (status != COMMAND_PASSED) {
        if (status == COMMAND_FAILED) {
            probe_sense_t sense;
            request_sense(ctx, &sense);
        }
        return;
    }
    if (result.size < sizeof(header) || memcmp(header, result.data, sizeof(header)) != 0 ||
        !probe_parse_toc(result.data, result.size, &ctx->toc)) {
        ESP_LOGE(TAG, "TOC truncated, changed or malformed; no track metadata published");
        return;
    }
    ctx->toc_valid = true;
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

static void poll_ready(probe_context_t *ctx)
{
    command_data_t result;
    command_result_t status = execute_command(ctx, PROBE_TEST_UNIT_READY, probe_data_size(PROBE_TEST_UNIT_READY), &result);
    if (status == COMMAND_PASSED) {
        ESP_LOGI(TAG, "medium ready (PCM audio not tested)");
        if (!ctx->toc_valid && ctx->toc_attempts < 3) {
            read_toc(ctx);
            if (!ctx->toc_valid && ctx->toc_attempts == 3) {
                ESP_LOGW(TAG, "TOC attempts exhausted; wait for medium-state change or reconnect");
            }
        }
    } else if (status == COMMAND_FAILED) {
        ctx->toc_valid = false;
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
    ESP_LOGI(TAG, "Discora M2 TOC read-only probe version=%s IDF=%s", app->version, app->idf_ver);
    ESP_LOGI(TAG, "Application ELF SHA256:");
    ESP_LOG_BUFFER_HEX_LEVEL(TAG, app->app_elf_sha256, sizeof(app->app_elf_sha256), ESP_LOG_INFO);
    ESP_LOGI(TAG, "Only INQUIRY / TEST UNIT READY / REQUEST SENSE / READ TOC; no media writes or eject");
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

    probe_context_t ctx = {0};
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
        handle_events(&ctx, 100);
        if (ctx.device) {
            if (ctx.gone) {
                close_device(&ctx);
            } else if (!ctx.faulted && ctx.identified && now_ms() >= ctx.next_poll) {
                poll_ready(&ctx);
            }
        } else {
            for (unsigned address = 1; address < 128; ++address) {
                if (ctx.pending[address]) {
                    ctx.pending[address] = false;
                    open_device(&ctx, address);
                    break;
                }
            }
        }
    }
}
