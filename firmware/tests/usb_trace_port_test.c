#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "hcd.h"
#include "audio_report.h"

static hcd_port_event_t next_event;
static int calls, reports, port;
static char line[384];
hcd_port_event_t __wrap_hcd_port_handle_event(hcd_port_handle_t handle);
hcd_port_event_t __real_hcd_port_handle_event(hcd_port_handle_t handle)
{
    assert(handle == &port);
    calls++;
    return next_event;
}
int64_t esp_timer_get_time(void) { return 3325555000LL; }
void audio_report(const char *tag, const char *format, ...)
{
    assert(strcmp(tag, "usb_diag") == 0);
    va_list ap;
    va_start(ap, format);
    int n = vsnprintf(line, sizeof(line), format, ap);
    va_end(ap);
    assert(n > 0 && (size_t)n < sizeof(line));
    reports++;
}
int main(void)
{
    const char *names[] = {NULL, "CONNECTION", "DISCONNECTION", "ERROR", "OVERCURRENT", "UNKNOWN"};
    for (int i = 0; i < 6; i++) {
        next_event = (hcd_port_event_t)i;
        assert(__wrap_hcd_port_handle_event(&port) == next_event);
        assert(calls == i + 1); // Exactly one real handler invocation, even for unknown events.
        assert(reports == i); // NONE does not generate output.
        if (i) {
            assert(strstr(line, names[i]));
            assert(strstr(line, "observed_us=3325555000"));
        }
    }
    puts("USB root-port observation forwarding tests passed");
    return 0;
}
