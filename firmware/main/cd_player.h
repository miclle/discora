#pragma once
#include "cd_player_core.h"
bool discora_cd_player_start(void);
bool discora_cd_player_snapshot(cd_player_status_t *status);
void discora_cd_player_media(const probe_toc_t *toc);
void discora_cd_player_unavailable(void);
// True only after the output owner closed its adapter with media unavailable.
bool discora_cd_player_quiescent(void);
bool discora_cd_player_request(cd_player_read_t *request);
void discora_cd_player_complete(const cd_player_read_t *request, bool ok, const uint8_t *data, size_t size);
