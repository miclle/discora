idf_component_register(
    SRCS "main.c" "usb_probe.c" "probe_protocol.c" "pcm_buffer.c" "cdda_cursor.c" "cdda_bench.c"
         "audio_core.c" "test_tone.c" "audio_i2s.c" "audio_diag.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES usb esp_timer esp_app_format esp_system mbedtls esp_driver_i2s
)
