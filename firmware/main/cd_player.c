#include "sdkconfig.h"
#if defined(CONFIG_DISCORA_CD_PLAYER)
#include "cd_player.h"
#include "track_buttons.h"
#include "oled_display.h"
#include "audio_i2s.h"
#include "audio_i2s_report.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_system.h"
#if defined(CONFIG_DISCORA_CD_PLAYER_VERIFY)
#include "mbedtls/sha256.h"
#endif
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
static bool output_quiescent; // Protected by lock, acknowledged only by output owner.
static int64_t next_tick;
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
// Owner-task snapshots only; defer their logs until the channel is closed.
typedef struct { int64_t us; unsigned dma, overflow; } eof_snapshot_t;
static struct { uint32_t generation; bool active; eof_snapshot_t point[6]; } eof_trace;
static void eof_mark(unsigned index)
{
    eof_trace.point[index] = (eof_snapshot_t){.us=esp_timer_get_time(),
        .dma=atomic_load_explicit(&output.dma_blocks,memory_order_relaxed),
        .overflow=atomic_load_explicit(&output.event_overflows,memory_order_relaxed)};
}
static void eof_report(void)
{
    static const char *names[] = {"last_write", "before_verify", "after_verify", "drain_start", "before_close", "closed"};
    for (unsigned i=0; i<6; i+=2) {
        eof_snapshot_t a=eof_trace.point[i], b=eof_trace.point[i+1];
        audio_report(TAG,"eof_trace generation=%" PRIu32 " %s_us=%" PRId64 " %s_dma=%u %s_ovf=%u %s_us=%" PRId64 " %s_dma=%u %s_ovf=%u",
            eof_trace.generation,names[i],a.us,names[i],a.dma,names[i],a.overflow,
            names[i+1],b.us,names[i+1],b.dma,names[i+1],b.overflow);
    }
    eof_trace.active=false;
}
#endif

#if defined(CONFIG_DISCORA_CD_PLAYER_VERIFY)
// Verification only: serialized with the PCM queue; never hash stale source replies.
static struct {
    mbedtls_sha256_context source, consumed;
    uint32_t generation;
    uint64_t produced, delivered;
    size_t tail;
    bool initialized, valid, finished, matched;
} verify;
static void verify_generation(void)
{
    if (verify.initialized && verify.generation == player.audio.generation) return;
    if (verify.initialized) {
        mbedtls_sha256_free(&verify.source);
        mbedtls_sha256_free(&verify.consumed);
    }
    memset(&verify, 0, sizeof(verify));
    mbedtls_sha256_init(&verify.source);
    mbedtls_sha256_init(&verify.consumed);
    verify.valid = mbedtls_sha256_starts(&verify.source, 0) == 0;
    verify.valid &= mbedtls_sha256_starts(&verify.consumed, 0) == 0;
    verify.generation = player.audio.generation;
    verify.initialized = true;
}
static void verify_take(const uint8_t *data, size_t size)
{
    verify_generation();
    if (size) {
        verify.valid &= mbedtls_sha256_update(&verify.consumed, data, size) == 0;
        verify.delivered += size;
        verify.tail = size;
    } else if (player.eof && !player.audio.pcm.used && player.audio.state == AUDIO_STOPPED && !verify.finished) {
        uint8_t a[32] = {0}, b[32] = {0}; char ah[65], bh[65];
        verify.valid &= mbedtls_sha256_finish(&verify.source, a) == 0;
        verify.valid &= mbedtls_sha256_finish(&verify.consumed, b) == 0;
        for (unsigned i = 0; i < 32; ++i) { sprintf(ah + 2*i, "%02x", a[i]); sprintf(bh + 2*i, "%02x", b[i]); }
        const probe_track_t *t = &player.toc.tracks[player.index];
        uint64_t expected = (uint64_t)(t->end_lba - t->start_lba) * PROBE_CD_SECTOR_SIZE;
        bool match = verify.valid && verify.produced == expected && verify.delivered == expected && !memcmp(a,b,32);
        audio_report(TAG,"verify EOF generation=%" PRIu32 " produced=%" PRIu64 " consumed=%" PRIu64 " expected=%" PRIu64 " tail=%u match=%u",
                 verify.generation, verify.produced, verify.delivered, expected, (unsigned)verify.tail, match);
        audio_report(TAG,"verify source_sha256=%s consumed_sha256=%s scope=software-queue",ah,bh);
        verify.matched = match;
        verify.finished = true;
    }
}
#endif

#if defined(CONFIG_DISCORA_CD_PLAYER_FAULT_TEST)
static bool delay_used, failure_used, failure_armed;
static int64_t delay_until;
static uint32_t failure_generation;
static bool inject_command(const char *line)
{
    bool delay = !strcmp(line, "test delay"), fail = !strcmp(line, "test fail");
    if (!delay && !fail) return false;
    xSemaphoreTake(lock, portMAX_DELAY);
    bool accepted = player.audio.state == AUDIO_PLAYING && (delay ? !delay_used : !failure_used);
    if (accepted && delay) { delay_used = true; delay_until = esp_timer_get_time() + 1200000; }
    if (accepted && fail) { failure_used = failure_armed = true; failure_generation = player.audio.generation; }
    xSemaphoreGive(lock);
    ESP_LOGW(TAG,"TEST injection=%s accepted=%u; software-only, once per boot",delay ? "producer-pause-1200ms" : "source-failure-armed",accepted);
    ESP_LOGI(TAG,"command=%s accepted=%u",line,accepted);
    return true;
}
#endif

static bool close_output(void)
{
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
    if (eof_trace.active) eof_mark(4);
    esp_err_t err = audio_i2s_close(&output);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "output close failed=%s; handle retained", esp_err_to_name(err));
        xSemaphoreTake(lock, portMAX_DELAY);
        cd_player_fault(&player);
        xSemaphoreGive(lock);
        return false;
    }
#endif
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
    if (eof_trace.active) { eof_mark(5); eof_report(); }
#endif
    running = false;
    return true;
}
static void status(void)
{
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
    audio_i2s_report(TAG, &output);
#endif
    xSemaphoreTake(lock, portMAX_DELAY);
    audio_state_t state = player.audio.state;
    uint32_t gen = player.audio.generation, underruns = player.audio.underruns;
    uint32_t lba = player.next_lba, reads = player.completed_reads, stale = player.stale_completions;
    size_t queued = player.audio.pcm.used;
    uint64_t bytes = player.audio.dequeued_bytes;
    bool media = player.media, eof = player.eof, pending = player.pending, continuous = player.continuous;
    unsigned track = media ? player.toc.tracks[player.index].number : 0;
    xSemaphoreGive(lock);
    audio_report(TAG,"resources heap_free=%lu heap_min=%lu output_stack_min=%u report_dropped=%" PRIu32,
             (unsigned long)esp_get_free_heap_size(), (unsigned long)esp_get_minimum_free_heap_size(),
             (unsigned)uxTaskGetStackHighWaterMark(NULL), audio_report_dropped());
    audio_report(TAG, "state=%s sink=%s media=%u track=%u generation=%" PRIu32 " queued=%u delivered=%" PRIu64
             " next_lba=%" PRIu32 " eof=%u pending=%u reads=%" PRIu32 " stale=%" PRIu32 " underruns=%" PRIu32 " continuous=%u",
             audio_state_name(state), sink, media, track, gen, (unsigned)queued, bytes, lba, eof, pending, reads, stale, underruns, continuous);
}
static void command(const char *line)
{
#if defined(CONFIG_DISCORA_CD_PLAYER_FAULT_TEST)
    if (inject_command(line)) { status(); return; }
#endif
    if (!strcmp(line, "status")) { status(); return; }
    if (!strcmp(line, "help")) {
        ESP_LOGI(TAG, "commands: play play-disc pause stop next prev track N status help; play-disc starts current track through disc end");
        return;
    }
    unsigned track = 0; char extra;
    bool select = sscanf(line, "track %u %c", &track, &extra) == 1 && track >= 1 && track <= 99;
    bool known = select || !strcmp(line,"play-disc") || !strcmp(line,"play") || !strcmp(line,"pause") || !strcmp(line,"stop") ||
                 !strcmp(line,"next") || !strcmp(line,"prev");
    if (!known) { ESP_LOGW(TAG,"unknown command; use help"); return; }
    // Only this task owns output; reject invalid commands without discarding DMA.
    xSemaphoreTake(lock, portMAX_DELAY);
    bool ok = true;
    if (select) ok = cd_player_select(&player, track);
    else if (!strcmp(line,"play")) ok = cd_player_play(&player);
    else if (!strcmp(line,"play-disc")) ok = cd_player_play_disc(&player);
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
static void poll_track_buttons(void)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    int direction = discora_track_buttons_poll(player.media && player.audio.state != AUDIO_FAULT);
    bool ok = direction && cd_player_step(&player, direction);
    xSemaphoreGive(lock);
    if (!direction) return;
    // Same transition as UART next/prev; only this task may discard the old DMA.
    if (ok && !close_output()) { status(); return; }
    ESP_LOGI(TAG, "button=%s accepted=%u", direction < 0 ? "prev" : "next", ok);
    status();
}
static void advance_sequence(void)
{
    // Called only by output owner, after any EOF drain and successful channel deletion.
    if (running) return;
    xSemaphoreTake(lock, portMAX_DELAY);
    bool ready = player.continuous && player.media && player.eof && !player.pending &&
                 !player.audio.pcm.used && player.audio.state == AUDIO_STOPPED;
    if (!ready) { xSemaphoreGive(lock); return; }
#if defined(CONFIG_DISCORA_CD_PLAYER_VERIFY)
    if (!verify.finished || !verify.matched || verify.generation != player.audio.generation) {
        cd_player_fault(&player); xSemaphoreGive(lock);
        audio_report(TAG,"sequence stopped: EOF verification failed"); return;
    }
#endif
    unsigned from = player.toc.tracks[player.index].number;
    bool advanced = cd_player_advance(&player);
    unsigned to = player.toc.tracks[player.index].number;
    uint32_t generation = player.audio.generation;
    xSemaphoreGive(lock);
    audio_report(TAG,"sequence %s from=%u to=%u generation=%" PRIu32,
                 advanced ? "advance" : "complete",from,to,generation);
}
static void output_task(void *arg)
{
    (void)arg;
    for (;;) {
        poll_commands();
        poll_track_buttons();
        xSemaphoreTake(lock, portMAX_DELAY);
        bool media = player.media;
        audio_state_t state = player.audio.state;
        uint32_t gen = player.audio.generation;
        xSemaphoreGive(lock);
        if (!media) {
            if (close_output()) {
                xSemaphoreTake(lock, portMAX_DELAY);
                if (!player.media) output_quiescent = true;
                xSemaphoreGive(lock);
            }
            vTaskDelay(1); continue;
        }
        if (gen != output_generation) {
            if (!close_output()) { vTaskDelay(1); continue; }
            output_generation = gen;
        }
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
        if (state == AUDIO_STOPPED && audio_i2s_draining(&output, esp_timer_get_time())) { vTaskDelay(1); continue; }
#endif
        if (state != AUDIO_PLAYING) {
            if (running) {
                if (!close_output()) { status(); vTaskDelay(1); continue; }
                status();
            }
            advance_sequence();
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
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
        if (!n && eof_trace.active) eof_mark(1);
#endif
#if defined(CONFIG_DISCORA_CD_PLAYER_VERIFY)
        verify_take(block, n);
#endif
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
        if (!n && eof_trace.active) eof_mark(2);
        bool last_pcm = n && player.eof && !player.audio.pcm.used;
#endif
        state = player.audio.state;
        bool eof = player.eof;
        xSemaphoreGive(lock);
        if (!n) {
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
            if (state == AUDIO_STOPPED && eof && running) { audio_i2s_eof(&output, esp_timer_get_time()); if (eof_trace.active) eof_mark(3); continue; }
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
            xSemaphoreTake(lock, portMAX_DELAY); cd_player_fault(&player); xSemaphoreGive(lock);
            status(); continue;
        }
        if (last_pcm) {
            memset(&eof_trace,0,sizeof(eof_trace));
            eof_trace.active=true; eof_trace.generation=gen; eof_mark(0);
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
    if (!discora_track_buttons_start()) { vSemaphoreDelete(lock); lock = NULL; return false; }
    int flags = fcntl(STDIN_FILENO, F_GETFL);
    if (flags < 0 || fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK) < 0 ||
        xTaskCreate(output_task,"cd_output",6144,NULL,3,NULL) != pdPASS) {
        vSemaphoreDelete(lock); lock = NULL; return false;
    }
    discora_oled_start(); // Optional UI failure must not prevent playback or USB startup.
    ESP_LOGI(TAG,"CD player boot=stopped sink=%s; UART0 controls; no automatic READ CD; play is single-track, play-disc is explicit",sink);
    return true;
}
bool discora_cd_player_snapshot(cd_player_status_t *status)
{
    if (!status || !lock || xSemaphoreTake(lock, pdMS_TO_TICKS(10)) != pdTRUE) return false;
    *status = cd_player_snapshot(&player);
    xSemaphoreGive(lock);
    return true;
}
void discora_cd_player_media(const probe_toc_t *toc)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    output_quiescent = false;
    discora_track_buttons_reset();
    bool ok = cd_player_media(&player, toc);
    xSemaphoreGive(lock);
    ESP_LOGI(TAG,"media published=%u; playback remains stopped",ok);
}
void discora_cd_player_unavailable(void)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    if (player.media) cd_player_lost(&player);
    discora_track_buttons_reset();
    xSemaphoreGive(lock);
}
bool discora_cd_player_quiescent(void)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    bool stopped = !player.media && output_quiescent;
    xSemaphoreGive(lock);
    return stopped;
}
bool discora_cd_player_request(cd_player_read_t *request)
{
    xSemaphoreTake(lock, portMAX_DELAY);
#if defined(CONFIG_DISCORA_CD_PLAYER_FAULT_TEST)
    if (esp_timer_get_time() < delay_until) { xSemaphoreGive(lock); return false; }
#endif
    bool ok = cd_player_request(&player,request);
#if defined(CONFIG_DISCORA_CD_PLAYER_FAULT_TEST)
    if (failure_armed && failure_generation != player.audio.generation) failure_armed = false;
    if (ok && failure_armed) {
        failure_armed = false;
        cd_player_complete(&player, request, false, NULL, 0);
        ESP_LOGW(TAG,"TEST synthetic source failure; no USB request submitted; generation=%" PRIu32,request->generation);
        ok = false;
    }
#endif
    xSemaphoreGive(lock); return ok;
}
void discora_cd_player_complete(const cd_player_read_t *request, bool ok, const uint8_t *data, size_t size)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    bool accepted = cd_player_complete(&player,request,ok,data,size);
#if defined(CONFIG_DISCORA_CD_PLAYER_VERIFY)
    if (accepted) {
        verify_generation();
        verify.valid &= mbedtls_sha256_update(&verify.source, data, size) == 0;
        verify.produced += size;
    }
#endif
    xSemaphoreGive(lock);
    if (!accepted) ESP_LOGW(TAG,"source result rejected generation=%" PRIu32 " lba=%" PRIu32 " ok=%u (stale or fault)",request->generation,request->lba,ok);
}
#endif
