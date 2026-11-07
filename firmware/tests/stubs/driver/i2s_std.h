#pragma once
// Host-only IDF API surface. No electrical/timing simulation.
#include <stdbool.h>
#include <stddef.h>
#include "esp_err.h"
enum { I2S_NUM_AUTO=0, I2S_ROLE_MASTER=1, I2S_DATA_BIT_WIDTH_16BIT=16, I2S_SLOT_MODE_STEREO=2, I2S_GPIO_UNUSED=-1 };
typedef void *i2s_chan_handle_t;
typedef struct { int dma_desc_num, dma_frame_num; bool auto_clear; } i2s_chan_config_t;
typedef struct { unsigned sample_rate_hz; } i2s_std_clk_config_t;
typedef struct { int bits, mode, slot_bit_width, ws_width; } i2s_std_slot_config_t;
typedef struct { i2s_std_clk_config_t clk_cfg; i2s_std_slot_config_t slot_cfg;
    struct { int mclk,bclk,ws,dout,din; } gpio_cfg; } i2s_std_config_t;
typedef struct { size_t total_dma_buf_size; } i2s_chan_info_t;
#define I2S_CHANNEL_DEFAULT_CONFIG(n,r) ((i2s_chan_config_t){0})
#define I2S_STD_CLK_DEFAULT_CONFIG(rate) { .sample_rate_hz=(rate) }
#define I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(b,m) { .bits=(b),.mode=(m) }
esp_err_t i2s_new_channel(const i2s_chan_config_t *, i2s_chan_handle_t *, i2s_chan_handle_t *);
esp_err_t i2s_channel_init_std_mode(i2s_chan_handle_t, const i2s_std_config_t *);
esp_err_t i2s_del_channel(i2s_chan_handle_t);
esp_err_t i2s_channel_get_info(i2s_chan_handle_t, i2s_chan_info_t *);
esp_err_t i2s_channel_preload_data(i2s_chan_handle_t, const void *, size_t, size_t *);
esp_err_t i2s_channel_enable(i2s_chan_handle_t);
esp_err_t i2s_channel_disable(i2s_chan_handle_t);
esp_err_t i2s_channel_write(i2s_chan_handle_t, const void *, size_t, size_t *, unsigned);

typedef struct { size_t size; void *data; } i2s_event_data_t;
typedef bool (*i2s_isr_callback_t)(i2s_chan_handle_t, i2s_event_data_t *, void *);
typedef struct { i2s_isr_callback_t on_sent, on_send_q_ovf; } i2s_event_callbacks_t;
esp_err_t i2s_channel_register_event_callback(i2s_chan_handle_t, const i2s_event_callbacks_t *, void *);
