#include <assert.h>
#include <stdio.h>
#include "usb_trace.h"

static void phase(usb_trace_t *d, usb_trace_phase_t p, int64_t begin, int64_t end)
{
    usb_trace_transfer_begin(d, p, 0x81, 64, begin);
    assert(!usb_trace_callback(d, 0, 13, end - 1));
    usb_trace_transfer_end(d, 0, end);
}

int main(void)
{
    usb_trace_t d = {0};
    assert(!usb_trace_report_command(&d.last, false));
    usb_trace_begin(&d, 7, 42, 13, 245000, 8, 1000);
    phase(&d, USB_TRACE_CBW, 1000, 3000);
    phase(&d, USB_TRACE_DATA, 3000, 153000);
    phase(&d, USB_TRACE_CSW, 153000, 154000);
    // A retry and its control transfer must be included, not overwrite the first phase.
    phase(&d, USB_TRACE_CONTROL, 154000, 157000);
    phase(&d, USB_TRACE_CSW, 157000, 159000);
    usb_trace_end(&d, 0, 0, true, 160000);
    assert(d.last.phase_us[USB_TRACE_CBW] == 2000);
    assert(d.last.phase_us[USB_TRACE_DATA] == 150000);
    assert(d.last.phase_us[USB_TRACE_CSW] == 3000);
    assert(d.last.phase_us[USB_TRACE_CONTROL] == 3000);
    assert(usb_trace_report_command(&d.last, true));
    assert(d.last_read.track == 13 && d.last_read.lba == 245000);

    // A subsequent poll must retain the last READ CD, and fast success stays quiet.
    usb_trace_begin(&d, 0, 43, 0, 0, 0, 200000);
    usb_trace_end(&d, 0, 0, false, 299999);
    assert(!usb_trace_report_command(&d.last, true));
    assert(d.last_read.tag == 42 && d.last.tag == 43);
    d.last.end_us++;
    assert(usb_trace_report_command(&d.last, true));

    usb_trace_begin(&d, 7, 44, 13, 245008, 8, 300000);
    usb_trace_transfer_begin(&d, USB_TRACE_DATA, 0x81, 18816, 301000);
    // DEV_GONE captures the in-flight request before later completion changes it.
    usb_trace_t gone = d;
    usb_trace_transfer_end(&d, 263, 303000);
    usb_trace_end(&d, 2, -1, true, 303001);
    assert(gone.current.active && !gone.transfer.callback_seen);
    assert(gone.transfer.actual == -1 && gone.transfer.status == -1);
    assert(usb_trace_report_command(&d.last, false));
    assert(d.last.phase_us[USB_TRACE_DATA] == 2000);
    assert(usb_trace_callback(&d, 1, 0, 305000));
    assert(d.transfer.error == 263 && d.transfer.end_us == 303000);
    assert(d.transfer.callback_us == 305000 && d.transfer.callback_seen);
    assert(gone.transfer.end_us == 0 && gone.current.tag == 44);

    // Failed submit has no callback: actual bytes/status must remain unknown.
    usb_trace_begin(&d, 7, 45, 13, 245008, 8, 400000);
    usb_trace_transfer_begin(&d, USB_TRACE_CBW, 2, 31, 400001);
    usb_trace_transfer_end(&d, 259, 400002);
    usb_trace_end(&d, 2, -1, true, 400003);
    assert(!d.transfer.callback_seen && d.transfer.status == -1 && d.transfer.actual == -1);
    assert(usb_trace_report_command(&d.last, false));
    puts("USB diagnostic snapshots and timing tests passed");
    return 0;
}
