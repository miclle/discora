#pragma once
#include <stdbool.h>
#include "esp_err.h"
typedef struct fake_counter *pcnt_unit_handle_t;
typedef struct fake_counter *pcnt_channel_handle_t;
typedef struct {
    int low_limit, high_limit;
    struct { bool accum_count; } flags;
} pcnt_unit_config_t;
typedef struct { int edge_gpio_num, level_gpio_num; } pcnt_chan_config_t;
enum { PCNT_CHANNEL_EDGE_ACTION_INCREASE, PCNT_CHANNEL_EDGE_ACTION_HOLD, PCNT_CHANNEL_LEVEL_ACTION_KEEP };
esp_err_t pcnt_new_unit(const pcnt_unit_config_t *, pcnt_unit_handle_t *);
esp_err_t pcnt_new_channel(pcnt_unit_handle_t, const pcnt_chan_config_t *, pcnt_channel_handle_t *);
esp_err_t pcnt_channel_set_edge_action(pcnt_channel_handle_t, int, int);
esp_err_t pcnt_channel_set_level_action(pcnt_channel_handle_t, int, int);
esp_err_t pcnt_unit_add_watch_point(pcnt_unit_handle_t, int);
esp_err_t pcnt_unit_enable(pcnt_unit_handle_t);
esp_err_t pcnt_unit_clear_count(pcnt_unit_handle_t);
esp_err_t pcnt_unit_start(pcnt_unit_handle_t);
esp_err_t pcnt_unit_stop(pcnt_unit_handle_t);
esp_err_t pcnt_unit_get_count(pcnt_unit_handle_t, int *);
