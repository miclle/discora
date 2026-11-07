#pragma once
// Only the private IDF 5.4 root-port API used by the observation wrapper.
typedef void *hcd_port_handle_t;
typedef enum {
    HCD_PORT_EVENT_NONE, HCD_PORT_EVENT_CONNECTION, HCD_PORT_EVENT_DISCONNECTION,
    HCD_PORT_EVENT_ERROR, HCD_PORT_EVENT_OVERCURRENT
} hcd_port_event_t;
