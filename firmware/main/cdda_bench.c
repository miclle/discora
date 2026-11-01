#include "cdda_bench.h"
#include "cdda_cursor.h"
#include "pcm_buffer.h"

#include <inttypes.h>
#include <string.h>
#include "esp_heap_caps.h"
#include "sdkconfig.h"
#include "esp_system.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/sha256.h"

static const char *TAG = "cdda_bench";
#if defined(CONFIG_DISCORA_CDDA_UNDERRUN_TEST)
enum { INJECT_UNDERRUN = 1 };
#else
enum { INJECT_UNDERRUN = 0 };
#endif

enum { PCM_RATE = 176400, BUFFER_SECTORS = 64, PREFILL_SECTORS = 48 };
#if defined(CONFIG_DISCORA_CDDA_SEEK_ROUNDS)
enum { SEEK_ROUNDS = CONFIG_DISCORA_CDDA_SEEK_ROUNDS };
#else
enum { SEEK_ROUNDS = 1 };
#endif

typedef struct {
    uint64_t bytes;
    uint32_t commands;
    int64_t longest_us;
} read_stats_t;

static void digest_log(const char *name, const uint8_t digest[32])
{
    char hex[65];
    for (size_t i = 0; i < 32; ++i) {
        static const char digits[] = "0123456789abcdef";
        hex[2 * i] = digits[digest[i] >> 4];
        hex[2 * i + 1] = digits[digest[i] & 15];
    }
    hex[64] = 0;
    ESP_LOGI(TAG, "%s SHA256=%s", name, hex);
}

static bool read_chunk(const cdda_bench_source_t *s, const probe_track_t *track,
                        uint32_t lba, uint8_t sectors, const uint8_t **data, read_stats_t *stats)
{
    size_t size = 0;
    int64_t started = esp_timer_get_time();
    if (!s->read(s->context, track, lba, sectors, data, &size) ||
        size != (size_t)sectors * PROBE_CD_SECTOR_SIZE) {
        ESP_LOGE(TAG, "read failed track=%u lba=%" PRIu32 " sectors=%u", track->number, lba, sectors);
        return false;
    }
    int64_t elapsed = esp_timer_get_time() - started;
    if (elapsed > stats->longest_us) stats->longest_us = elapsed;
    stats->bytes += size;
    ++stats->commands;
    return true;
}

static bool seek_bench(const cdda_bench_source_t *s)
{
    size_t eligible[PROBE_MAX_TRACKS], count = 0;
    for (size_t i = 0; i < s->toc->track_count; ++i) {
        const probe_track_t *t = &s->toc->tracks[i];
        if (!(t->control & 0x0c) && t->end_lba - t->start_lba >= 8) eligible[count++] = i;
    }
    if (!count) return false;
    read_stats_t stats = {0};
    const int64_t deadline = esp_timer_get_time() + INT64_C(600000000);
    ESP_LOGI(TAG, "seek start rounds=%u positions=%u soft_limit_s=600", SEEK_ROUNDS, 12 * SEEK_ROUNDS);
    for (unsigned step = 0; step < 12 * SEEK_ROUNDS; ++step) {
        unsigned i = step % 12, round = step / 12 + 1;
        if (esp_timer_get_time() >= deadline) {
            ESP_LOGE(TAG, "seek deadline reached completed_positions=%u; incomplete", step);
            return false;
        }
        if (!s->service(s->context, 0)) return false;
        size_t pick = i % 3 == 0 ? 0 : (i % 3 == 1 ? count - 1 : count / 2);
        const probe_track_t *track = &s->toc->tracks[eligible[pick]];
        uint32_t span = track->end_lba - track->start_lba;
        uint32_t lba = track->start_lba;
        switch (i / 3) {
        case 0: if (span >= 158) lba += 150; break;
        case 1: lba += (span - 8) / 2; break;
        case 2: lba = track->end_lba - 8; break;
        default: break;
        }
#if defined(CONFIG_DISCORA_CDDA_SEEK_VARY_OFFSET)
        // Keep the first-round reference locations and every read inside its track.
        uint64_t offset = (uint64_t)(lba - track->start_lba) + (uint64_t)(round - 1) * 997;
        lba = track->start_lba + (uint32_t)(offset % (span - 7));
#endif
        uint8_t first[32], repeat[32];
        const uint8_t *data;
        ESP_LOGI(TAG, "seek begin round=%u/%u step=%u/12 track=%u lba=%" PRIu32,
                 round, SEEK_ROUNDS, i + 1, track->number, lba);
#if defined(CONFIG_DISCORA_CDDA_SEEK_WAIT_MS) && CONFIG_DISCORA_CDDA_SEEK_WAIT_MS > 0
        ESP_LOGI(TAG, "seek settle step=%u wait_ms=%u", i + 1, CONFIG_DISCORA_CDDA_SEEK_WAIT_MS);
        int64_t until = esp_timer_get_time() + (int64_t)CONFIG_DISCORA_CDDA_SEEK_WAIT_MS * 1000;
        while (esp_timer_get_time() < until) {
            if (!s->service(s->context, 20)) return false;
        }
#endif
        int64_t started = esp_timer_get_time();
        if (!read_chunk(s, track, lba, 8, &data, &stats) ||
            mbedtls_sha256(data, 8 * PROBE_CD_SECTOR_SIZE, first, 0)) return false;
        int64_t seek_us = esp_timer_get_time() - started;
        if (!read_chunk(s, track, lba, 8, &data, &stats) ||
            mbedtls_sha256(data, 8 * PROBE_CD_SECTOR_SIZE, repeat, 0)) return false;
        if (memcmp(first, repeat, sizeof(first))) {
            ESP_LOGE(TAG, "seek repeat mismatch step=%u track=%u lba=%" PRIu32, i, track->number, lba);
            return false;
        }
        ESP_LOGI(TAG, "seek round=%u/%u step=%u/12 track=%u lba=%" PRIu32 " sectors=8 elapsed_us=%" PRIi64 " repeat=match",
                 round, SEEK_ROUNDS, i + 1, track->number, lba, seek_us);
        digest_log("seek sample", first);
    }
    ESP_LOGI(TAG, "seek complete rounds=%u positions=%u commands=%" PRIu32 " longest_read_us=%" PRIi64,
             SEEK_ROUNDS, 12 * SEEK_ROUNDS, stats.commands, stats.longest_us);
    return true;
}

static bool full_track_bench(const cdda_bench_source_t *s, size_t index)
{
    const probe_track_t *track = &s->toc->tracks[index];
    cdda_cursor_t cursor;
    uint32_t sectors = track->end_lba - track->start_lba;
    if (!cdda_cursor_init(&cursor, s->toc, index, track->start_lba, sectors)) return false;
    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);
    bool ok = mbedtls_sha256_starts(&sha, 0) == 0;
    read_stats_t stats = {0};
    int64_t started = esp_timer_get_time(), next_log = started + 10000000;
    ESP_LOGI(TAG, "full-track start track=%u lba=%" PRIu32 " sectors=%" PRIu32, track->number, track->start_lba, sectors);
    while (ok && cursor.remaining) {
        const probe_track_t *part;
        const uint8_t *data;
        uint32_t lba;
        uint8_t count;
        ok = cdda_cursor_next(&cursor, &part, &lba, &count) &&
             read_chunk(s, part, lba, count, &data, &stats) &&
             mbedtls_sha256_update(&sha, data, (size_t)count * PROBE_CD_SECTOR_SIZE) == 0 &&
             cdda_cursor_advance(&cursor, count);
        if (esp_timer_get_time() >= next_log) {
            ESP_LOGI(TAG, "full-track progress bytes=%" PRIu64 " remaining_sectors=%" PRIu32, stats.bytes, cursor.remaining);
            next_log += 10000000;
        }
    }
    uint8_t digest[32];
    if (ok) ok = mbedtls_sha256_finish(&sha, digest) == 0;
    mbedtls_sha256_free(&sha);
    int64_t elapsed = esp_timer_get_time() - started;
    ESP_LOGI(TAG, "full-track %s track=%u bytes=%" PRIu64 " commands=%" PRIu32
             " elapsed_us=%" PRIi64 " bytes_per_sec=%" PRIu64 " longest_read_us=%" PRIi64,
             ok ? "complete" : "failed", track->number, stats.bytes, stats.commands,
             elapsed, elapsed > 0 ? stats.bytes * 1000000 / elapsed : 0, stats.longest_us);
    if (ok) digest_log("full-track", digest);
    return ok;
}

typedef struct {
    pcm_buffer_t ring;
    uint64_t goal;
    uint64_t produced;
    uint64_t consumed;
    int64_t start_us;
    int64_t max_late_us;
    size_t low_active;
    size_t high;
    uint64_t missing;
    unsigned underruns;
    unsigned sink_stack_free;
    bool producer_done;
    bool stop;
    bool done;
    bool failed;
    uint8_t digest[32];
} stream_state_t;

static stream_state_t stream;
static portMUX_TYPE stream_lock = portMUX_INITIALIZER_UNLOCKED;

static void clock_sink(void *arg)
{
    stream_state_t *state = arg;
    uint8_t block[4096];
    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);
    bool failed = mbedtls_sha256_starts(&sha, 0) != 0;
    TickType_t tick = xTaskGetTickCount();
    const TickType_t period = pdMS_TO_TICKS(10) ? pdMS_TO_TICKS(10) : 1;
    int64_t expected_wake = state->start_us;
    while (!failed) {
        vTaskDelayUntil(&tick, period);
        expected_wake += (int64_t)period * portTICK_PERIOD_MS * 1000;
        int64_t now = esp_timer_get_time();
        uint64_t target = (uint64_t)(now - state->start_us) * PCM_RATE / 1000000 / 4 * 4;
        if (target > state->goal) target = state->goal;
        portENTER_CRITICAL(&stream_lock);
        uint64_t due = target - state->consumed;
        bool stop = state->stop;
        if (now - expected_wake > state->max_late_us) state->max_late_us = now - expected_wake;
        if (!stop && due > state->ring.used) {
            ++state->underruns;
            state->missing += due - state->ring.used;
            failed = true;
        }
        portEXIT_CRITICAL(&stream_lock);
        if (stop || failed) { failed = true; break; }
        while (due && !failed) {
            size_t take = due > sizeof(block) ? sizeof(block) : (size_t)due;
            portENTER_CRITICAL(&stream_lock);
            bool copied = pcm_buffer_read(&state->ring, block, take);
            if (copied) {
                state->consumed += take;
                if (!state->producer_done && state->ring.used < state->low_active) state->low_active = state->ring.used;
            }
            portEXIT_CRITICAL(&stream_lock);
            failed = !copied || mbedtls_sha256_update(&sha, block, take) != 0;
            due -= take;
        }
        if (target == state->goal) break;
    }
    if (mbedtls_sha256_finish(&sha, state->digest)) failed = true;
    mbedtls_sha256_free(&sha);
    unsigned stack_free = uxTaskGetStackHighWaterMark(NULL);
    portENTER_CRITICAL(&stream_lock);
    state->sink_stack_free = stack_free;
    state->failed = failed;
    state->done = true; // No access to the ring or state after publishing completion.
    portEXIT_CRITICAL(&stream_lock);
    vTaskDelete(NULL);
}

static bool buffered_bench(const cdda_bench_source_t *s, size_t index, uint32_t start_lba, unsigned seconds)
{
    if (seconds < 60 || seconds > 1800) return false;
    cdda_cursor_t cursor;
    if (!cdda_cursor_init(&cursor, s->toc, index, start_lba, seconds * 75)) {
        ESP_LOGE(TAG, "buffer test needs %u seconds of contiguous stereo audio; no looping", seconds);
        return false;
    }
    size_t capacity = BUFFER_SECTORS * PROBE_CD_SECTOR_SIZE;
    uint8_t *storage = heap_caps_malloc(capacity, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    if (!storage) { ESP_LOGE(TAG, "cannot allocate internal PCM ring"); return false; }
    memset(&stream, 0, sizeof(stream));
    pcm_buffer_init(&stream.ring, storage, capacity);
    stream.goal = (uint64_t)seconds * PCM_RATE;
    stream.low_active = capacity;
    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);
    bool ok = mbedtls_sha256_starts(&sha, 0) == 0;
    bool running = false, injected = false;
    int64_t pause_until = 0;
    read_stats_t stats = {0};
    int64_t prefill_start = esp_timer_get_time(), next_log = 0;
    size_t previous_index = index;
    unsigned transitions = 0;
    ESP_LOGI(TAG, "buffer start seconds=%u rate=%u capacity=%u prefill=%u software-clock-sink (no I2S)",
             seconds, PCM_RATE, (unsigned)capacity, PREFILL_SECTORS * PROBE_CD_SECTOR_SIZE);
    while (ok) {
        portENTER_CRITICAL(&stream_lock);
        bool done = stream.done;
        size_t free_bytes = capacity - stream.ring.used;
        portEXIT_CRITICAL(&stream_lock);
        if (done) break;
        if (INJECT_UNDERRUN && running && !injected && esp_timer_get_time() - stream.start_us >= 2000000) {
            injected = true;
            pause_until = esp_timer_get_time() + 1200000;
            ESP_LOGW(TAG, "negative control: pause producer 1200 ms; expect real clock-sink underrun");
        }
        if (injected && esp_timer_get_time() < pause_until) {
            if (!s->service(s->context, 10)) { ok = false; break; }
            continue;
        }
        if (running && esp_timer_get_time() - stream.start_us > ((int64_t)seconds + 35) * 1000000) { ok = false; break; }
        const probe_track_t *part;
        uint32_t lba;
        uint8_t count;
        if (cursor.remaining && cdda_cursor_next(&cursor, &part, &lba, &count) &&
            free_bytes >= (size_t)count * PROBE_CD_SECTOR_SIZE) {
            const uint8_t *data;
            ok = read_chunk(s, part, lba, count, &data, &stats) &&
                 mbedtls_sha256_update(&sha, data, (size_t)count * PROBE_CD_SECTOR_SIZE) == 0;
            if (!ok) break;
            size_t bytes = (size_t)count * PROBE_CD_SECTOR_SIZE;
            portENTER_CRITICAL(&stream_lock);
            ok = pcm_buffer_write(&stream.ring, data, bytes);
            if (ok) stream.produced += bytes;
            if (stream.ring.used > stream.high) stream.high = stream.ring.used;
            portEXIT_CRITICAL(&stream_lock);
            if (!ok || !cdda_cursor_advance(&cursor, count)) { ok = false; break; }
            if (previous_index != (size_t)(part - s->toc->tracks)) {
                ++transitions;
                previous_index = (size_t)(part - s->toc->tracks);
                ESP_LOGI(TAG, "buffer track transition=%u track=%u lba=%" PRIu32, transitions, part->number, lba);
            }
            if (!cursor.remaining) {
                portENTER_CRITICAL(&stream_lock);
                stream.producer_done = true;
                portEXIT_CRITICAL(&stream_lock);
            }
        } else if (!s->service(s->context, 5)) { ok = false; break; }
        if (!running && stream.produced >= PREFILL_SECTORS * PROBE_CD_SECTOR_SIZE) {
            stream.start_us = esp_timer_get_time();
            ESP_LOGI(TAG, "buffer prefill complete elapsed_us=%" PRIi64 " free_internal_heap=%" PRIu32,
                     stream.start_us - prefill_start, esp_get_free_internal_heap_size());
            if (xTaskCreate(clock_sink, "pcm_clock_sink", 6144, &stream, 4, NULL) != pdPASS) { ok = false; break; }
            running = true;
            next_log = stream.start_us + 10000000;
        }
        if (running && esp_timer_get_time() >= next_log) {
            portENTER_CRITICAL(&stream_lock);
            uint64_t produced = stream.produced, consumed = stream.consumed;
            size_t fill = stream.ring.used;
            unsigned underruns = stream.underruns;
            portEXIT_CRITICAL(&stream_lock);
            ESP_LOGI(TAG, "buffer progress elapsed_s=%" PRIi64 " produced=%" PRIu64 " consumed=%" PRIu64
                     " fill=%u underruns=%u", (esp_timer_get_time() - stream.start_us) / 1000000,
                     produced, consumed, (unsigned)fill, underruns);
            next_log += 10000000;
        }
    }
    if (!ok && running) {
        portENTER_CRITICAL(&stream_lock);
        stream.stop = true;
        portEXIT_CRITICAL(&stream_lock);
    }
    bool joined = !running;
    int64_t deadline = esp_timer_get_time() + 2000000;
    while (!joined && esp_timer_get_time() < deadline) {
        portENTER_CRITICAL(&stream_lock);
        joined = stream.done;
        portEXIT_CRITICAL(&stream_lock);
        if (!joined) vTaskDelay(1);
    }
    uint8_t digest[32] = {0};
    bool hash_ok = mbedtls_sha256_finish(&sha, digest) == 0;
    if (!hash_ok) ok = false;
    mbedtls_sha256_free(&sha);
    if (!joined) {
        // The consumer can still mutate its counters/digest. Do not read or free them.
        ESP_LOGE(TAG, "sink did not stop; ring quarantined until reboot (not freed)");
        return false;
    }
    bool negative_pass = INJECT_UNDERRUN && injected && ok && hash_ok && running &&
                         stream.failed && stream.underruns == 1 && stream.missing > 0 &&
                         stream.consumed < stream.goal && s->service(s->context, 0);
    ok = ok && joined && running && !stream.failed && !stream.underruns &&
         !cursor.remaining && stream.produced == stream.goal && stream.consumed == stream.goal &&
         memcmp(digest, stream.digest, sizeof(digest)) == 0;
    ESP_LOGI(TAG, "buffer %s seconds=%u produced=%" PRIu64 " consumed=%" PRIu64
             " underruns=%u missing_bytes=%" PRIu64 " low_active=%u high=%u longest_read_us=%" PRIi64
             " sink_max_late_us=%" PRIi64 " transitions=%u joined=%u sink_stack_free=%u",
             ok ? "complete" : "failed", seconds, stream.produced, stream.consumed, stream.underruns,
             stream.missing, (unsigned)stream.low_active, (unsigned)stream.high, stats.longest_us,
             stream.max_late_us, transitions, joined, stream.sink_stack_free);
    if (joined) {
        if (hash_ok) digest_log("buffer producer", digest);
        if (running) digest_log("buffer consumer", stream.digest);
        heap_caps_free(storage);
        stream.ring.data = NULL;
    }
    if (INJECT_UNDERRUN) {
        ESP_LOGI(TAG, "negative-control %s underruns=%u missing_bytes=%" PRIu64 " joined=%u ring_released=1; not a normal streaming PASS",
                 negative_pass ? "PASS" : "FAIL", stream.underruns, stream.missing, joined);
        return negative_pass;
    }
    return ok;
}

bool cdda_bench_run(const cdda_bench_source_t *s, unsigned seconds, bool include_seeks, bool include_full_track)
{
    if (!s || !s->toc || !s->read || !s->service) return false;
    if (INJECT_UNDERRUN && (include_seeks || include_full_track)) {
        ESP_LOGE(TAG, "negative control requires seeks and full-track stages disabled");
        return false;
    }
    size_t first = s->toc->track_count;
    for (size_t i = 0; i < s->toc->track_count; ++i) {
        if (!(s->toc->tracks[i].control & 0x0c)) { first = i; break; }
    }
    if (first == s->toc->track_count) return false;
#if defined(CONFIG_DISCORA_CDDA_SEEK_ONLY)
    {
        bool ok = include_seeks && seek_bench(s);
        ESP_LOGI(TAG, "extended bench %s seek_only=1 full_track=not_run buffer=not_run (not I2S playback)",
                 ok ? "complete" : "failed");
        return ok;
    }
#endif
    ESP_LOGI(TAG, "extended bench profile seeks=%s full_track=%s paced_seconds=%u",
             include_seeks ? "enabled" : "not_run", include_full_track ? "enabled" : "not_run", seconds);
    uint32_t start_lba = s->toc->tracks[first].start_lba;
    if (s->toc->tracks[first].end_lba - start_lba >= 158) start_lba += 150;
    if (!include_seeks && !include_full_track) {
        first = s->resume_index;
        start_lba = s->resume_lba;
        ESP_LOGI(TAG, "buffer sequential handoff index=%u lba=%" PRIu32, (unsigned)first, start_lba);
    }
    bool ok = (!include_seeks || seek_bench(s)) &&
              (!include_full_track || full_track_bench(s, first)) && buffered_bench(s, first, start_lba, seconds);
    ESP_LOGI(TAG, "extended bench %s negative_control=%u seeks=%s full_track=%s (software sink only; not I2S playback)",
             ok ? "complete" : "failed", INJECT_UNDERRUN, include_seeks ? "enabled" : "not_run", include_full_track ? "enabled" : "not_run");
    return ok;
}
