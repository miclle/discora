#include "oled_display.h"
#if defined(CONFIG_DISCORA_OLED)
#include "oled_panel.h"
#include "cd_player.h"
#include "driver/i2c_master.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#if defined(CONFIG_DISCORA_CD_PLAYER_I2S) && (CONFIG_DISCORA_I2S_BCLK == 10 || CONFIG_DISCORA_I2S_LRCK == 10 || CONFIG_DISCORA_I2S_DATA == 10 || CONFIG_DISCORA_I2S_BCLK == 11 || CONFIG_DISCORA_I2S_LRCK == 11 || CONFIG_DISCORA_I2S_DATA == 11)
#error "GPIO10/11 are reserved for OLED; move I2S pins or disable DISCORA_OLED"
#endif
static const char *TAG = "oled";
static esp_err_t last_error; // Display task is the sole I2C owner.
static bool write_panel(void *context, const uint8_t *bytes, size_t size)
{
    last_error = i2c_master_transmit((i2c_master_dev_handle_t)context, bytes, size, 50);
    return last_error == ESP_OK;
}
static void display_task(void *arg)
{
    (void)arg;
    i2c_master_bus_handle_t bus = NULL;
    i2c_master_dev_handle_t device = NULL;
    const i2c_master_bus_config_t config = {
        .i2c_port = -1, .sda_io_num = 10, .scl_io_num = 11,
        .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = false, // Module/external pull-ups must be 3.3V.
    };
    last_error = i2c_new_master_bus(&config, &bus);
    if (last_error != ESP_OK) goto done;
    const i2c_device_config_t panel = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = CONFIG_DISCORA_OLED_ADDRESS, .scl_speed_hz = 100000,
    };
    last_error = i2c_master_bus_add_device(bus, &panel, &device);
    if (last_error != ESP_OK) goto done;
    vTaskDelay(pdMS_TO_TICKS(100)); // Four-pin module owns reset/power-on circuitry.
    last_error = i2c_master_probe(bus, CONFIG_DISCORA_OLED_ADDRESS, 50);
    if (last_error != ESP_OK || !oled_panel_init(write_panel, device)) goto done;
    vTaskDelay(pdMS_TO_TICKS(100)); // SH1106 internal DC-DC stabilization.
    uint8_t frame[OLED_FRAME_BYTES];
    cd_player_status_t previous = {0};
    bool displayed = false;
    for (;;) {
        cd_player_status_t current;
        if (discora_cd_player_snapshot(&current) && (!displayed || current.media != previous.media ||
            current.track != previous.track || current.state != previous.state)) {
#if defined(CONFIG_DISCORA_CD_PLAYER_I2S)
            oled_render(frame, &current, true);
#else
            oled_render(frame, &current, false);
#endif
            if (!oled_panel_flush(write_panel, device, frame)) break;
            if (!displayed) {
                if (!oled_panel_on(write_panel, device)) break;
                ESP_LOGI(TAG, "SH1106 initialized SDA=GPIO10 SCL=GPIO11 address=0x%02x; physical display unverified", CONFIG_DISCORA_OLED_ADDRESS);
            }
            displayed = true;
            previous = current;
        }
        vTaskDelay(pdMS_TO_TICKS(200));
    }
done:
    ESP_LOGW(TAG, "display disabled until reboot: %s; player continues", esp_err_to_name(last_error));
    // Try to blank stale state after a partial transfer; one bounded attempt only.
    if (device) {
        const uint8_t off[] = {0x00, 0xae};
        (void)i2c_master_transmit(device, off, sizeof(off), 50);
        esp_err_t err = i2c_master_bus_rm_device(device);
        if (err != ESP_OK) { ESP_LOGE(TAG, "remove device: %s; bus retained", esp_err_to_name(err)); bus = NULL; }
    }
    if (bus) {
        esp_err_t err = i2c_del_master_bus(bus);
        if (err != ESP_OK) ESP_LOGE(TAG, "delete bus: %s", esp_err_to_name(err));
    }
    vTaskDelete(NULL);
}
void discora_oled_start(void)
{
    if (xTaskCreate(display_task, "oled", 4096, NULL, 1, NULL) != pdPASS)
        ESP_LOGW(TAG, "display task allocation failed; player continues");
}
#endif
