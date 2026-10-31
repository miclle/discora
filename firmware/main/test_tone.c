#include "test_tone.h"

static const int16_t quarter[26] = {0, 257, 513, 768, 1019, 1266, 1508, 1744, 1973, 2195, 2408, 2611, 2804, 2986, 3156, 3314, 3458, 3589, 3706, 3808, 3896, 3967, 4023, 4064, 4088, 4096};

static int16_t sample(unsigned phase)
{
    phase %= 100;
    if (phase <= 25) return quarter[phase];
    if (phase <= 50) return quarter[50 - phase];
    if (phase <= 75) return (int16_t)-quarter[phase - 50];
    return (int16_t)-quarter[100 - phase];
}

bool test_tone_init(test_tone_t *tone, test_tone_mode_t mode)
{
    if (!tone || mode < TONE_LEFT || mode > TONE_SILENCE) return false;
    *tone = (test_tone_t){.mode = mode};
    return true;
}

static void put_le16(uint8_t *out, int16_t value)
{
    out[0] = (uint8_t)(uint16_t)value;
    out[1] = (uint8_t)((uint16_t)value >> 8);
}

bool test_tone_render(test_tone_t *tone, uint8_t *pcm, size_t size)
{
    if (!tone || !pcm || !size || size % 4 || tone->phase >= 100 ||
        tone->mode < TONE_LEFT || tone->mode > TONE_SILENCE) return false;
    for (size_t i = 0; i < size; i += 4) {
        int16_t left = tone->mode == TONE_LEFT || tone->mode == TONE_STEREO ? sample(tone->phase) : 0;
        int16_t right = tone->mode == TONE_RIGHT || tone->mode == TONE_STEREO ? sample(2 * tone->phase) : 0;
        put_le16(pcm + i, left);
        put_le16(pcm + i + 2, right);
        tone->phase = (tone->phase + 1) % 100;
    }
    return true;
}

const char *test_tone_name(test_tone_mode_t mode)
{
    switch (mode) {
    case TONE_LEFT: return "left-441Hz";
    case TONE_RIGHT: return "right-882Hz";
    case TONE_STEREO: return "stereo-441Hz-882Hz";
    case TONE_SILENCE: return "silence";
    default: return "invalid";
    }
}
