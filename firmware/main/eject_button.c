#include "eject_button.h"
#if defined(CONFIG_DISCORA_EJECT_BUTTON)
#include "eject_button_core.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#if defined(CONFIG_DISCORA_CD_PLAYER_I2S) && (CONFIG_DISCORA_I2S_BCLK == 7 || CONFIG_DISCORA_I2S_LRCK == 7 || CONFIG_DISCORA_I2S_DATA == 7)
#error "GPIO7 is reserved for eject; move I2S pins or disable DISCORA_EJECT_BUTTON"
#endif
static eject_button_core_t button;
static void button_task(void *arg)
{
    (void)arg;
    for (;;) {
        if (eject_button_sample(&button, gpio_get_level(EJECT_BUTTON_GPIO) == 0,
                                esp_timer_get_time() / 1000))
            ESP_LOGI("eject_button", "press accepted GPIO%d", EJECT_BUTTON_GPIO);
        vTaskDelay(pdMS_TO_TICKS(10) ? pdMS_TO_TICKS(10) : 1);
    }
}
bool discora_eject_button_start(void)
{
    eject_button_init(&button, esp_timer_get_time() / 1000);
    const gpio_config_t config = {
        .pin_bit_mask = 1ULL << EJECT_BUTTON_GPIO, .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&config);
    if (err != ESP_OK) {
        ESP_LOGE("eject_button", "GPIO setup failed: %s", esp_err_to_name(err));
        return false;
    }
    if (xTaskCreate(button_task, "eject_button", 2048, NULL, 2, NULL) != pdPASS) return false;
    ESP_LOGI("eject_button", "GPIO%d active-low internal pull-up; debounce=30ms; release before press", EJECT_BUTTON_GPIO);
    return true;
}
void discora_eject_button_enable(bool enabled) { eject_button_enable(&button, enabled); }
bool discora_eject_button_take(void) { return eject_button_take(&button); }
#endif
