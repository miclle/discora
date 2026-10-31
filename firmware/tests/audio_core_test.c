#include "audio_core.h"
#include "test_tone.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void state_test(void)
{
    uint8_t store[32], data[32], out[32];
    for (size_t i = 0; i < sizeof(data); ++i) data[i] = (uint8_t)i;
    audio_core_t c;
    assert(!audio_core_init(NULL, store, 32, 16));
    assert(!audio_core_init(&c, store, 32, 0));
    assert(!audio_core_init(&c, store, 32, 3));
    assert(!audio_core_init(&c, store, 32, 36));
    assert(audio_core_init(&c, store, 32, 16));
    uint32_t generation = c.generation;
    assert(c.state == AUDIO_STOPPED && !audio_core_pause(&c));
    assert(!audio_core_push(&c, generation, data, 16));
    assert(audio_core_play(&c) && c.state == AUDIO_PREFILL);
    assert(audio_core_push(&c, generation, data, 8) && c.state == AUDIO_PREFILL);
    assert(!audio_core_take(&c, out, 8) && !c.underruns && c.pcm.used == 8);
    assert(audio_core_pause(&c));
    assert(audio_core_push(&c, generation, data + 8, 8) && c.state == AUDIO_PAUSED);
    assert(!audio_core_take(&c, out, 8) && c.pcm.used == 16);
    assert(audio_core_play(&c) && c.state == AUDIO_PLAYING);
    assert(audio_core_take(&c, out, 8) && !memcmp(out, data, 8) && c.dequeued_bytes == 8);
    assert(audio_core_pause(&c));
    assert(audio_core_push(&c, generation, data + 16, 16) && c.state == AUDIO_PAUSED);
    assert(audio_core_play(&c));
    assert(audio_core_take(&c, out, 24) && !memcmp(out, data + 8, 24));
    assert(c.dequeued_bytes == 32 && c.pcm.used == 0);
    assert(!audio_core_take(&c, out, 3) && c.state == AUDIO_PLAYING && !c.underruns);
    assert(!audio_core_take(&c, out, 36) && c.state == AUDIO_PLAYING && !c.underruns);
    assert(!audio_core_take(&c, out, 4) && c.state == AUDIO_UNDERRUN && c.underruns == 1);
    assert(audio_core_push(&c, generation, data, 16) && c.state == AUDIO_UNDERRUN);
    assert(!audio_core_take(&c, out, 4));
    assert(audio_core_play(&c) && c.state == AUDIO_PLAYING);
    audio_core_stop(&c);
    assert(c.state == AUDIO_STOPPED && c.generation != generation && !c.pcm.used && !c.dequeued_bytes);
    assert(audio_core_play(&c));
    assert(!audio_core_push(&c, generation, data, 16)); // Late reply from the prior source.
    assert(audio_core_push(&c, c.generation, data, 32));
    assert(!audio_core_push(&c, c.generation, data, 4));
    assert(audio_core_take(&c, out, 32) && !memcmp(out, data, 32));
    generation = c.generation;
    audio_core_fault(&c);
    assert(c.state == AUDIO_FAULT && c.generation != generation && !audio_core_play(&c));
    assert(!audio_core_push(&c, c.generation, data, 16));
    audio_core_stop(&c);
    assert(audio_core_play(&c) && c.state == AUDIO_PREFILL);
    assert(!strcmp(audio_state_name(AUDIO_UNDERRUN), "underrun"));
    assert(!strcmp(audio_state_name((audio_state_t)99), "invalid"));
}

static int value(const uint8_t *p)
{
    int v = p[0] | ((unsigned)p[1] << 8);
    return v >= 32768 ? v - 65536 : v;
}

static void tone_test(void)
{
    test_tone_t tone;
    uint8_t left[800], right[800], stereo[800], silence[800], split[400];
    assert(test_tone_init(&tone, TONE_LEFT) && test_tone_render(&tone, left, sizeof(left)));
    assert(test_tone_init(&tone, TONE_RIGHT) && test_tone_render(&tone, right, sizeof(right)));
    assert(test_tone_init(&tone, TONE_STEREO) && test_tone_render(&tone, stereo, sizeof(stereo)));
    assert(test_tone_init(&tone, TONE_SILENCE) && test_tone_render(&tone, silence, sizeof(silence)));
    int sum_l = 0, sum_r = 0;
    for (size_t i = 0; i < 200; ++i) {
        assert(value(left + 4 * i + 2) == 0 && value(right + 4 * i) == 0);
        assert(!memcmp(stereo + 4 * i, left + 4 * i, 2));
        assert(!memcmp(stereo + 4 * i + 2, right + 4 * i + 2, 2));
        assert(!value(silence + 4 * i) && !value(silence + 4 * i + 2));
        int l = value(left + 4 * i), r = value(right + 4 * i + 2);
        assert(l >= -4096 && l <= 4096 && r >= -4096 && r <= 4096);
        sum_l += l; sum_r += r;
        if (i >= 100) assert(!memcmp(left + 4 * i, left + 4 * (i - 100), 4));
        if (i >= 50) assert(!memcmp(right + 4 * i, right + 4 * (i - 50), 4));
    }
    assert(!sum_l && !sum_r);
    assert(value(left + 4 * 25) == 4096 && value(left + 4 * 75) == -4096);
    assert(left[8] == 1 && left[9] == 2); // +513, explicit little endian.
    assert(left[300] == 0 && left[301] == 0xf0); // -4096, two's complement.
    assert(test_tone_init(&tone, TONE_LEFT));
    assert(test_tone_render(&tone, split, 17 * 4));
    assert(test_tone_render(&tone, split + 17 * 4, 83 * 4));
    assert(!memcmp(split, left, sizeof(split)));
    assert(!test_tone_render(&tone, split, 3) && tone.phase == 0);
    assert(!test_tone_render(&tone, split, 0));
    assert(!test_tone_render(NULL, split, 4));
    assert(!test_tone_init(&tone, (test_tone_mode_t)99));
    assert(!test_tone_init(NULL, TONE_LEFT));
}

int main(void)
{
    state_test();
    tone_test();
    puts("PASS: prefill/pause/stop/underrun/fault, stale-generation rejection and PCM16LE diagnostic L/R tones (offline)");
    return 0;
}
