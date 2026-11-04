#include "oled_panel.h"
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
            uint8_t bits = glyph ? glyph[row] : (*s == '-' && row == 3 ? 14 : 0);
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
const char *oled_status_label(const cd_player_status_t *s)
{
    // Unavailable includes missing/invalid TOC; do not claim a physical no-disc diagnosis.
    if (!s->media) return "NO MEDIA";
    switch (s->state) {
    case AUDIO_STOPPED: return "STOPPED";
    case AUDIO_PREFILL: return "BUFFERING";
    case AUDIO_PLAYING: return "PLAYING";
    case AUDIO_PAUSED: return "PAUSED";
    case AUDIO_UNDERRUN: return "UNDERRUN";
    case AUDIO_FAULT: return "FAULT";
    default: return "UNKNOWN";
    }
}
void oled_render(uint8_t frame[OLED_FRAME_BYTES], const cd_player_status_t *s, bool i2s)
{
    memset(frame, 0, OLED_FRAME_BYTES);
    text(frame, 0, 0, 1, "DISCORA");
    char track[16] = "TRACK --";
    if (s->media) snprintf(track, sizeof(track), "TRACK %02u", s->track);
    text(frame, 0, 16, 2, track);
    text(frame, 0, 38, 2, oled_status_label(s));
    text(frame, 0, 57, 1, i2s ? "I2S OUTPUT" : "CLOCK - NO AUDIO");
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
