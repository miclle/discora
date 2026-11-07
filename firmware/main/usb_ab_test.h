#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "probe_protocol.h"

// One A/B observation per boot; only the USB client task owns this state.
typedef enum {
    USB_AB_WAIT, USB_AB_ENUM_ONLY, USB_AB_QUERIES,
    USB_AB_COMPLETE, USB_AB_FAILED, USB_AB_CANCELLED
} usb_ab_phase_t;
typedef struct {
    usb_ab_phase_t phase, failed_in;
    int64_t phase_start_us;
} usb_ab_test_t;
#define USB_AB_WINDOW_US INT64_C(120000000)

static inline const char *usb_ab_name(usb_ab_phase_t phase)
{
    switch (phase) {
    case USB_AB_WAIT: return "waiting";
    case USB_AB_ENUM_ONLY: return "enum_only";
    case USB_AB_QUERIES: return "queries";
    case USB_AB_COMPLETE: return "complete";
    case USB_AB_FAILED: return "failed";
    case USB_AB_CANCELLED: return "cancelled";
    default: return "invalid";
    }
}
static inline bool usb_ab_terminal(const usb_ab_test_t *t)
{
    return t->phase >= USB_AB_COMPLETE;
}
static inline void usb_ab_fail(usb_ab_test_t *t)
{
    if (usb_ab_terminal(t)) return;
    t->failed_in = t->phase;
    t->phase = USB_AB_FAILED;
}
static inline void usb_ab_attach(usb_ab_test_t *t, int64_t now)
{
    if (usb_ab_terminal(t)) return;
    if (t->phase != USB_AB_WAIT) { usb_ab_fail(t); return; }
    t->phase = USB_AB_ENUM_ONLY;
    t->phase_start_us = now;
}
static inline void usb_ab_tick(usb_ab_test_t *t, int64_t now, bool cancel, int64_t enum_wait_us)
{
    if (usb_ab_terminal(t)) return;
    if (cancel) { t->phase = USB_AB_CANCELLED; return; }
    int64_t window = t->phase == USB_AB_ENUM_ONLY ? enum_wait_us : USB_AB_WINDOW_US;
    if (now - t->phase_start_us < window) return;
    if (t->phase == USB_AB_ENUM_ONLY) {
        t->phase = USB_AB_QUERIES;
        t->phase_start_us = now;
    } else if (t->phase == USB_AB_QUERIES) {
        t->phase = USB_AB_COMPLETE;
    }
}
static inline bool usb_ab_command_allowed(const usb_ab_test_t *t, probe_command_t command)
{
    // Finish the current query/sense chain before tick closes the window.
    if (t->phase != USB_AB_QUERIES) return false;
    return command == PROBE_INQUIRY || command == PROBE_TEST_UNIT_READY ||
           command == PROBE_REQUEST_SENSE || command == PROBE_READ_TOC;
}
