#include <assert.h>
#include <stdio.h>
#include "usb_ab_test.h"

static void no_commands(const usb_ab_test_t *t)
{
    for (int c = 0; c < 32; c++) assert(!usb_ab_command_allowed(t, (probe_command_t)c));
}
int main(void)
{
    usb_ab_test_t t = {0};
    no_commands(&t);
    usb_ab_tick(&t, 1000000000, false, USB_AB_WINDOW_US);
    assert(t.phase == USB_AB_WAIT); // Duration starts on claim, not boot.
    usb_ab_attach(&t, 1000000000);
    usb_ab_tick(&t, 1000000000 + USB_AB_WINDOW_US - 1, false, USB_AB_WINDOW_US);
    assert(t.phase == USB_AB_ENUM_ONLY);
    no_commands(&t);
    usb_ab_tick(&t, 1000000000 + USB_AB_WINDOW_US, false, USB_AB_WINDOW_US);
    assert(t.phase == USB_AB_QUERIES);
    assert(usb_ab_command_allowed(&t, PROBE_INQUIRY));
    assert(usb_ab_command_allowed(&t, PROBE_TEST_UNIT_READY));
    assert(usb_ab_command_allowed(&t, PROBE_REQUEST_SENSE));
    assert(usb_ab_command_allowed(&t, PROBE_READ_TOC));
    assert(!usb_ab_command_allowed(&t, PROBE_READ_CD));
    assert(!usb_ab_command_allowed(&t, PROBE_READ_CDTEXT));
    assert(!usb_ab_command_allowed(&t, PROBE_EJECT));
    assert(!usb_ab_command_allowed(&t, PROBE_ALLOW_REMOVAL));
    usb_ab_tick(&t, 1000000000 + 2 * USB_AB_WINDOW_US - 1, false, USB_AB_WINDOW_US);
    assert(t.phase == USB_AB_QUERIES);
    usb_ab_tick(&t, 1000000000 + 2 * USB_AB_WINDOW_US, false, USB_AB_WINDOW_US);
    assert(t.phase == USB_AB_COMPLETE);
    usb_ab_attach(&t, 2000000000);
    usb_ab_fail(&t);
    usb_ab_tick(&t, 3000000000, true, USB_AB_WINDOW_US);
    assert(t.phase == USB_AB_COMPLETE);
    no_commands(&t);

    for (int phase = USB_AB_WAIT; phase <= USB_AB_QUERIES; phase++) {
        t = (usb_ab_test_t){.phase = phase, .phase_start_us = 10};
        usb_ab_fail(&t); // Loss wins over a simultaneous stage deadline.
        usb_ab_tick(&t, 10 + USB_AB_WINDOW_US, false, USB_AB_WINDOW_US);
        assert(t.phase == USB_AB_FAILED && t.failed_in == (usb_ab_phase_t)phase);
        usb_ab_attach(&t, 20 + USB_AB_WINDOW_US);
        no_commands(&t);
        assert(t.phase == USB_AB_FAILED);

        t = (usb_ab_test_t){.phase = phase};
        usb_ab_tick(&t, USB_AB_WINDOW_US, true, USB_AB_WINDOW_US);
        assert(t.phase == USB_AB_CANCELLED);
        usb_ab_attach(&t, 2 * USB_AB_WINDOW_US);
        no_commands(&t);
    }
    t = (usb_ab_test_t){0};
    usb_ab_attach(&t, 10);
    usb_ab_attach(&t, 20);
    assert(t.phase == USB_AB_FAILED); // Reconnect cannot restart or shorten stage A.
    no_commands(&t);
    t = (usb_ab_test_t){0};
    usb_ab_tick(&t, 1000, false, 0);
    assert(t.phase == USB_AB_WAIT);
    usb_ab_attach(&t, 1000);
    no_commands(&t); // Zero delay still requires a successful attach and client step.
    usb_ab_tick(&t, 1000, false, 0);
    assert(t.phase == USB_AB_QUERIES);
    usb_ab_tick(&t, 1000, false, 0);
    assert(t.phase == USB_AB_QUERIES); // Zero A wait must not shorten B.
    usb_ab_tick(&t, 1000 + USB_AB_WINDOW_US - 1, false, 0);
    assert(t.phase == USB_AB_QUERIES);
    usb_ab_tick(&t, 1000 + USB_AB_WINDOW_US, false, 0);
    assert(t.phase == USB_AB_COMPLETE);
    no_commands(&t);
    t = (usb_ab_test_t){0};
    usb_ab_attach(&t, 1000);
    usb_ab_tick(&t, 1000, true, 0);
    assert(t.phase == USB_AB_CANCELLED);
    no_commands(&t);
    t = (usb_ab_test_t){0};
    usb_ab_attach(&t, 1000);
    usb_ab_fail(&t);
    usb_ab_tick(&t, 1000, false, 0);
    assert(t.phase == USB_AB_FAILED);
    no_commands(&t);
    puts("USB A/B phase deadlines, command allowlist, loss and cancellation tests passed");
    return 0;
}
