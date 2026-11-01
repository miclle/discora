#include "sdkconfig.h"
#if defined(CONFIG_DISCORA_CD_PLAYER)
#include "cd_player.h"
#include "audio_i2s.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

static const char *TAG = "cd_player";
static cd_player_core_t player;
static uint8_t storage[64 * PROBE_CD_SECTOR_SIZE];
static uint8_t block[AUDIO_PRELOAD_BYTES]; // Output task only; USB never touches this copy.
static SemaphoreHandle_t lock;
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
static audio_i2s_t output;
static const char *sink = "I2S-unverified";
#else
static const char *sink = "software-clock-no-I2S";
#endif
static uint32_t output_generation;
static bool running;
static int64_t next_tick, drain_until;

static bool close_output(void)
{
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
    esp_err_t err = audio_i2s_close(&output);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "output close failed=%s; handle retained", esp_err_to_name(err));
        xSemaphoreTake(lock, portMAX_DELAY);
        audio_core_fault(&player.audio);
        xSemaphoreGive(lock);
        return false;
    }
#endif
    running = false;
    drain_until = 0;
    return true;
}
static void status(void)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    audio_state_t state = player.audio.state;
    uint32_t gen = player.audio.generation, underruns = player.audio.underruns;
    uint32_t lba = player.next_lba, reads = player.completed_reads, stale = player.stale_completions;
    size_t queued = player.audio.pcm.used;
    uint64_t bytes = player.audio.dequeued_bytes;
    bool media = player.media, eof = player.eof, pending = player.pending;
    unsigned track = media ? player.toc.tracks[player.index].number : 0;
    xSemaphoreGive(lock);
    ESP_LOGI(TAG, "state=%s sink=%s media=%u track=%u generation=%" PRIu32 " queued=%u delivered=%" PRIu64
             " next_lba=%" PRIu32 " eof=%u pending=%u reads=%" PRIu32 " stale=%" PRIu32 " underruns=%" PRIu32,
             audio_state_name(state), sink, media, track, gen, (unsigned)queued, bytes, lba, eof, pending, reads, stale, underruns);
}
static void command(const char *line)
{
    if (!strcmp(line, "status")) { status(); return; }
    if (!strcmp(line, "help")) {
        ESP_LOGI(TAG, "commands: play pause stop next prev track N status help; track/next/prev start selected track; EOF stops");
        return;
    }
    unsigned track = 0; char extra;
    bool select = sscanf(line, "track %u %c", &track, &extra) == 1 && track >= 1 && track <= 99;
    bool known = select || !strcmp(line,"play") || !strcmp(line,"pause") || !strcmp(line,"stop") ||
                 !strcmp(line,"next") || !strcmp(line,"prev");
    if (!known) { ESP_LOGW(TAG,"unknown command; use help"); return; }
    // Only this task owns output; reject invalid commands without discarding DMA.
    xSemaphoreTake(lock, portMAX_DELAY);
    bool ok = true;
    if (select) ok = cd_player_select(&player, track);
    else if (!strcmp(line,"play")) ok = cd_player_play(&player);
    else if (!strcmp(line,"pause")) ok = cd_player_pause(&player);
    else if (!strcmp(line,"stop")) cd_player_stop(&player);
    else ok = cd_player_step(&player, !strcmp(line,"next") ? 1 : -1);
    xSemaphoreGive(lock);
    if (ok && strcmp(line,"play") && !close_output()) { status(); return; }
    ESP_LOGI(TAG,"command=%s accepted=%u",line,ok);
    if (!ok) ESP_LOGW(TAG,"command rejected: %s (media/state/track boundary)",line);
    status();
}
static void poll_commands(void)
{
    static char line[32]; static size_t used; static bool discard;
    char input[64]; ssize_t n = read(STDIN_FILENO, input, sizeof(input));
    if (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK) { discora_cd_player_unavailable(); return; }
    for (ssize_t i = 0; i < n; ++i) {
        char c = input[i];
        if (c == '\r' || c == '\n') {
            if (discard) ESP_LOGW(TAG,"invalid/overlong command discarded");
            else if (used) { line[used] = 0; command(line); }
            used = 0; discard = false;
        } else if (c < 32 || c > 126 || used + 1 >= sizeof(line)) discard = true;
        else if (!discard) line[used++] = c;
    }
}
static void output_task(void *arg)
{
    (void)arg;
    for (;;) {
        poll_commands();
        xSemaphoreTake(lock, portMAX_DELAY);
        audio_state_t state = player.audio.state;
        uint32_t gen = player.audio.generation;
        xSemaphoreGive(lock);
        if (gen != output_generation) {
            if (!close_output()) { vTaskDelay(1); continue; }
            output_generation = gen;
        }
        if (drain_until && state == AUDIO_STOPPED && esp_timer_get_time() < drain_until) { vTaskDelay(1); continue; }
        if (state != AUDIO_PLAYING) {
            if (running) { close_output(); status(); }
            vTaskDelay(1); continue;
        }
        if (!running) next_tick = esp_timer_get_time() + 10000;
#if !defined(CONFIG_DISCORA_CD_PLAYER_I2S)
        if (!running) running = true;
        if (esp_timer_get_time() < next_tick) { vTaskDelay(1); continue; }
#endif
        size_t wanted = AUDIO_BLOCK_BYTES;
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
        if (!running) wanted = AUDIO_PRELOAD_BYTES;
#endif
        xSemaphoreTake(lock, portMAX_DELAY);
        size_t n = cd_player_take(&player, block, wanted);
        state = player.audio.state;
        bool eof = player.eof;
        xSemaphoreGive(lock);
        if (!n) {
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
            if (state == AUDIO_STOPPED && eof && running) { drain_until = esp_timer_get_time() + 50000; continue; }
#else
            (void)eof;
#endif
            close_output(); status(); continue;
        }
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
        esp_err_t err;
        if (!running) {
            err = audio_i2s_open(&output, CONFIG_DISCORA_I2S_BCLK, CONFIG_DISCORA_I2S_LRCK, CONFIG_DISCORA_I2S_DATA);
            if (err == ESP_OK) err = audio_i2s_start(&output, block, n);
        } else err = audio_i2s_write(&output, block, n);
        if (err != ESP_OK) {
            ESP_LOGE(TAG,"output error=%s; explicit stop required",esp_err_to_name(err));
            close_output();
            xSemaphoreTake(lock, portMAX_DELAY); audio_core_fault(&player.audio); xSemaphoreGive(lock);
            status(); continue;
        }
        running = true;
#else
        next_tick += 10000; // Catch up using actual elapsed time, never silently slow the consumer clock.
#endif
    }
}
bool discora_cd_player_start(void)
{
    if (!cd_player_init(&player, storage, sizeof(storage), 48 * PROBE_CD_SECTOR_SIZE)) return false;
    lock = xSemaphoreCreateMutex();
    if (!lock) return false;
    int flags = fcntl(STDIN_FILENO, F_GETFL);
    if (flags < 0 || fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK) < 0 ||
        xTaskCreate(output_task,"cd_output",6144,NULL,3,NULL) != pdPASS) {
        vSemaphoreDelete(lock); lock = NULL; return false;
    }
    ESP_LOGI(TAG,"CD player boot=stopped sink=%s; UART0 controls; no automatic READ CD; one track then stop",sink);
    return true;
}
void discora_cd_player_media(const probe_toc_t *toc)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    bool ok = cd_player_media(&player, toc);
    xSemaphoreGive(lock);
    ESP_LOGI(TAG,"media published=%u; playback remains stopped",ok);
}
void discora_cd_player_unavailable(void)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    if (player.media) cd_player_lost(&player);
    xSemaphoreGive(lock);
}
bool discora_cd_player_request(cd_player_read_t *request)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    bool ok = cd_player_request(&player,request);
    xSemaphoreGive(lock); return ok;
}
void discora_cd_player_complete(const cd_player_read_t *request, bool ok, const uint8_t *data, size_t size)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    bool accepted = cd_player_complete(&player,request,ok,data,size);
    xSemaphoreGive(lock);
    if (!accepted) ESP_LOGW(TAG,"source result rejected generation=%" PRIu32 " lba=%" PRIu32 " ok=%u (stale or fault)",request->generation,request->lba,ok);
}
#endif
