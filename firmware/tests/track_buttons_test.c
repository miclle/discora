#include "track_buttons_core.h"
#include "cd_player_core.h"
#include <assert.h>
#include <stdio.h>

static track_buttons_core_t buttons;
static cd_player_core_t player;
static uint8_t storage[16 * PROBE_CD_SECTOR_SIZE], data[8 * PROBE_CD_SECTOR_SIZE];
static int64_t now;
static unsigned events;
static bool sample_keys(bool prev, bool next, bool play, int ms)
{
    now += ms;
    int direction = track_buttons_sample(&buttons, player.media && player.audio.state != AUDIO_FAULT,
                                         prev, next, play, now);
    if (direction) ++events;
    return direction == PLAYER_BUTTON_TOGGLE ? cd_player_toggle(&player) :
           direction && cd_player_step(&player, direction);
}
static bool sample(bool prev, bool next, int ms) { return sample_keys(prev, next, false, ms); }
static void release(void)
{
    assert(!sample(false, false, 10));
    assert(!sample(false, false, 30));
}
static bool press(int direction)
{
    assert(!sample(direction < 0, direction > 0, 10));
    assert(!sample(direction < 0, direction > 0, 29));
    return sample(direction < 0, direction > 0, 1);
}
int main(void)
{
    probe_toc_t toc = {.track_count=4, .tracks={
        {.number=1, .start_lba=0, .end_lba=16},
        {.number=2, .control=4, .start_lba=16, .end_lba=32},
        {.number=3, .start_lba=32, .end_lba=48},
        {.number=4, .start_lba=48, .end_lba=64},
    }};
    assert(cd_player_init(&player, storage, sizeof(storage), sizeof(data)));
    assert(cd_player_media(&player, &toc));
    track_buttons_init(&buttons, now);
    assert(!sample(false, true, 5000) && events == 0); // Boot-held never navigates.
    release();
    assert(!press(-1) && events == 1 && player.index == 0); // First-track boundary.
    release();
    assert(!sample(false, true, 10));
    assert(!sample(false, false, 10));
    assert(!sample(false, true, 10));
    assert(!sample(false, true, 29));
    assert(sample(false, true, 1) && events == 2 && player.index == 2); // Bounce; skip data.
    assert(player.audio.state == AUDIO_PREFILL && player.next_lba == 32);
    assert(!sample(false, true, 5000) && events == 2); // No autorepeat.

    cd_player_read_t old;
    assert(cd_player_request(&player, &old));
    assert(cd_player_complete(&player, &old, true, data, sizeof(data)));
    assert(cd_player_play_disc(&player) && cd_player_request(&player, &old));
    uint32_t generation = player.audio.generation;
    release(); assert(press(1) && player.index == 3 && player.continuous);
    assert(player.audio.generation != generation && !player.audio.pcm.used);
    assert(!cd_player_complete(&player, &old, true, data, sizeof(data)));
    assert(player.next_lba == 48 && player.audio.state == AUDIO_PREFILL);
    assert(cd_player_request(&player, &old));
    assert(cd_player_complete(&player, &old, true, data, sizeof(data)));
    generation = player.audio.generation;
    release(); assert(!press(1)); // Last-track rejection preserves current audio.
    assert(player.audio.generation == generation && player.audio.pcm.used == sizeof(data));
    assert(cd_player_pause(&player));
    release(); assert(press(-1) && player.index == 2 && player.audio.state == AUDIO_PAUSED);
    assert(player.continuous && !player.audio.pcm.used && !cd_player_request(&player, &old));

    release();
    unsigned before = events;
    assert(!sample(true, false, 10));
    assert(!sample(true, true, 10)); // Overlapping press before debounce completes.
    assert(!sample(true, true, 100));
    assert(!sample(false, true, 50));
    assert(!sample(false, true, 100));
    assert(!sample(false, false, 10));
    assert(!sample(true, false, 10)); // Release bounce must not unlock the chord.
    assert(!sample(true, false, 100) && events == before);
    release(); assert(press(-1) && player.index == 0);

    cd_player_lost(&player);
    release(); before = events;
    assert(!press(1) && events == before);
    assert(cd_player_media(&player, &toc));
    assert(!sample(false, true, 1000) && events == before); // No deferred action on insertion.
    release(); assert(press(1));
    cd_player_fault(&player);
    release(); before = events;
    assert(!press(-1) && events == before);
    cd_player_stop(&player);
    assert(!sample(true, false, 1000) && events == before); // Fault recovery while held.
    release(); assert(press(-1));

    // Media replacement between polls resets a partially debounced gesture in production.
    release(); before = events;
    assert(!sample(false, true, 10));
    assert(cd_player_media(&player, &toc));
    track_buttons_init(&buttons, now);
    assert(!sample(false, true, 1000) && events == before);
    release(); assert(press(1));
    // Front-panel play/pause, debounce, hold and three-key overlap.
    cd_player_stop(&player);
    track_buttons_init(&buttons, now);
    before = events;
    assert(!sample_keys(false, false, true, 1000) && events == before);
    release();
    assert(!sample_keys(false, false, true, 10));
    assert(!sample_keys(false, false, false, 10)); // Bounce is not a press.
    assert(!sample_keys(false, false, true, 10));
    assert(!sample_keys(false, false, true, 29));
    assert(sample_keys(false, false, true, 1));
    assert(player.continuous && player.audio.state == AUDIO_PREFILL);
    assert(!sample_keys(false, false, true, 2000));
    assert(player.audio.state == AUDIO_PREFILL);
    release();
    assert(!sample_keys(false, false, true, 10));
    assert(sample_keys(false, false, true, 30));
    assert(player.audio.state == AUDIO_PAUSED);
    release(); before = events;
    assert(!sample_keys(false, false, true, 10));
    assert(!sample_keys(false, true, true, 10));
    assert(!sample_keys(false, true, true, 100));
    assert(!sample_keys(false, false, true, 100));
    assert(!sample_keys(false, false, true, 100) && events == before);
    release();
    assert(!sample_keys(false, false, true, 10));
    assert(sample_keys(false, false, true, 30));
    assert(player.audio.state == AUDIO_PREFILL && player.continuous);
    cd_player_lost(&player); release(); before = events;
    assert(!sample_keys(false, false, true, 10));
    assert(!sample_keys(false, false, true, 30));
    assert(cd_player_media(&player, &toc));
    assert(!sample_keys(false, false, true, 1000) && events == before);
    release();
    cd_player_fault(&player);
    assert(!sample_keys(false, false, true, 10));
    assert(!sample_keys(false, false, true, 30));
    cd_player_stop(&player);
    assert(!sample_keys(false, false, true, 1000) && events == before);
    puts("PASS: play/pause/track debounce, hold/chord, media/fault gating, boundaries, paused navigation, continuous mode and stale PCM isolation (offline)");
}
