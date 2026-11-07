#pragma once
#include <stddef.h>
#include <stdint.h>

// Interleaved PCM16LE, whole stereo frames; gain is 1..100 percent from Kconfig.
static inline void pcm_gain(uint8_t *pcm, size_t size, unsigned percent)
{
    if (percent == 100) return;
    for (size_t i = 0; i < size; i += 2) {
        uint16_t raw = (uint16_t)pcm[i] | ((uint16_t)pcm[i + 1] << 8);
        int32_t sample = raw >= 32768 ? (int32_t)raw - 65536 : raw;
        uint16_t scaled = (uint16_t)(sample * (int32_t)percent / 100);
        pcm[i] = scaled & 255;
        pcm[i + 1] = scaled >> 8;
    }
}
