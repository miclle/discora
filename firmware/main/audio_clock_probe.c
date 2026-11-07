#include "sdkconfig.h"
#if defined(CONFIG_DISCORA_AUDIO_DIAGNOSTIC) && defined(CONFIG_DISCORA_DIAG_CLOCK_PROBE)
#include "audio_clock_probe.h"
#include "audio_report.h"
#include "driver/pulse_cnt.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include <inttypes.h>

static const char *TAG = "clock_probe";
static struct {
    pcnt_unit_handle_t unit;
    pcnt_channel_handle_t channel;
    int gpio;
    bool running;
    int64_t started;
} counters[2];
static bool initialized, failed, active;

void audio_clock_probe_cancel(void)
{
    active = false;
    for (unsigned i = 0; i < 2; ++i) {
        if (!counters[i].running) continue;
        esp_err_t err = pcnt_unit_stop(counters[i].unit);
        if (err == ESP_OK) counters[i].running = false;
        else {
            failed = true;
            audio_report(TAG, "stop error=%d; probe disabled until reboot", err);
        }
    }
}

static esp_err_t init_counter(unsigned i, int gpio)
{
    counters[i].gpio = gpio;
    pcnt_unit_config_t unit = {.low_limit = -30000, .high_limit = 30000,
                              .flags.accum_count = true};
    esp_err_t err = pcnt_new_unit(&unit, &counters[i].unit);
    if (err != ESP_OK) return err;
    // IDF v5.4 appends input routing without changing the existing I2S output.
    pcnt_chan_config_t channel = {.edge_gpio_num = gpio, .level_gpio_num = -1};
    if ((err = pcnt_new_channel(counters[i].unit, &channel, &counters[i].channel)) != ESP_OK) return err;
    if ((err = gpio_pullup_dis(gpio)) != ESP_OK) return err;
    if ((err = pcnt_channel_set_edge_action(counters[i].channel,
                PCNT_CHANNEL_EDGE_ACTION_INCREASE, PCNT_CHANNEL_EDGE_ACTION_HOLD)) != ESP_OK) return err;
    if ((err = pcnt_channel_set_level_action(counters[i].channel,
                PCNT_CHANNEL_LEVEL_ACTION_KEEP, PCNT_CHANNEL_LEVEL_ACTION_KEEP)) != ESP_OK) return err;
    // Accumulator needs both limit events; filter stays disabled for MHz clocks.
    if ((err = pcnt_unit_add_watch_point(counters[i].unit, 30000)) != ESP_OK) return err;
    if ((err = pcnt_unit_add_watch_point(counters[i].unit, -30000)) != ESP_OK) return err;
    return pcnt_unit_enable(counters[i].unit);
}

esp_err_t audio_clock_probe_begin(int bclk, int lrck)
{
    if (failed || active) return ESP_ERR_INVALID_STATE;
    if (bclk < 1 || bclk > 18 || bclk == 3 || lrck < 1 || lrck > 18 || lrck == 3 || bclk == lrck)
        return ESP_ERR_INVALID_ARG;
    esp_err_t err = ESP_OK;
    if (!initialized) {
        if ((err = init_counter(0, bclk)) != ESP_OK ||
            (err = init_counter(1, lrck)) != ESP_OK) goto fail;
        initialized = true;
    }
    if (counters[0].gpio != bclk || counters[1].gpio != lrck) return ESP_ERR_INVALID_ARG;
    for (unsigned i = 0; i < 2; ++i) {
        // Reopening I2S may disable pad input; preserve output and enable input again.
        if ((err = gpio_input_enable(counters[i].gpio)) != ESP_OK) goto fail;
        if ((err = pcnt_unit_clear_count(counters[i].unit)) != ESP_OK) goto fail;
        counters[i].started = esp_timer_get_time();
        if ((err = pcnt_unit_start(counters[i].unit)) != ESP_OK) goto fail;
        counters[i].running = true;
    }
    active = true;
    audio_report(TAG, "started GPIO%d/ GPIO%d; rising edges, >=1s gate; MCU pad readback only", bclk, lrck);
    return ESP_OK;
fail:
    // Keep partially allocated handles bounded; refuse retries until reboot.
    failed = true;
    audio_clock_probe_cancel();
    audio_report(TAG, "setup error=%d; probe disabled until reboot", err);
    return err;
}

void audio_clock_probe_poll(void)
{
    if (!active || esp_timer_get_time() - counters[1].started < 1000000) return;
    active = false;
    int counts[2] = {0};
    int64_t elapsed[2] = {0};
    esp_err_t err = ESP_OK;
    // Stop/read both before logging. API/timestamp overhead is not calibrated.
    for (unsigned i = 0; i < 2; ++i) {
        if ((err = pcnt_unit_stop(counters[i].unit)) != ESP_OK) goto fail;
        counters[i].running = false;
        elapsed[i] = esp_timer_get_time() - counters[i].started;
        if ((err = pcnt_unit_get_count(counters[i].unit, &counts[i])) != ESP_OK) goto fail;
    }
    for (unsigned i = 0; i < 2; ++i)
        audio_report(TAG, "GPIO%d edges=%d elapsed_us=%" PRId64 " (not DAC waveform verification)",
                     counters[i].gpio, counts[i], elapsed[i]);
    return;
fail:
    failed = true;
    audio_clock_probe_cancel();
    audio_report(TAG, "capture error=%d; no valid result; probe disabled until reboot", err);
}
#endif
