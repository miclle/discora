#include "audio_core.h"

bool audio_core_init(audio_core_t *c, uint8_t *storage, size_t capacity, size_t prefill)
{
    if (!c || !prefill || prefill % 4 || prefill > capacity) return false;
    pcm_buffer_t ring;
    if (!pcm_buffer_init(&ring, storage, capacity)) return false;
    *c = (audio_core_t){.pcm = ring, .prefill = prefill, .generation = 1, .state = AUDIO_STOPPED};
    return true;
}

bool audio_core_play(audio_core_t *c)
{
    if (!c || !c->pcm.data || c->state == AUDIO_FAULT) return false;
    if (c->state == AUDIO_PLAYING || c->state == AUDIO_PREFILL) return true;
    c->state = c->pcm.used >= c->prefill ? AUDIO_PLAYING : AUDIO_PREFILL;
    return true;
}

bool audio_core_pause(audio_core_t *c)
{
    if (!c || c->state == AUDIO_STOPPED || c->state == AUDIO_FAULT) return false;
    c->state = AUDIO_PAUSED;
    return true;
}

void audio_core_stop(audio_core_t *c)
{
    if (!c) return;
    c->state = AUDIO_STOPPED;
    c->pcm.head = c->pcm.used = 0;
    c->dequeued_bytes = 0;
    if (++c->generation == 0) ++c->generation;
}

void audio_core_fault(audio_core_t *c)
{
    if (!c) return;
    audio_core_stop(c);
    c->state = AUDIO_FAULT;
}

bool audio_core_push(audio_core_t *c, uint32_t generation, const uint8_t *data, size_t size)
{
    if (!c || generation != c->generation || c->state == AUDIO_STOPPED || c->state == AUDIO_FAULT ||
        !pcm_buffer_write(&c->pcm, data, size)) return false;
    if (c->state == AUDIO_PREFILL && c->pcm.used >= c->prefill) c->state = AUDIO_PLAYING;
    return true;
}

bool audio_core_take(audio_core_t *c, uint8_t *data, size_t size)
{
    if (!c || !data || !size || size % 4 || size > c->pcm.capacity || c->state != AUDIO_PLAYING) return false;
    if (size > c->pcm.used) {
        ++c->underruns;
        c->state = AUDIO_UNDERRUN; // Explicit play is required to re-arm; never insert fake PCM.
        return false;
    }
    if (!pcm_buffer_read(&c->pcm, data, size)) return false;
    c->dequeued_bytes += size;
    return true;
}

const char *audio_state_name(audio_state_t state)
{
    switch (state) {
    case AUDIO_STOPPED: return "stopped";
    case AUDIO_PREFILL: return "prefill";
    case AUDIO_PLAYING: return "playing";
    case AUDIO_PAUSED: return "paused";
    case AUDIO_UNDERRUN: return "underrun";
    case AUDIO_FAULT: return "fault";
    default: return "invalid";
    }
}
