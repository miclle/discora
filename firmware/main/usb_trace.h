#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

// Client-task snapshots, never shared with the USB daemon or used to control IO.
typedef enum { USB_TRACE_CBW, USB_TRACE_DATA, USB_TRACE_CSW, USB_TRACE_CONTROL, USB_TRACE_PHASES } usb_trace_phase_t;
typedef struct {
    bool valid, active;
    unsigned command, track, sectors;
    uint32_t tag, lba;
    int64_t start_us, end_us;
    uint64_t phase_us[USB_TRACE_PHASES];
    int result, csw;
} usb_trace_command_t;
typedef struct {
    bool valid, callback_seen;
    usb_trace_phase_t phase;
    uint8_t endpoint;
    int requested, actual, status, error;
    int64_t start_us, callback_us, end_us;
} usb_trace_transfer_t;
typedef struct {
    usb_trace_command_t current, last, last_read;
    usb_trace_transfer_t transfer;
} usb_trace_t;

static inline const char *usb_trace_phase_name(usb_trace_phase_t p)
{
    switch (p) {
    case USB_TRACE_CBW: return "CBW";
    case USB_TRACE_DATA: return "DATA";
    case USB_TRACE_CSW: return "CSW";
    case USB_TRACE_CONTROL: return "CONTROL";
    default: return "UNKNOWN";
    }
}
static inline void usb_trace_begin(usb_trace_t *d, unsigned command, uint32_t tag,
                                   unsigned track, uint32_t lba, unsigned sectors, int64_t now)
{
    d->current = (usb_trace_command_t){.valid=true, .active=true, .command=command,
        .tag=tag, .track=track, .lba=lba, .sectors=sectors, .start_us=now, .result=-1, .csw=-1};
}
static inline void usb_trace_transfer_begin(usb_trace_t *d, usb_trace_phase_t phase,
                                           uint8_t ep, int bytes, int64_t now)
{
    d->transfer = (usb_trace_transfer_t){.valid=true, .phase=phase, .endpoint=ep,
        .requested=bytes, .actual=-1, .status=-1, .error=-1, .start_us=now};
}
static inline bool usb_trace_callback(usb_trace_t *d, int status, int actual, int64_t now)
{
    d->transfer.callback_seen=true;
    d->transfer.status=status;
    d->transfer.actual=actual;
    d->transfer.callback_us=now;
    return d->transfer.end_us != 0; // Late ownership return must not erase the timeout.
}
static inline void usb_trace_transfer_end(usb_trace_t *d, int error, int64_t now)
{
    d->transfer.error=error;
    d->transfer.end_us=now;
    if (d->current.active && d->transfer.phase < USB_TRACE_PHASES)
        d->current.phase_us[d->transfer.phase] += (uint64_t)(now-d->transfer.start_us);
}
static inline void usb_trace_end(usb_trace_t *d, int result, int csw, bool read_cd, int64_t now)
{
    d->current.active=false;
    d->current.result=result;
    d->current.csw=csw;
    d->current.end_us=now;
    d->last=d->current;
    if (read_cd) d->last_read=d->current;
}
static inline bool usb_trace_report_command(const usb_trace_command_t *c, bool passed)
{
    return c->valid && !c->active && (!passed || c->end_us-c->start_us >= 100000);
}
