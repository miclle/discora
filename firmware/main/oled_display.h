#pragma once
#include "sdkconfig.h"
#if defined(CONFIG_DISCORA_OLED)
void discora_oled_start(void);
#else
static inline void discora_oled_start(void) {}
#endif
