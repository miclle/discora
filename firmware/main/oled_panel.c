#include "oled_panel.h"
#include "oled_font_zh.h"
#include <stdio.h>
#include <string.h>

// Locally drawn 5x7 glyphs, rows with bit 4 at the left. No vendor font/library.
static const uint8_t letters[26][7] = {
    {14,17,17,31,17,17,17}, {30,17,17,30,17,17,30},
    {14,17,16,16,16,17,14}, {30,17,17,17,17,17,30},
    {31,16,16,30,16,16,31}, {31,16,16,30,16,16,16},
    {14,17,16,23,17,17,14}, {17,17,17,31,17,17,17},
    {31,4,4,4,4,4,31}, {7,2,2,2,18,18,12},
    {17,18,20,24,20,18,17}, {16,16,16,16,16,16,31},
    {17,27,21,21,17,17,17}, {17,25,21,19,17,17,17},
    {14,17,17,17,17,17,14}, {30,17,17,30,16,16,16},
    {14,17,17,17,21,18,13}, {30,17,17,30,20,18,17},
    {15,16,16,14,1,1,30}, {31,4,4,4,4,4,4},
    {17,17,17,17,17,17,14}, {17,17,17,17,17,10,4},
    {17,17,17,21,21,21,10}, {17,17,10,4,10,17,17},
    {17,17,10,4,4,4,4}, {31,1,2,4,8,16,31},
};
static const uint8_t digits[10][7] = {
    {14,17,19,21,25,17,14}, {4,12,4,4,4,4,14},
    {14,17,1,2,4,8,31}, {30,1,1,14,1,1,30},
    {2,6,10,18,31,2,2}, {31,16,16,30,1,1,30},
    {14,16,16,30,17,17,14}, {31,1,2,4,8,8,8},
    {14,17,17,14,17,17,14}, {14,17,17,15,1,1,14},
};
static void text(uint8_t *frame, unsigned x, unsigned y, unsigned scale, const char *s)
{
    for (; *s; ++s, x += 6 * scale) {
        const uint8_t *glyph = NULL;
        if (*s >= 'A' && *s <= 'Z') glyph = letters[*s - 'A'];
        if (*s >= '0' && *s <= '9') glyph = digits[*s - '0'];
        for (unsigned row = 0; row < 7; ++row) {
            uint8_t bits = glyph ? glyph[row] :
                (*s == '-' && row == 3 ? 14 :
                 *s == ':' && (row == 2 || row == 5) ? 4 :
                 *s == '/' ? (1U << (row * 4 / 6)) : 0);
            for (unsigned col = 0; col < 5; ++col) {
                if (!(bits & (1U << (4 - col)))) continue;
                for (unsigned dy = 0; dy < scale; ++dy)
                    for (unsigned dx = 0; dx < scale; ++dx) {
                        unsigned px = x + col * scale + dx, py = y + row * scale + dy;
                        if (px < OLED_WIDTH && py < OLED_HEIGHT)
                            frame[(py / 8) * OLED_WIDTH + px] |= 1U << (py % 8);
                    }
            }
        }
    }
}
static void pixel(uint8_t *frame, unsigned x, unsigned y)
{
    if (x < OLED_WIDTH && y < OLED_HEIGHT)
        frame[(y / 8) * OLED_WIDTH + x] |= 1U << (y % 8);
}
// Only fixed, three-byte Chinese UI strings from the compiled subset reach here.
static void zh_text(uint8_t *frame, unsigned x, unsigned y, const char *s)
{
    for (; *s; s += 3, x += 16) {
        for (size_t i = 0; i < sizeof(oled_zh_glyphs) / sizeof(oled_zh_glyphs[0]); ++i) {
            if (strncmp(s, oled_zh_glyphs[i].utf8, 3)) continue;
            for (unsigned row = 0; row < 16; ++row)
                for (unsigned col = 0; col < 16; ++col)
                    if (oled_zh_glyphs[i].rows[row] & (1U << (15 - col)))
                        pixel(frame, x + col, y + row);
            break;
        }
    }
}
const char *oled_status_label(const cd_player_status_t *s)
{
    // Missing/invalid TOC does not prove that the drive physically contains no disc.
    if (!s->media) return "无目录";
    switch (s->state) {
    case AUDIO_STOPPED: return "已停止";
    case AUDIO_PREFILL: return "缓冲中";
    case AUDIO_PLAYING: return "播放中";
    case AUDIO_PAUSED: return "已暂停";
    case AUDIO_UNDERRUN: return "欠载";
    case AUDIO_FAULT: return "故障";
    default: return "未知";
    }
}
void oled_render(uint8_t frame[OLED_FRAME_BYTES], const cd_player_status_t *s, bool i2s)
{
    memset(frame, 0, OLED_FRAME_BYTES);
    zh_text(frame, 0, 0, "曲目");
    char track[12] = "--";
    if (s->media) snprintf(track, sizeof(track), "%02u", s->track);
    text(frame, 40, 1, 2, track);
    zh_text(frame, 0, 24, oled_status_label(s));
    if (!i2s) zh_text(frame, 80, 24, "无声");

    char times[32] = "--:-- / --:--";
    uint32_t position = s->position_sectors < s->duration_sectors ?
                        s->position_sectors : s->duration_sectors;
    unsigned fill = 0;
    if (s->media && s->duration_sectors) {
        unsigned elapsed = position / 75, duration = s->duration_sectors / 75;
        snprintf(times, sizeof(times), "%02u:%02u / %02u:%02u",
                 elapsed / 60, elapsed % 60, duration / 60, duration % 60);
        fill = (uint64_t)position * 124 / s->duration_sectors;
    }
    text(frame, 0, 45, 1, times);
    // Empty border remains visible without media; no stale duration or filled pixels.
    for (unsigned x = 0; x < OLED_WIDTH; ++x) {
        pixel(frame, x, 56);
        pixel(frame, x, 63);
    }
    for (unsigned y = 57; y < 63; ++y) {
        pixel(frame, 0, y);
        pixel(frame, 127, y);
    }
    for (unsigned x = 2; x < 2 + fill; ++x)
        for (unsigned y = 58; y < 62; ++y) pixel(frame, x, y);
}
bool oled_panel_init(oled_write_fn write, void *context)
{
    // SH1106 AD/8B charge pump, 64 COM, segment remap and reverse COM scan.
    // This is deliberately not the SSD1306 8D/14 or horizontal addressing sequence.
    static const uint8_t commands[] = {0x00, 0xae, 0xd5, 0x80, 0xa8, 0x3f,
        0xd3, 0x00, 0x40, 0xa1, 0xc8, 0xda, 0x12, 0x81, 0x80,
        0xd9, 0x22, 0xdb, 0x35, 0xa4, 0xa6, 0xad, 0x8b};
    return write(context, commands, sizeof(commands));
}
bool oled_panel_on(oled_write_fn write, void *context)
{
    static const uint8_t command[] = {0x00, 0xaf};
    return write(context, command, sizeof(command));
}
bool oled_panel_flush(oled_write_fn write, void *context, const uint8_t frame[OLED_FRAME_BYTES])
{
    uint8_t data[OLED_WIDTH + 1];
    data[0] = 0x40;
    for (unsigned page = 0; page < 8; ++page) {
        // The 128 visible columns occupy columns 2..129 of SH1106's 132-column RAM.
        const uint8_t address[] = {0x00, 0xb0 | page, 0x02, 0x10};
        if (!write(context, address, sizeof(address))) return false;
        memcpy(data + 1, frame + page * OLED_WIDTH, OLED_WIDTH);
        if (!write(context, data, sizeof(data))) return false;
    }
    return true;
}
