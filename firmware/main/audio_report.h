#pragma once
#include <stdbool.h>
#include <stdint.h>
// Task callers only; tag must have static lifetime. Reports never block the audio owner.
bool audio_report_start(void);
void audio_report(const char *tag, const char *format, ...) __attribute__((format(printf, 2, 3)));
uint32_t audio_report_dropped(void);
