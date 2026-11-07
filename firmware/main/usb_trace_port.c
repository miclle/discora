#include "sdkconfig.h"
#if defined(CONFIG_DISCORA_USB_DIAGNOSTICS)
#include "esp_idf_version.h"
#if ESP_IDF_VERSION_MAJOR != 5 || ESP_IDF_VERSION_MINOR != 4
#error "Revalidate the private HCD diagnostic hook before changing ESP-IDF 5.4"
#endif
#include "hcd.h"
#include "audio_report.h"
#include "esp_timer.h"
#include <inttypes.h>

// Link-time observation only: call the SDK handler once, return its event unchanged.
// Called by hub.c in daemon task context, after HCD releases its own locks.
// No ISR/register interception, SDK patch, extra reset or change to port policy.
hcd_port_event_t __real_hcd_port_handle_event(hcd_port_handle_t port);
hcd_port_event_t __wrap_hcd_port_handle_event(hcd_port_handle_t port)
{
    hcd_port_event_t event = __real_hcd_port_handle_event(port);
    const char *name;
    switch (event) {
    case HCD_PORT_EVENT_NONE: return event;
    case HCD_PORT_EVENT_CONNECTION: name="CONNECTION"; break;
    case HCD_PORT_EVENT_DISCONNECTION: name="DISCONNECTION"; break;
    case HCD_PORT_EVENT_ERROR: name="ERROR"; break;
    case HCD_PORT_EVENT_OVERCURRENT: name="OVERCURRENT"; break;
    default: name="UNKNOWN"; break;
    }
    audio_report("usb_diag", "root_event=%s code=%d observed_us=%" PRId64,
                 name, event, esp_timer_get_time());
    return event;
}
#endif
