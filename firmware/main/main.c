#include "sdkconfig.h"
#include "usb_probe.h"
#include "audio_diag.h"
#include "audio_report.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

void app_main(void)
{
#if defined(CONFIG_DISCORA_AUDIO_DIAGNOSTIC) || defined(CONFIG_DISCORA_CD_PLAYER)
    if (!audio_report_start()) { ESP_LOGE("main", "audio report task allocation failed"); return; }
#endif
#if defined(CONFIG_DISCORA_AUDIO_DIAGNOSTIC)
    vTaskPrioritySet(NULL, 3); // Keep DMA feeding above the deferred UART reporter.
#endif
#if defined(CONFIG_DISCORA_AUDIO_DIAGNOSTIC)
    discora_audio_diag_run();
#else
    discora_usb_probe_run();
#endif
}
