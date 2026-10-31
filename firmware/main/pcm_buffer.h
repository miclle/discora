#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Byte counts are stereo PCM frames (4 bytes) aligned. Caller serializes access.
typedef struct {
    uint8_t *data;
    size_t capacity;
    size_t head;
    size_t used;
} pcm_buffer_t;

bool pcm_buffer_init(pcm_buffer_t *buffer, uint8_t *storage, size_t capacity);
bool pcm_buffer_write(pcm_buffer_t *buffer, const uint8_t *data, size_t size);
bool pcm_buffer_read(pcm_buffer_t *buffer, uint8_t *data, size_t size);
