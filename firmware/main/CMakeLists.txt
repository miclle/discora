idf_component_register(
    SRCS "main.c" "usb_probe.c" "probe_protocol.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES usb esp_timer esp_app_format esp_system
)
