#include "sdkconfig.h"
#include "usb_probe.h"
#include "audio_diag.h"

void app_main(void)
{
#if defined(CONFIG_DISCORA_AUDIO_DIAGNOSTIC)
    discora_audio_diag_run();
#else
    discora_usb_probe_run();
#endif
}
