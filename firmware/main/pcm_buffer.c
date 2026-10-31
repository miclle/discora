#include "pcm_buffer.h"
#include <string.h>

bool pcm_buffer_init(pcm_buffer_t *buffer, uint8_t *storage, size_t capacity)
{
    if (!buffer || !storage || !capacity || capacity % 4) {
        return false;
    }
    *buffer = (pcm_buffer_t){.data = storage, .capacity = capacity};
    return true;
}

static bool valid(const pcm_buffer_t *b, const void *data, size_t size)
{
    return b && b->data && b->capacity && b->capacity % 4 == 0 &&
           b->head < b->capacity && b->head % 4 == 0 && b->used % 4 == 0 && b->used <= b->capacity && data && size && size % 4 == 0;
}

bool pcm_buffer_write(pcm_buffer_t *b, const uint8_t *data, size_t size)
{
    if (!valid(b, data, size) || size > b->capacity - b->used) {
        return false;
    }
    size_t tail = (b->head + b->used) % b->capacity;
    size_t first = size < b->capacity - tail ? size : b->capacity - tail;
    memcpy(b->data + tail, data, first);
    memcpy(b->data, data + first, size - first);
    b->used += size;
    return true;
}

bool pcm_buffer_read(pcm_buffer_t *b, uint8_t *data, size_t size)
{
    if (!valid(b, data, size) || size > b->used) {
        return false;
    }
    size_t first = size < b->capacity - b->head ? size : b->capacity - b->head;
    memcpy(data, b->data + b->head, first);
    memcpy(data + first, b->data, size - first);
    b->head = (b->head + size) % b->capacity;
    b->used -= size;
    return true;
}
