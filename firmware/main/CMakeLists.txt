idf_component_register(
    SRCS "main.c" "usb_probe.c" "probe_protocol.c" "pcm_buffer.c" "cdda_cursor.c" "cdda_bench.c" "cdda_recovery.c" "transfer_wait.c" "eject_button.c" "button_core.c"
         "track_buttons.c" "track_buttons_core.c" "cd_player_core.c" "cd_player.c" "audio_core.c" "test_tone.c" "audio_i2s.c" "audio_report.c" "audio_diag.c" "oled_display.c" "oled_panel.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES usb esp_timer esp_app_format esp_system mbedtls esp_driver_i2s esp_driver_gpio esp_driver_i2c
)
