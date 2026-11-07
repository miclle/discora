idf_component_register(
    SRCS "main.c" "usb_probe.c" "usb_trace_port.c" "probe_protocol.c" "pcm_buffer.c" "cdda_cursor.c" "cdda_bench.c" "cdda_recovery.c" "transfer_wait.c" "eject_button.c" "button_core.c"
         "track_buttons.c" "track_buttons_core.c" "cd_player_core.c" "cd_player.c" "audio_core.c" "test_tone.c" "audio_i2s.c" "audio_report.c" "audio_diag.c" "audio_clock_probe.c" "oled_display.c" "oled_panel.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES usb esp_timer esp_app_format esp_system mbedtls esp_driver_i2s esp_driver_gpio esp_driver_i2c esp_driver_pcnt
)

if(CONFIG_DISCORA_USB_DIAGNOSTICS)
    idf_component_get_property(usb_dir usb COMPONENT_DIR)
    target_include_directories(${COMPONENT_LIB} PRIVATE "${usb_dir}/private_include")
    # USB is linked after main; force extraction of the observation wrapper.
    target_link_options(${COMPONENT_LIB} INTERFACE
        "-Wl,--wrap=hcd_port_handle_event" "-Wl,-u,__wrap_hcd_port_handle_event")
endif()
