#include "oled_panel.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    unsigned calls, fail_at;
    bool pages;
    uint8_t ram[8][132];
    unsigned page, column;
} fake_bus_t;
static bool write_fake(void *context, const uint8_t *bytes, size_t size)
{
    fake_bus_t *bus = context;
    if (++bus->calls == bus->fail_at) return false;
    assert(size && (bytes[0] == 0 || bytes[0] == 0x40));
    if (!bus->pages) return true;
    if (bytes[0] == 0) {
        assert(size == 4 && (bytes[1] & 0xf8) == 0xb0);
        bus->page = bytes[1] & 7;
        bus->column = (bytes[2] & 15) | ((bytes[3] & 15) << 4);
    } else {
        assert(size == 129 && bus->column + size - 1 <= 132);
        memcpy(bus->ram[bus->page] + bus->column, bytes + 1, size - 1);
    }
    return true;
}
static uint8_t storage[16 * PROBE_CD_SECTOR_SIZE];
static void check_progress(void)
{
    cd_player_core_t player;
    uint8_t pcm[8 * PROBE_CD_SECTOR_SIZE] = {0};
    assert(cd_player_init(&player, storage, sizeof(storage), sizeof(pcm)));
    probe_toc_t toc = {.track_count = 2, .tracks = {
        {.number = 2, .start_lba = 500, .end_lba = 516},
        {.number = 7, .start_lba = 516, .end_lba = 540},
    }};
    assert(cd_player_media(&player, &toc));
    assert(cd_player_snapshot(&player).duration_sectors == 16);
    assert(cd_player_play(&player));
    cd_player_read_t read;
    assert(cd_player_request(&player, &read));
    assert(cd_player_complete(&player, &read, true, pcm, sizeof(pcm)));
    assert(cd_player_snapshot(&player).position_sectors == 0); // Pre-read is not playback.
    assert(cd_player_take(&player, pcm, sizeof(pcm)) == sizeof(pcm));
    assert(cd_player_snapshot(&player).position_sectors == 8);
    player.auto_recover = true;
    assert(!cd_player_take(&player, pcm, sizeof(pcm)));
    assert(cd_player_snapshot(&player).state == AUDIO_UNDERRUN);
    assert(cd_player_rebuffer(&player));
    assert(cd_player_snapshot(&player).state == AUDIO_PREFILL);
    assert(cd_player_snapshot(&player).position_sectors == 8);
    assert(cd_player_pause(&player));
    assert(!cd_player_take(&player, pcm, sizeof(pcm)));
    assert(cd_player_snapshot(&player).position_sectors == 8);
    assert(cd_player_play(&player)); // Refill retains progress.
    assert(cd_player_snapshot(&player).position_sectors == 8);
    assert(cd_player_request(&player, &read));
    assert(cd_player_complete(&player, &read, true, pcm, sizeof(pcm)));
    assert(cd_player_take(&player, pcm, sizeof(pcm)) == sizeof(pcm));
    assert(!cd_player_take(&player, pcm, sizeof(pcm)));
    assert(cd_player_snapshot(&player).state == AUDIO_STOPPED);
    assert(cd_player_snapshot(&player).position_sectors == 16); // Single-track EOF is full.
    assert(cd_player_step(&player, 1));
    assert(cd_player_snapshot(&player).track == 7);
    assert(cd_player_snapshot(&player).duration_sectors == 24);
    assert(cd_player_snapshot(&player).position_sectors == 0);
    player.audio.dequeued_bytes = UINT64_MAX;
    assert(cd_player_snapshot(&player).position_sectors == 24); // Clamp before narrowing.
    cd_player_stop(&player);
    assert(cd_player_snapshot(&player).position_sectors == 0);
    cd_player_lost(&player);
    assert(cd_player_snapshot(&player).duration_sectors == 0);
    assert(cd_player_snapshot(&player).position_sectors == 0);
}
static void check_bar(void)
{
    uint8_t frame[OLED_FRAME_BYTES];
    cd_player_status_t status = {.media = true, .track = 1, .duration_sectors = 300};
    const unsigned positions[] = {0, 150, 300, UINT32_MAX};
    const unsigned widths[] = {0, 62, 124, 124};
    for (unsigned i = 0; i < 4; ++i) {
        status.position_sectors = positions[i];
        oled_render(frame, &status, true);
        for (unsigned x = 2; x < 126; ++x)
            assert(((frame[7 * 128 + x] & 0x3c) != 0) == (x < 2 + widths[i]));
    }
    status.media = false; // Ignore even stale incoming position/duration without media.
    oled_render(frame, &status, true);
    for (unsigned x = 2; x < 126; ++x) assert(!(frame[7 * 128 + x] & 0x3c));
    status.media = true;
    status.duration_sectors = 0;
    oled_render(frame, &status, true); // No division by zero.
    for (unsigned x = 2; x < 126; ++x) assert(!(frame[7 * 128 + x] & 0x3c));
}
int main(int argc, char **argv)
{
    check_progress();
    check_bar();
    cd_player_core_t player;
    assert(cd_player_init(&player, storage, sizeof(storage), 8 * PROBE_CD_SECTOR_SIZE));
    cd_player_status_t status = cd_player_snapshot(&player);
    assert(!status.media && !status.track && !strcmp(oled_status_label(&status), "无目录"));
    probe_toc_t toc = {.track_count = 2, .tracks = {
        {.number = 2, .start_lba = 0, .end_lba = 100},
        {.number = 3, .start_lba = 100, .end_lba = 200},
    }};
    assert(cd_player_media(&player, &toc));
    status = cd_player_snapshot(&player);
    assert(status.media && status.track == 2 && status.state == AUDIO_STOPPED);
    assert(cd_player_step(&player, 1));
    status = cd_player_snapshot(&player);
    assert(status.track == 3 && status.state == AUDIO_PREFILL);
    assert(cd_player_step(&player, 1));
    assert(cd_player_snapshot(&player).track == 2);
    assert(cd_player_step(&player, -1) && cd_player_snapshot(&player).track == 3);
    cd_player_fault(&player);
    status = cd_player_snapshot(&player);
    assert(status.track == 3 && !strcmp(oled_status_label(&status), "故障"));
    cd_player_lost(&player);
    status = cd_player_snapshot(&player);
    assert(!status.media && status.track == 0 && !strcmp(oled_status_label(&status), "无目录"));

    const char *labels[] = {"已停止", "缓冲中", "播放中", "已暂停", "欠载", "故障"};
    uint8_t frame[OLED_FRAME_BYTES], previous[OLED_FRAME_BYTES] = {0};
    status = (cd_player_status_t){.media = true, .track = 99};
    for (unsigned i = 0; i < 6; ++i) {
        status.state = (audio_state_t)i;
        assert(!strcmp(oled_status_label(&status), labels[i]));
        oled_render(frame, &status, false);
        assert(memcmp(previous, frame, sizeof(frame)) != 0);
        memcpy(previous, frame, sizeof(frame));
    }
    oled_render(frame, &status, true);
    assert(memcmp(previous, frame, 3 * OLED_WIDTH) == 0);
    assert(memcmp(previous, frame, sizeof(frame)) != 0);
    // Rendering clears old glyphs and depends only on this snapshot.
    status = (cd_player_status_t){0};
    oled_render(frame, &status, false);
    memset(previous, 0xff, sizeof(previous));
    oled_render(previous, &status, false);
    assert(!memcmp(frame, previous, sizeof(frame)));

    fake_bus_t bus = {0};
    assert(oled_panel_init(write_fake, &bus) && bus.calls == 1);
    assert(oled_panel_on(write_fake, &bus) && bus.calls == 2);
    bus = (fake_bus_t){.fail_at = 1};
    assert(!oled_panel_init(write_fake, &bus));
    bus = (fake_bus_t){.fail_at = 1};
    assert(!oled_panel_on(write_fake, &bus));
    for (unsigned i = 0; i < sizeof(frame); ++i) frame[i] = (uint8_t)(i * 37 + i / 128);
    bus = (fake_bus_t){.pages = true};
    memset(bus.ram, 0xa5, sizeof(bus.ram));
    assert(oled_panel_flush(write_fake, &bus, frame) && bus.calls == 16);
    for (unsigned page = 0; page < 8; ++page) {
        assert(!memcmp(bus.ram[page] + 2, frame + page * 128, 128));
        assert(bus.ram[page][0] == 0xa5 && bus.ram[page][1] == 0xa5);
        assert(bus.ram[page][130] == 0xa5 && bus.ram[page][131] == 0xa5);
    }
    for (unsigned i = 1; i <= 16; ++i) {
        bus = (fake_bus_t){.pages = true, .fail_at = i};
        assert(!oled_panel_flush(write_fake, &bus, frame) && bus.calls == i);
    }
    // Optional PGM contact sheet from the production renderer, for visual inspection.
    if (argc == 2) {
        FILE *out = fopen(argv[1], "wb"); assert(out);
        fprintf(out, "P5\n256 448\n255\n");
        for (unsigned scene = 0; scene < 7; ++scene) {
            status = (cd_player_status_t){.media = scene < 6, .track = 13,
                .state = (audio_state_t)(scene % 6), .duration_sectors = 18000,
                .position_sectors = scene == 0 ? 0 : 6750};
            oled_render(frame, &status, true);
            oled_render(previous, &status, false);
            for (unsigned y = 0; y < 64; ++y) {
                for (unsigned x = 0; x < 128; ++x)
                    fputc(frame[(y / 8) * 128 + x] & (1U << (y % 8)) ? 255 : 0, out);
                for (unsigned x = 0; x < 128; ++x)
                    fputc(previous[(y / 8) * 128 + x] & (1U << (y % 8)) ? 255 : 0, out);
            }
        }
        assert(!fclose(out));
    }
    puts("OLED snapshot, rendering and SH1106 page/failure tests passed");
    return 0;
}
