#pragma once
#include "sdkconfig.h"

// Runs the native USB Host daemon and a single serialized, read-only BOT client.
void discora_usb_probe_run(void);

#if defined(CONFIG_DISCORA_USB_ENUM_QUERY_TEST)
// Console task requests cancellation; the USB client observes it at a command boundary.
void discora_usb_probe_cancel_test(void);
#endif
