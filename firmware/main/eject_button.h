#pragma once
#include "sdkconfig.h"
#include <stdbool.h>
#if defined(CONFIG_DISCORA_EJECT_BUTTON)
bool discora_eject_button_start(void);
void discora_eject_button_enable(bool enabled);
bool discora_eject_button_take(void);
#else
static inline bool discora_eject_button_start(void) { return true; }
static inline void discora_eject_button_enable(bool enabled) { (void)enabled; }
static inline bool discora_eject_button_take(void) { return false; }
#endif
