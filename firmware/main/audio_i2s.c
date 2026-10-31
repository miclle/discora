#include "audio_i2s.h"

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
    if (err != ESP_OK) audio_i2s_close(out);
    return err;
}

esp_err_t audio_i2s_start(audio_i2s_t *out, const uint8_t *pcm, size_t size)
{
    if (!out || !out->channel || out->running || !pcm || size != AUDIO_PRELOAD_BYTES) return ESP_ERR_INVALID_ARG;
    size_t loaded = 0;
    esp_err_t err = i2s_channel_preload_data(out->channel, pcm, size, &loaded);
    if (err != ESP_OK) return err;
    if (loaded != size) return ESP_ERR_INVALID_SIZE;
    err = i2s_channel_enable(out->channel);
    if (err == ESP_OK) out->running = true;
    return err;
}

esp_err_t audio_i2s_write(audio_i2s_t *out, const uint8_t *pcm, size_t size)
{
    if (!out || !out->running || !pcm || !size || size % 4) return ESP_ERR_INVALID_ARG;
    size_t written = 0;
    esp_err_t err = i2s_channel_write(out->channel, pcm, size, &written, 25);
    if (err == ESP_OK && written != size) err = ESP_ERR_INVALID_SIZE;
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
    if (err == ESP_OK) out->channel = NULL;
    return err;
}
