#include "audio_diag.h"
#include "audio_core.h"
#include "audio_i2s.h"
#include "test_tone.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <string.h>
#include <unistd.h>
#include "sdkconfig.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#if defined(CONFIG_DISCORA_AUDIO_DIAGNOSTIC)
static const char *TAG = "audio_diag";
static audio_core_t core;
static audio_i2s_t output;
static test_tone_t tone;
static uint8_t storage[8 * AUDIO_BLOCK_BYTES];
static uint8_t block[AUDIO_BLOCK_BYTES];
static uint8_t preload[AUDIO_PRELOAD_BYTES];

static void status(void)
{
    ESP_LOGI(TAG, "state=%s tone=%s tx=%s queued=%u dequeued=%" PRIu64 " generation=%" PRIu32 " underruns=%" PRIu32,
             audio_state_name(core.state), test_tone_name(tone.mode), output.running ? "running" : "closed", (unsigned)core.pcm.used,
             core.dequeued_bytes, core.generation, core.underruns);
}

static void output_fault(esp_err_t err)
{
    ESP_LOGE(TAG, "I2S error=%s; stopped, explicit stop required before retry", esp_err_to_name(err));
    esp_err_t closed = audio_i2s_close(&output);
    if (closed != ESP_OK) ESP_LOGE(TAG, "I2S close=%s; retaining handle", esp_err_to_name(closed));
    audio_core_fault(&core);
}

static void command(const char *line)
{
    if (!strcmp(line, "status")) { status(); return; }
    if (!strcmp(line, "help")) {
        ESP_LOGI(TAG, "commands: left right stereo silence play pause stop status help (diagnostic tones only)");
        return;
    }
    if (!strcmp(line, "pause")) {
        esp_err_t err = audio_i2s_close(&output);
        if (err != ESP_OK) output_fault(err);
        else audio_core_pause(&core);
        status();
        return;
    }
    if (!strcmp(line, "stop")) {
        esp_err_t err = audio_i2s_close(&output);
        if (err != ESP_OK) output_fault(err);
        else {
            audio_core_stop(&core);
            test_tone_init(&tone, tone.mode);
        }
        status();
        return;
    }
    if (!strcmp(line, "play")) {
        if (!audio_core_play(&core)) ESP_LOGW(TAG, "play rejected; use stop to clear fault");
        status();
        return;
    }
    test_tone_mode_t mode;
    if (!strcmp(line, "left")) mode = TONE_LEFT;
    else if (!strcmp(line, "right")) mode = TONE_RIGHT;
    else if (!strcmp(line, "stereo")) mode = TONE_STEREO;
    else if (!strcmp(line, "silence")) mode = TONE_SILENCE;
    else { ESP_LOGW(TAG, "unknown command; use help"); return; }
    if (core.state == AUDIO_FAULT) { ESP_LOGW(TAG, "source change rejected; use stop to clear fault"); return; }
    esp_err_t err = audio_i2s_close(&output);
    if (err != ESP_OK) { output_fault(err); return; }
    audio_core_stop(&core); // New source invalidates previous generation and all software/DMA bytes.
    test_tone_init(&tone, mode);
    audio_core_play(&core);
    status();
}

static void poll_commands(void)
{
    static char line[32];
    static size_t used;
    static bool discard;
    char input[64];
    ssize_t count = read(STDIN_FILENO, input, sizeof(input));
    if (count < 0 && errno != EAGAIN && errno != EWOULDBLOCK) {
        output_fault(ESP_FAIL);
        vTaskDelay(pdMS_TO_TICKS(10));
        return;
    }
    for (ssize_t i = 0; i < count; ++i) {
        char c = input[i];
        if (c == '\r' || c == '\n') {
            if (discard) ESP_LOGW(TAG, "overlong/invalid command discarded");
            else if (used) { line[used] = 0; command(line); }
            used = 0;
            discard = false;
        } else if (c < 32 || c > 126 || used + 1 >= sizeof(line)) {
            discard = true;
        } else if (!discard) {
            line[used++] = c;
        }
    }
}

void discora_audio_diag_run(void)
{
    ESP_LOGI(TAG, "Discora I2S tone diagnostic; generated PCM only, USB optical service inactive");
    ESP_LOGI(TAG, "target=44100Hz PCM16LE stereo Philips I2S BCLK=GPIO%d LRCK=GPIO%d DATA=GPIO%d MCLK=unused",
             CONFIG_DISCORA_I2S_BCLK, CONFIG_DISCORA_I2S_LRCK, CONFIG_DISCORA_I2S_DATA);
    ESP_LOGI(TAG, "nominal BCLK=1411200Hz; left=441Hz right=882Hz peak=4096; no analog/clock verification");
    ESP_LOGI(TAG, "boot state=stopped; enter left/right/stereo/silence or play via UART0 115200");
    if (!audio_core_init(&core, storage, sizeof(storage), AUDIO_PRELOAD_BYTES) ||
        !test_tone_init(&tone, TONE_LEFT)) { ESP_LOGE(TAG, "audio core init failed"); return; }
    int flags = fcntl(STDIN_FILENO, F_GETFL);
    if (flags < 0 || fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK) < 0) {
        ESP_LOGE(TAG, "UART0 nonblocking input unavailable"); return;
    }
    for (;;) {
        poll_commands();
        if (core.state != AUDIO_PREFILL && core.state != AUDIO_PLAYING) {
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }
        while (core.pcm.capacity - core.pcm.used >= sizeof(block)) {
            if (!test_tone_render(&tone, block, sizeof(block)) ||
                !audio_core_push(&core, core.generation, block, sizeof(block))) {
                output_fault(ESP_FAIL);
                break;
            }
        }
        if (core.state != AUDIO_PLAYING) continue;
        if (!output.running) {
            esp_err_t err = audio_i2s_open(&output, CONFIG_DISCORA_I2S_BCLK,
                                          CONFIG_DISCORA_I2S_LRCK, CONFIG_DISCORA_I2S_DATA);
            if (err != ESP_OK) { output_fault(err); continue; }
            if (!audio_core_take(&core, preload, sizeof(preload))) { output_fault(ESP_FAIL); continue; }
            err = audio_i2s_start(&output, preload, sizeof(preload));
            if (err != ESP_OK) output_fault(err);
            else status();
        } else {
            if (!audio_core_take(&core, block, sizeof(block))) {
                esp_err_t err = audio_i2s_close(&output);
                if (err != ESP_OK) output_fault(err);
                else ESP_LOGW(TAG, "software underrun; use play to rebuffer");
                continue;
            }
            esp_err_t err = audio_i2s_write(&output, block, sizeof(block));
            if (err != ESP_OK) output_fault(err);
        }
    }
}
#endif
