#include "audio_i2s.h"

_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "ISR counters require lock-free unsigned atomics");
// ISR: counters only. A completion can contain auto-cleared silence, not necessarily PCM.
static bool sent(i2s_chan_handle_t channel, i2s_event_data_t *event, void *user)
{
    (void)channel;
    audio_i2s_t *out = user;
    atomic_fetch_add_explicit(&out->dma_blocks, 1, memory_order_relaxed);
    if (event->size != AUDIO_BLOCK_BYTES)
        atomic_fetch_add_explicit(&out->unexpected_dma_sizes, 1, memory_order_relaxed);
    return false;
}
static bool overflow(i2s_chan_handle_t channel, i2s_event_data_t *event, void *user)
{
    (void)channel; (void)event;
    audio_i2s_t *out = user;
    atomic_fetch_add_explicit(&out->event_overflows, 1, memory_order_relaxed);
    return false;
}

static bool safe_pin(int pin)
{
    // Restrict this board's first diagnostic to exposed GPIO1/2/4..18.
    // USB19/20, UART43/44, memory pins, straps and RGB remain outside the set.
    return pin >= 1 && pin <= 18 && pin != 3;
}

esp_err_t audio_i2s_open(audio_i2s_t *out, int bclk, int lrck, int data)
{
    if (!out || !safe_pin(bclk) || !safe_pin(lrck) || !safe_pin(data) ||
        bclk == lrck || bclk == data || lrck == data) return ESP_ERR_INVALID_ARG;
    if (out->channel) return ESP_ERR_INVALID_STATE;
    i2s_chan_config_t channel = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);
    channel.dma_desc_num = AUDIO_DMA_BLOCKS;
    channel.dma_frame_num = AUDIO_BLOCK_FRAMES;
    channel.auto_clear = true;
    esp_err_t err = i2s_new_channel(&channel, &out->channel, NULL);
    if (err != ESP_OK) return err;
    const i2s_std_config_t std = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(44100),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {.mclk = I2S_GPIO_UNUSED, .bclk = bclk, .ws = lrck,
                     .dout = data, .din = I2S_GPIO_UNUSED},
    };
    err = i2s_channel_init_std_mode(out->channel, &std);
    if (err != ESP_OK) {
        if (i2s_del_channel(out->channel) == ESP_OK) out->channel = NULL;
        return err;
    }
    i2s_chan_info_t info;
    err = i2s_channel_get_info(out->channel, &info);
    if (err == ESP_OK && info.total_dma_buf_size != AUDIO_PRELOAD_BYTES) err = ESP_ERR_INVALID_SIZE;
    if (err == ESP_OK) {
        const i2s_event_callbacks_t callbacks = {.on_sent=sent, .on_send_q_ovf=overflow};
        err = i2s_channel_register_event_callback(out->channel, &callbacks, out);
    }
    if (err != ESP_OK) audio_i2s_close(out);
    else ++out->opens;
    return err;
}

esp_err_t audio_i2s_start(audio_i2s_t *out, const uint8_t *pcm, size_t size)
{
    if (!out || !out->channel || out->running || !pcm || !size || size % 4 || size > AUDIO_PRELOAD_BYTES) return ESP_ERR_INVALID_ARG;
    size_t loaded = 0;
    esp_err_t err = i2s_channel_preload_data(out->channel, pcm, size, &loaded);
    out->submitted_pcm += loaded;
    if (err != ESP_OK) { ++out->write_errors; return err; }
    if (loaded != size) { ++out->write_errors; return ESP_ERR_INVALID_SIZE; }
    if (size < AUDIO_PRELOAD_BYTES) {
        static const uint8_t silence[AUDIO_PRELOAD_BYTES];
        loaded = 0;
        err = i2s_channel_preload_data(out->channel, silence, AUDIO_PRELOAD_BYTES - size, &loaded);
        out->padding_bytes += loaded;
        if (err != ESP_OK) { ++out->write_errors; return err; }
        if (loaded != AUDIO_PRELOAD_BYTES - size) { ++out->write_errors; return ESP_ERR_INVALID_SIZE; }
    }
    err = i2s_channel_enable(out->channel);
    if (err == ESP_OK) out->running = true;
    else ++out->write_errors;
    return err;
}

esp_err_t audio_i2s_write(audio_i2s_t *out, const uint8_t *pcm, size_t size)
{
    if (!out || !out->running || !pcm || !size || size % 4) return ESP_ERR_INVALID_ARG;
    size_t written = 0;
    esp_err_t err = i2s_channel_write(out->channel, pcm, size, &written, 25);
    out->submitted_pcm += written;
    if (err == ESP_OK && written != size) err = ESP_ERR_INVALID_SIZE;
    if (err != ESP_OK) ++out->write_errors;
    return err;
}

esp_err_t audio_i2s_close(audio_i2s_t *out)
{
    if (!out) return ESP_ERR_INVALID_ARG;
    if (!out->channel) return ESP_OK;
    if (out->running) {
        esp_err_t err = i2s_channel_disable(out->channel);
        if (err != ESP_OK) return err;
        out->running = false;
    }
    esp_err_t err = i2s_del_channel(out->channel);
    if (err == ESP_OK) { out->channel = NULL; out->drain_until = 0; ++out->closes; }
    return err;
}

void audio_i2s_eof(audio_i2s_t *out, int64_t now)
{
    if (out && out->running && !out->drain_until) out->drain_until = now + 50000;
}
bool audio_i2s_draining(const audio_i2s_t *out, int64_t now)
{
    return out && out->running && out->drain_until && now < out->drain_until;
}
