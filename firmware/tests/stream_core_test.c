#include "pcm_buffer.h"
#include "cdda_cursor.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void test_ring(void)
{
    uint8_t storage[128], input[128], output[128];
    pcm_buffer_t ring;
    assert(!pcm_buffer_init(NULL, storage, sizeof(storage)));
    assert(!pcm_buffer_init(&ring, NULL, sizeof(storage)));
    assert(!pcm_buffer_init(&ring, storage, 0));
    assert(!pcm_buffer_init(&ring, storage, 127));
    assert(pcm_buffer_init(&ring, storage, sizeof(storage)));
    assert(!pcm_buffer_read(&ring, output, 4));
    assert(!pcm_buffer_write(&ring, input, 1));
    assert(!pcm_buffer_write(&ring, NULL, 4));
    assert(!pcm_buffer_write(&ring, input, 0));
    uint32_t written = 0, read = 0, random = 17;
    for (unsigned i = 0; i < 20000; ++i) {
        random = random * 1664525u + 1013904223u;
        size_t frames = (random >> 16) % 32 + 1;
        size_t bytes = frames * 4;
        size_t previous = ring.used;
        if (random & 1) {
            for (size_t j = 0; j < frames; ++j) {
                uint32_t value = written + (uint32_t)j;
                memcpy(input + 4 * j, &value, 4);
            }
            bool ok = pcm_buffer_write(&ring, input, bytes);
            assert(ok == (bytes <= sizeof(storage) - previous));
            if (ok) written += (uint32_t)frames;
            else assert(ring.used == previous);
        } else {
            bool ok = pcm_buffer_read(&ring, output, bytes);
            assert(ok == (bytes <= previous));
            if (ok) {
                for (size_t j = 0; j < frames; ++j) {
                    uint32_t value;
                    memcpy(&value, output + 4 * j, 4);
                    assert(value == read++);
                }
            } else assert(ring.used == previous);
        }
        assert(ring.used == (size_t)(written - read) * 4);
    }
    while (ring.used) {
        uint32_t value;
        assert(pcm_buffer_read(&ring, (uint8_t *)&value, 4));
        assert(value == read++);
    }
    assert(read == written && written > 10000);
    memset(input, 0x5a, sizeof(input));
    assert(pcm_buffer_write(&ring, input, sizeof(input)));
    assert(!pcm_buffer_write(&ring, input, 4));
    assert(pcm_buffer_read(&ring, output, sizeof(output)));
    assert(!memcmp(input, output, sizeof(input)));
    assert(!pcm_buffer_read(&ring, output, 4));
}

static void test_cursor(void)
{
    probe_toc_t toc = {.track_count = 3, .tracks = {
        {.number = 1, .start_lba = 0, .end_lba = 16},
        {.number = 2, .start_lba = 16, .end_lba = 26},
        {.number = 3, .start_lba = 26, .end_lba = 34},
    }};
    cdda_cursor_t cursor;
    const probe_track_t *track;
    uint32_t lba;
    uint8_t sectors;
    assert(cdda_cursor_init(&cursor, &toc, 0, 13, 21));
    const uint8_t chunks[] = {3, 8, 2, 8};
    uint32_t expected = 13;
    for (size_t i = 0; i < sizeof(chunks); ++i) {
        assert(cdda_cursor_next(&cursor, &track, &lba, &sectors));
        assert(lba == expected && sectors == chunks[i]);
        assert(lba + sectors <= track->end_lba);
        assert(!cdda_cursor_advance(&cursor, sectors + 1));
        assert(!cdda_cursor_advance(&cursor, 0));
        assert(cdda_cursor_advance(&cursor, sectors));
        expected += sectors;
    }
    assert(expected == 34 && !cursor.remaining);
    assert(!cdda_cursor_next(&cursor, &track, &lba, &sectors));
    assert(!cdda_cursor_init(NULL, &toc, 0, 0, 1));
    assert(!cdda_cursor_init(&cursor, NULL, 0, 0, 1));
    assert(!cdda_cursor_init(&cursor, &toc, 3, 0, 1));
    assert(!cdda_cursor_init(&cursor, &toc, 0, 0, 0));
    assert(!cdda_cursor_init(&cursor, &toc, 0, 0, 35));
    assert(!cdda_cursor_init(&cursor, &toc, 0, 16, 1));
    assert(!cdda_cursor_init(&cursor, &toc, 0, UINT32_MAX, 1));
    toc.tracks[1].control = 4;
    assert(!cdda_cursor_init(&cursor, &toc, 0, 0, 17));
    assert(cdda_cursor_init(&cursor, &toc, 0, 0, 16));
    toc.tracks[1].control = 8;
    assert(!cdda_cursor_init(&cursor, &toc, 0, 0, 17));
    toc.tracks[1].control = 0;
    toc.tracks[1].start_lba = 17;
    assert(!cdda_cursor_init(&cursor, &toc, 0, 0, 17));
    toc.tracks[1].start_lba = 16;
    toc.tracks[1].number = 3;
    assert(!cdda_cursor_init(&cursor, &toc, 0, 0, 17));
}

int main(void)
{
    test_ring();
    test_cursor();
    puts("PASS: 20000 PCM queue operations, wraparound/order/overflow and track boundaries (synthetic, no device)");
    return 0;
}
