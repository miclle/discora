#include "esp_log.h"
#include "esp_system.h"

static const char *TAG = "discora";

void app_main(void)
{
    ESP_LOGI(TAG, "Discora boot-only firmware skeleton");
    ESP_LOGI(TAG, "ESP-IDF: %s", esp_get_idf_version());
    ESP_LOGI(TAG, "Target: ESP32-S3");
    ESP_LOGW(TAG, "USB optical drive, CD-DA, I2S and CD writing are NOT implemented yet.");
}
