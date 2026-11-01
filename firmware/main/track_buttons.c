#include "track_buttons.h"
#if defined(CONFIG_DISCORA_TRACK_BUTTONS)
#include "track_buttons_core.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"

#if defined(CONFIG_DISCORA_CD_PLAYER_I2S) && (CONFIG_DISCORA_I2S_BCLK == 8 || CONFIG_DISCORA_I2S_LRCK == 8 || CONFIG_DISCORA_I2S_DATA == 8 || CONFIG_DISCORA_I2S_BCLK == 9 || CONFIG_DISCORA_I2S_LRCK == 9 || CONFIG_DISCORA_I2S_DATA == 9)
#error "GPIO8/9 are reserved for track buttons; move I2S pins or disable DISCORA_TRACK_BUTTONS"
#endif
enum { PREV_GPIO = 8, NEXT_GPIO = 9 };
static track_buttons_core_t buttons;
void discora_track_buttons_reset(void)
{
    track_buttons_init(&buttons, esp_timer_get_time() / 1000);
}
bool discora_track_buttons_start(void)
{
    discora_track_buttons_reset();
    const gpio_config_t config = {
        .pin_bit_mask = (1ULL << PREV_GPIO) | (1ULL << NEXT_GPIO), .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&config);
    if (err != ESP_OK) {
        ESP_LOGE("track_buttons", "GPIO setup failed: %s", esp_err_to_name(err));
        return false;
    }
    ESP_LOGI("track_buttons", "prev=GPIO%d next=GPIO%d active-low internal pull-up; debounce=30ms; release before press", PREV_GPIO, NEXT_GPIO);
    return true;
}
int discora_track_buttons_poll(bool available)
{
    return track_buttons_sample(&buttons, available, gpio_get_level(PREV_GPIO) == 0,
                                gpio_get_level(NEXT_GPIO) == 0, esp_timer_get_time() / 1000);
}
#endif
