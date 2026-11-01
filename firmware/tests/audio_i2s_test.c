#include "audio_i2s.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static int token, new_error, init_error, info_error, del_error, enable_error, disable_error, write_error;
static size_t dma_size=AUDIO_PRELOAD_BYTES, short_load, short_write, loaded_total;
static uint8_t preload[AUDIO_PRELOAD_BYTES];
static bool enabled;
esp_err_t i2s_new_channel(const i2s_chan_config_t *c, i2s_chan_handle_t *h, i2s_chan_handle_t *rx)
{
    assert(!rx && c->dma_desc_num==4 && c->dma_frame_num==441 && c->auto_clear);
    if (!new_error) { *h=&token; loaded_total=0; memset(preload,0xcc,sizeof(preload)); }
    return new_error;
}
esp_err_t i2s_channel_init_std_mode(i2s_chan_handle_t h, const i2s_std_config_t *c)
{
    assert(h==&token && c->clk_cfg.sample_rate_hz==44100 && c->slot_cfg.bits==16 && c->slot_cfg.mode==2);
    assert(c->gpio_cfg.bclk==4 && c->gpio_cfg.ws==5 && c->gpio_cfg.dout==6 && c->gpio_cfg.mclk==-1);
    return init_error;
}
esp_err_t i2s_del_channel(i2s_chan_handle_t h) { assert(h==&token && !enabled); return del_error; }
esp_err_t i2s_channel_get_info(i2s_chan_handle_t h, i2s_chan_info_t *i) { assert(h==&token); i->total_dma_buf_size=dma_size; return info_error; }
esp_err_t i2s_channel_preload_data(i2s_chan_handle_t h, const void *p, size_t n, size_t *loaded)
{
    assert(h==&token && !enabled && loaded_total+n<=sizeof(preload));
    *loaded=n-short_load; memcpy(preload+loaded_total,p,*loaded);loaded_total+=*loaded;return ESP_OK;
}
esp_err_t i2s_channel_enable(i2s_chan_handle_t h) { assert(h==&token); if (!enable_error) enabled=true;return enable_error; }
esp_err_t i2s_channel_disable(i2s_chan_handle_t h) { assert(h==&token); if (!disable_error) enabled=false;return disable_error; }
esp_err_t i2s_channel_write(i2s_chan_handle_t h,const void *p,size_t n,size_t *written,unsigned timeout)
{ assert(h==&token && enabled && p && timeout==25); *written=n-short_write;return write_error; }
static void open_ok(audio_i2s_t *o) { assert(audio_i2s_open(o,4,5,6)==ESP_OK); }
int main(void)
{
    audio_i2s_t o={0}; uint8_t pcm[AUDIO_PRELOAD_BYTES]; memset(pcm,0x5a,sizeof(pcm));
    assert(audio_i2s_open(&o,19,5,6)==ESP_ERR_INVALID_ARG && !o.channel);
    new_error=ESP_FAIL;assert(audio_i2s_open(&o,4,5,6)==ESP_FAIL && !o.channel);new_error=0;
    init_error=ESP_FAIL;del_error=ESP_FAIL;
    assert(audio_i2s_open(&o,4,5,6)==ESP_FAIL && o.channel);
    assert(audio_i2s_open(&o,4,5,6)==ESP_ERR_INVALID_STATE);
    del_error=0;assert(audio_i2s_close(&o)==ESP_OK && !o.channel);init_error=0;
    dma_size=1;assert(audio_i2s_open(&o,4,5,6)==ESP_ERR_INVALID_SIZE && !o.channel);dma_size=AUDIO_PRELOAD_BYTES;
    info_error=ESP_FAIL;assert(audio_i2s_open(&o,4,5,6)==ESP_FAIL && !o.channel);info_error=0;
    open_ok(&o);short_load=4;assert(audio_i2s_start(&o,pcm,sizeof(pcm))==ESP_ERR_INVALID_SIZE && !o.running);
    short_load=0;assert(audio_i2s_close(&o)==ESP_OK);
    open_ok(&o);enable_error=ESP_FAIL;assert(audio_i2s_start(&o,pcm,sizeof(pcm))==ESP_FAIL && !o.running);
    enable_error=0;assert(audio_i2s_close(&o)==ESP_OK);
    open_ok(&o);assert(audio_i2s_start(&o,pcm,sizeof(pcm))==ESP_OK && o.running);
    short_write=4;assert(audio_i2s_write(&o,pcm,1764)==ESP_ERR_INVALID_SIZE);short_write=0;
    write_error=ESP_FAIL;assert(audio_i2s_write(&o,pcm,1764)==ESP_FAIL);write_error=0;
    assert(audio_i2s_write(&o,pcm,1176)==ESP_OK);
    disable_error=ESP_FAIL;assert(audio_i2s_close(&o)==ESP_FAIL && o.running && o.channel);
    disable_error=0;del_error=ESP_FAIL;assert(audio_i2s_close(&o)==ESP_FAIL && !o.running && o.channel);
    del_error=0;assert(audio_i2s_close(&o)==ESP_OK && !o.channel);
    // Pause/reopen owns a fresh DMA allocation; no stale preload is retained.
    open_ok(&o);assert(audio_i2s_start(&o,pcm,sizeof(pcm))==ESP_OK);
    assert(!memcmp(preload,pcm,sizeof(pcm)));assert(audio_i2s_close(&o)==ESP_OK);
    open_ok(&o);assert(audio_i2s_start(&o,pcm,1176)==ESP_OK);
    assert(loaded_total==AUDIO_PRELOAD_BYTES && !memcmp(preload,pcm,1176));
    for (size_t i=1176;i<sizeof(preload);++i) assert(preload[i]==0);
    audio_i2s_eof(&o,100);assert(audio_i2s_draining(&o,50099));
    audio_i2s_eof(&o,40000);assert(o.drain_until==50100); // Never extend a pending EOF.
    assert(!audio_i2s_draining(&o,50100) && o.running);
    assert(audio_i2s_close(&o)==ESP_OK && !o.drain_until);
    open_ok(&o);assert(audio_i2s_start(&o,pcm,sizeof(pcm))==ESP_OK);
    audio_i2s_eof(&o,100);assert(audio_i2s_close(&o)==ESP_OK); // Pause/stop bypasses drain.
    assert(!audio_i2s_draining(&o,101));
    puts("PASS: production I2S adapter with fake IDF calls; open/preload/enable/write/close failures and reopen (no hardware)");
}
