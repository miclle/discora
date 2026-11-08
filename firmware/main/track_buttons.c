#include "track_buttons.h"
#include "control_pins.h"
#if defined(CONFIG_DISCORA_TRACK_BUTTONS) || defined(CONFIG_DISCORA_PLAY_PAUSE_BUTTON)
#include "track_buttons_core.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"

#if defined(CONFIG_DISCORA_TRACK_BUTTONS)
enum { PREV_GPIO = CONFIG_DISCORA_PREV_GPIO, NEXT_GPIO = CONFIG_DISCORA_NEXT_GPIO };
#endif
static track_buttons_core_t buttons;
void discora_track_buttons_reset(void)
{
    track_buttons_init(&buttons, esp_timer_get_time() / 1000);
}
bool discora_track_buttons_start(void)
{
    discora_track_buttons_reset();
    uint64_t pins = 0;
#if defined(CONFIG_DISCORA_TRACK_BUTTONS)
    pins |= (1ULL << PREV_GPIO) | (1ULL << NEXT_GPIO);
#endif
#if defined(CONFIG_DISCORA_PLAY_PAUSE_BUTTON)
    pins |= 1ULL << CONFIG_DISCORA_PLAY_PAUSE_GPIO;
#endif
    const gpio_config_t config = {
        .pin_bit_mask = pins, .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&config);
    if (err != ESP_OK) {
        ESP_LOGE("track_buttons", "GPIO setup failed: %s", esp_err_to_name(err));
        return false;
    }
#if defined(CONFIG_DISCORA_TRACK_BUTTONS)
    ESP_LOGI("track_buttons", "prev=GPIO%d next=GPIO%d active-low internal pull-up; debounce=30ms; release before press", PREV_GPIO, NEXT_GPIO);
#endif
#if defined(CONFIG_DISCORA_PLAY_PAUSE_BUTTON)
    ESP_LOGI("track_buttons", "play/pause=GPIO%d active-low internal pull-up; debounce=30ms; release before press", CONFIG_DISCORA_PLAY_PAUSE_GPIO);
#endif
    return true;
}
int discora_track_buttons_poll(bool available)
{
    bool prev = false, next = false, play = false;
#if defined(CONFIG_DISCORA_TRACK_BUTTONS)
    prev = gpio_get_level(PREV_GPIO) == 0;
    next = gpio_get_level(NEXT_GPIO) == 0;
#endif
#if defined(CONFIG_DISCORA_PLAY_PAUSE_BUTTON)
    play = gpio_get_level(CONFIG_DISCORA_PLAY_PAUSE_GPIO) == 0;
#endif
    return track_buttons_sample(&buttons, available, prev, next, play, esp_timer_get_time() / 1000);
}
#endif
