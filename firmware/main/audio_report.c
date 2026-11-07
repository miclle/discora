#include "audio_report.h"
#include <stdarg.h>
#include <stdatomic.h>
#include <stdio.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

typedef struct { const char *tag; char text[384]; } report_t;
static QueueHandle_t reports;
static atomic_uint dropped;
static void report_task(void *arg)
{
    (void)arg;
    report_t item;
    for (;;) if (xQueueReceive(reports, &item, portMAX_DELAY) == pdTRUE)
        ESP_LOGI(item.tag, "%s", item.text);
}
bool audio_report_start(void)
{
    if (reports) return true;
    // EOF trace, optional verification, expanded status and sequence event can
    // arrive in one burst. Keep headroom without ever blocking the audio owner.
    reports = xQueueCreate(16, sizeof(report_t));
    if (!reports) return false;
    if (xTaskCreate(report_task,"audio_report",3072,NULL,1,NULL) != pdPASS) {
        vQueueDelete(reports); reports = NULL; return false;
    }
    return true;
}
void audio_report(const char *tag, const char *format, ...)
{
    report_t item = {.tag=tag};
    va_list args; va_start(args, format);
    int n = vsnprintf(item.text, sizeof(item.text), format, args);
    va_end(args);
    if (!reports || n < 0 || (size_t)n >= sizeof(item.text) || xQueueSend(reports, &item, 0) != pdTRUE)
        atomic_fetch_add_explicit(&dropped, 1, memory_order_relaxed);
}
uint32_t audio_report_dropped(void) { return atomic_load_explicit(&dropped, memory_order_relaxed); }
