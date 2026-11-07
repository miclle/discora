#include "audio_clock_probe.h"
#include "driver/pulse_cnt.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "audio_report.h"
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

struct fake_counter { int gpio, watch; bool enabled, running, cleared; } units[2];
static int allocated, results;
static int64_t now;
static bool fail_setup, fail_start, fail_read;
static bool input[19];

int64_t esp_timer_get_time(void) { return now; }
esp_err_t gpio_pullup_dis(int gpio) { assert(gpio==4 || gpio==5); return ESP_OK; }
esp_err_t gpio_input_enable(int gpio) { input[gpio]=true; return ESP_OK; }
esp_err_t pcnt_new_unit(const pcnt_unit_config_t *c, pcnt_unit_handle_t *u)
{
    assert(allocated<2 && c->low_limit==-30000 && c->high_limit==30000 && c->flags.accum_count);
    if (fail_setup && allocated==1) return ESP_FAIL;
    *u=&units[allocated++]; return ESP_OK;
}
esp_err_t pcnt_new_channel(pcnt_unit_handle_t u, const pcnt_chan_config_t *c, pcnt_channel_handle_t *h)
{ assert(c->level_gpio_num==-1); u->gpio=c->edge_gpio_num; *h=u; return ESP_OK; }
esp_err_t pcnt_channel_set_edge_action(pcnt_channel_handle_t u, int rising, int falling)
{ assert(u && rising==PCNT_CHANNEL_EDGE_ACTION_INCREASE && falling==PCNT_CHANNEL_EDGE_ACTION_HOLD); return ESP_OK; }
esp_err_t pcnt_channel_set_level_action(pcnt_channel_handle_t u, int high, int low)
{ assert(u && high==PCNT_CHANNEL_LEVEL_ACTION_KEEP && low==PCNT_CHANNEL_LEVEL_ACTION_KEEP); return ESP_OK; }
esp_err_t pcnt_unit_add_watch_point(pcnt_unit_handle_t u, int limit)
{ assert(limit==30000 || limit==-30000); u->watch |= limit>0?1:2; return ESP_OK; }
esp_err_t pcnt_unit_enable(pcnt_unit_handle_t u) { assert(u->watch==3); u->enabled=true; return ESP_OK; }
esp_err_t pcnt_unit_clear_count(pcnt_unit_handle_t u)
{ assert(!u->running && u->enabled); u->cleared=true; return ESP_OK; }
esp_err_t pcnt_unit_start(pcnt_unit_handle_t u)
{ assert(u->cleared && input[u->gpio] && !u->running); if (fail_start && u==&units[1]) return ESP_FAIL; u->running=true; return ESP_OK; }
esp_err_t pcnt_unit_stop(pcnt_unit_handle_t u)
{ assert(u->running); u->running=false; return ESP_OK; }
esp_err_t pcnt_unit_get_count(pcnt_unit_handle_t u, int *n)
{ assert(!u->running); if (fail_read) return ESP_FAIL; *n=u==&units[0]?1411200:44100; return ESP_OK; }
void audio_report(const char *tag, const char *format, ...)
{
    assert(!strcmp(tag,"clock_probe")); char text[256]; va_list args;
    va_start(args,format); vsnprintf(text,sizeof(text),format,args); va_end(args);
    if (strstr(text," edges=")) { assert(strstr(text,"elapsed_us=1000000")); ++results; }
}
int main(int argc, char **argv)
{
    fail_setup=argc>1 && !strcmp(argv[1],"setup-error");
    fail_start=argc>1 && !strcmp(argv[1],"start-error");
    assert(audio_clock_probe_begin(19,5)==ESP_ERR_INVALID_ARG && allocated==0);
    audio_clock_probe_cancel();
    if (fail_setup || fail_start) {
        assert(audio_clock_probe_begin(4,5)==ESP_FAIL);
        assert(!units[0].running && !units[1].running && results==0);
        int before=allocated;
        assert(audio_clock_probe_begin(4,5)==ESP_ERR_INVALID_STATE && allocated==before);
        puts("PASS: clock probe partial setup/start failure is bounded and blocks retry (fake APIs)");
        return 0;
    }
    assert(audio_clock_probe_begin(4,5)==ESP_OK && allocated==2);
    assert(audio_clock_probe_begin(4,5)==ESP_ERR_INVALID_STATE);
    now=999999; audio_clock_probe_poll(); assert(results==0 && units[0].running);
    audio_clock_probe_cancel(); assert(results==0 && !units[0].running && !units[1].running);
    assert(audio_clock_probe_begin(6,5)==ESP_ERR_INVALID_ARG);
    input[4]=input[5]=false; // I2S reopen can clear input enable.
    assert(audio_clock_probe_begin(4,5)==ESP_OK && allocated==2 && input[4] && input[5]);
    now+=1000000; audio_clock_probe_poll(); assert(results==2 && !units[0].running && !units[1].running);
    audio_clock_probe_poll(); assert(results==2);
    assert(audio_clock_probe_begin(4,5)==ESP_OK); fail_read=true;
    now+=1000000; audio_clock_probe_poll();
    assert(results==2 && !units[0].running && !units[1].running);
    assert(audio_clock_probe_begin(4,5)==ESP_ERR_INVALID_STATE);
    puts("PASS: clock probe gate, cancellation, input re-enable, resource reuse and read failure (fake APIs, no electrical proof)");
}
