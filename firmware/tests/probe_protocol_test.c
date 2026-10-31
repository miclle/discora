#include "probe_protocol.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Synthetic protocol fixtures, never hardware success logs.
static const uint8_t config[] = {
    9, 2, 32, 0, 1, 1, 0, 0x80, 50,
    9, 4, 3, 0, 2, 8, 6, 0x50, 0,
    7, 5, 0x81, 2, 64, 0, 0,
    7, 5, 0x02, 2, 64, 0, 0,
};

static void test_descriptors(void)
{
    probe_interface_t out;
    assert(probe_find_interface(config, sizeof(config), &out));
    assert(out.number == 3 && out.subclass == 6 && out.ep_in == 0x81 && out.ep_out == 2);
    assert(out.mps_in == 64 && out.mps_out == 64);
    assert(!probe_find_interface(NULL, sizeof(config), &out));
    assert(!probe_find_interface(config, sizeof(config), NULL));
    for (size_t n = 0; n < sizeof(config); ++n) {
        assert(!probe_find_interface(config, n, &out));
    }
    uint8_t bad[sizeof(config)];
    const struct { size_t offset; uint8_t value; } corruptions[] = {
        {9, 0}, {9, 1}, {9, 33}, {18, 6}, {25, 8}, // malformed descriptor lengths
        {12, 1}, {13, 1}, {14, 3}, {15, 4}, {16, 0x62}, // alt / count / class / subclass / UAS
        {20, 0x80}, {20, 0x91}, {21, 3}, {22, 0}, {22, 63}, {23, 2},
        {27, 0x82}, // two IN endpoints
    };
    for (size_t i = 0; i < sizeof(corruptions) / sizeof(corruptions[0]); ++i) {
        memcpy(bad, config, sizeof(bad));
        bad[corruptions[i].offset] = corruptions[i].value;
        assert(!probe_find_interface(bad, sizeof(bad), &out));
    }
    for (unsigned subclass = 2; subclass <= 6; ++subclass) {
        memcpy(bad, config, sizeof(bad));
        bad[15] = (uint8_t)subclass;
        assert(probe_find_interface(bad, sizeof(bad), &out) ==
               (subclass == 2 || subclass == 5 || subclass == 6));
    }
    // Hub/non-storage interface before BOT: selected interface number is not assumed to be zero.
    uint8_t composite[41] = {9, 2, 41, 0, 2, 1, 0, 0x80, 50,
                             9, 4, 0, 0, 0, 9, 0, 0, 0};
    memcpy(composite + 18, config + 9, 23);
    assert(probe_find_interface(composite, sizeof(composite), &out) && out.number == 3);
    // Even after finding a valid interface, malformed trailing descriptors must be rejected.
    uint8_t trailing[34];
    memcpy(trailing, config, sizeof(config));
    trailing[2] = 34;
    trailing[32] = 0;
    trailing[33] = 4;
    assert(!probe_find_interface(trailing, sizeof(trailing), &out));
}

static void test_cbw(void)
{
    uint8_t cbw[PROBE_CBW_SIZE];
    assert(probe_make_cbw(PROBE_INQUIRY, 6, 0x12345678, 36, cbw));
    const uint8_t expected[PROBE_CBW_SIZE] = {
        0x55, 0x53, 0x42, 0x43, 0x78, 0x56, 0x34, 0x12,
        36, 0, 0, 0, 0x80, 0, 6, 0x12, 0, 0, 0, 36,
    };
    assert(memcmp(cbw, expected, sizeof(cbw)) == 0);
    assert(probe_make_cbw(PROBE_REQUEST_SENSE, 5, 1, 18, cbw));
    assert(cbw[8] == 18 && cbw[12] == 0x80 && cbw[14] == 12 && cbw[15] == 3 && cbw[19] == 18);
    assert(probe_make_cbw(PROBE_TEST_UNIT_READY, 2, 2, 0, cbw));
    assert(cbw[8] == 0 && cbw[12] == 0 && cbw[13] == 0 && cbw[14] == 12 && cbw[15] == 0);
    assert(!probe_make_cbw((probe_command_t)99, 6, 0, 0, cbw));
    assert(!probe_make_cbw(PROBE_INQUIRY, 4, 0, 36, cbw));
    assert(!probe_make_cbw(PROBE_INQUIRY, 6, 0, 36, NULL));
    assert(!probe_make_cbw(PROBE_INQUIRY, 6, 0, 35, cbw));
    assert(!probe_make_cbw(PROBE_TEST_UNIT_READY, 6, 0, 1, cbw));
    assert(probe_make_cbw(PROBE_READ_TOC, 6, 3, 4, cbw));
    assert(cbw[8] == 4 && cbw[12] == 0x80 && cbw[14] == 10 && cbw[15] == 0x43);
    assert(cbw[16] == 0 && cbw[17] == 0 && cbw[21] == 0 && cbw[22] == 0 && cbw[23] == 4);
    assert(probe_make_cbw(PROBE_READ_TOC, 2, 4, 804, cbw));
    assert(cbw[8] == 0x24 && cbw[9] == 3 && cbw[14] == 12 && cbw[22] == 3 && cbw[23] == 0x24);
    assert(cbw[24] == 0 && cbw[25] == 0 && cbw[26] == 0);
    assert(!probe_make_cbw(PROBE_READ_TOC, 6, 0, 3, cbw));
    assert(!probe_make_cbw(PROBE_READ_TOC, 6, 0, 805, cbw));
}

static void test_read_cd(void)
{
    uint8_t cbw[PROBE_CBW_SIZE];
    probe_track_t track = {.number = 1, .start_lba = 0x1234560, .end_lba = 0x1234580};
    assert(probe_make_read_cd_cbw(6, 0x12345678, &track, 0x1234567, 8, cbw));
    const uint8_t expected[PROBE_CBW_SIZE] = {
        0x55, 0x53, 0x42, 0x43, 0x78, 0x56, 0x34, 0x12,
        0x80, 0x49, 0, 0, 0x80, 0, 12,
        0xbe, 4, 1, 0x23, 0x45, 0x67, 0, 0, 8, 0x10, 0, 0, 0, 0, 0, 0,
    };
    assert(memcmp(cbw, expected, sizeof(cbw)) == 0);
    assert(probe_make_read_cd_cbw(2, 1, &track, track.end_lba - 1, 1, cbw));
    assert(cbw[8] == 0x30 && cbw[9] == 9 && cbw[14] == 12);
    assert(probe_make_read_cd_cbw(5, 1, &track, track.end_lba - 8, 8, cbw));
    assert(!probe_make_read_cd_cbw(4, 1, &track, track.start_lba, 1, cbw));
    assert(!probe_make_read_cd_cbw(6, 1, NULL, 0, 1, cbw));
    assert(!probe_make_read_cd_cbw(6, 1, &track, track.start_lba, 1, NULL));
    assert(!probe_make_read_cd_cbw(6, 1, &track, track.start_lba - 1, 1, cbw));
    assert(!probe_make_read_cd_cbw(6, 1, &track, track.end_lba, 1, cbw));
    assert(!probe_make_read_cd_cbw(6, 1, &track, UINT32_MAX, 1, cbw));
    assert(!probe_make_read_cd_cbw(6, 1, &track, track.end_lba - 1, 2, cbw));
    assert(!probe_make_read_cd_cbw(6, 1, &track, track.start_lba, 0, cbw));
    assert(!probe_make_read_cd_cbw(6, 1, &track, track.start_lba, 9, cbw));
    assert(!probe_make_cbw(PROBE_READ_CD, 6, 1, 2352, cbw)); // Track guard is mandatory.
    track.control = 4;
    assert(!probe_make_read_cd_cbw(6, 1, &track, track.start_lba, 1, cbw));
    track.control = 0;
    track.number = 0;
    assert(!probe_make_read_cd_cbw(6, 1, &track, track.start_lba, 1, cbw));
    track.number = 100;
    assert(!probe_make_read_cd_cbw(6, 1, &track, track.start_lba, 1, cbw));
    track.number = 1;
    track.end_lba = track.start_lba;
    assert(!probe_make_read_cd_cbw(6, 1, &track, track.start_lba, 1, cbw));
    track.end_lba = UINT32_MAX;
    assert(!probe_make_read_cd_cbw(6, 1, &track, track.start_lba, 1, cbw));
}

static void test_toc(void)
{
    const uint8_t toc[] = {
        0, 26, 1, 2,
        0, 0x10, 1, 0, 0, 0, 0, 0,
        0, 0x10, 2, 0, 0, 0, 0x57, 0xe4,
        0, 0x10, 0xaa, 0, 0, 0, 0xaf, 0xc8,
    };
    probe_toc_t parsed;
    size_t total;
    assert(probe_toc_size_from_header(toc, 4, &total) && total == sizeof(toc));
    assert(probe_parse_toc(toc, sizeof(toc), &parsed));
    assert(parsed.first_track == 1 && parsed.last_track == 2 && parsed.track_count == 2);
    assert(parsed.audio_tracks == 2 && parsed.data_tracks == 0 && parsed.lead_out_lba == 45000);
    assert(parsed.tracks[0].start_lba == 0 && parsed.tracks[0].end_lba == 22500);
    assert(parsed.tracks[1].start_lba == 22500 && parsed.tracks[1].end_lba == 45000);
    for (size_t n = 0; n < sizeof(toc); ++n) {
        assert(!probe_parse_toc(toc, n, &parsed));
    }
    assert(!probe_parse_toc(NULL, sizeof(toc), &parsed));
    assert(!probe_parse_toc(toc, sizeof(toc), NULL));
    assert(!probe_toc_size_from_header(toc, 3, &total));
    assert(!probe_toc_size_from_header(toc, 4, NULL));
    uint8_t bad[sizeof(toc)];
    const struct { size_t offset; uint8_t value; } corruptions[] = {
        {0, 1}, {1, 25}, {2, 0}, {2, 3}, {3, 100}, // invalid header / descriptor count
        {6, 2}, {14, 1}, {22, 3}, // track order / lead-out
        {5, 0}, {13, 0x20}, // invalid ADR
        {8, 0x80}, {16, 0x80}, {24, 0x80}, // negative LBA (unsupported)
        {18, 0xff}, // second track starts after the lead-out
        {26, 0}, // lead-out precedes final track
    };
    for (size_t i = 0; i < sizeof(corruptions) / sizeof(corruptions[0]); ++i) {
        memcpy(bad, toc, sizeof(bad));
        bad[corruptions[i].offset] = corruptions[i].value;
        assert(!probe_parse_toc(bad, sizeof(bad), &parsed));
    }
    memcpy(bad, toc, sizeof(bad));
    memset(bad + 16, 0, 4); // Two tracks cannot start at the same LBA.
    assert(!probe_parse_toc(bad, sizeof(bad), &parsed));
    uint8_t excess[sizeof(toc) + 1];
    memcpy(excess, toc, sizeof(toc));
    excess[sizeof(toc)] = 0;
    assert(!probe_parse_toc(excess, sizeof(excess), &parsed));

    // Maximum CD TOC: 99 tracks plus lead-out; preserve data / audio control bits.
    uint8_t maximum[PROBE_MAX_TOC_DATA] = {0};
    maximum[0] = (sizeof(maximum) - 2) >> 8;
    maximum[1] = (sizeof(maximum) - 2) & 0xff;
    maximum[2] = 1;
    maximum[3] = 99;
    for (size_t i = 0; i <= 99; ++i) {
        uint8_t *d = maximum + 4 + 8 * i;
        d[1] = i == 98 ? 0x14 : 0x10;
        d[2] = i == 99 ? 0xaa : (uint8_t)(i + 1);
        uint32_t lba = (uint32_t)i * 4500;
        d[4] = (uint8_t)(lba >> 24);
        d[5] = (uint8_t)(lba >> 16);
        d[6] = (uint8_t)(lba >> 8);
        d[7] = (uint8_t)lba;
    }
    assert(probe_parse_toc(maximum, sizeof(maximum), &parsed));
    assert(parsed.track_count == 99 && parsed.audio_tracks == 98 && parsed.data_tracks == 1);
    assert(parsed.tracks[98].control == 4 && parsed.tracks[98].end_lba == 445500);

    // First track need not be numbered 1; header and descriptors must still agree.
    memcpy(bad, toc, sizeof(bad));
    bad[2] = 3;
    bad[3] = 4;
    bad[6] = 3;
    bad[14] = 4;
    assert(probe_parse_toc(bad, sizeof(bad), &parsed) && parsed.first_track == 3);
}

static void test_csw(void)
{
    uint8_t csw[13] = {0x55, 0x53, 0x42, 0x53, 7, 0, 0, 0, 0, 0, 0, 0, 0};
    probe_csw_t out;
    assert(probe_parse_csw(csw, 13, 7, 36, 36, &out));
    assert(out.status == 0 && out.residue == 0 && out.relevant_size == 36);
    assert(!probe_parse_csw(csw, 12, 7, 36, 36, &out));
    assert(!probe_parse_csw(csw, 14, 7, 36, 36, &out));
    assert(!probe_parse_csw(csw, 13, 8, 36, 36, &out));
    assert(!probe_parse_csw(csw, 13, 7, 36, 37, &out));
    assert(!probe_parse_csw(csw, 13, 7, 36, 35, &out));
    csw[0] = 0;
    assert(!probe_parse_csw(csw, 13, 7, 36, 36, &out));
    csw[0] = 0x55;
    csw[12] = 1;
    csw[8] = 36;
    assert(probe_parse_csw(csw, 13, 7, 36, 0, &out) && out.status == 1);
    csw[8] = 37;
    assert(!probe_parse_csw(csw, 13, 7, 36, 0, &out));
    csw[8] = 4;
    assert(probe_parse_csw(csw, 13, 7, 36, 32, &out) && out.relevant_size == 32);
    // Relevant bytes can be fewer than USB bytes received (BOT residue semantics).
    assert(probe_parse_csw(csw, 13, 7, 36, 36, &out) && out.relevant_size == 32);
    csw[8] = 0;
    csw[12] = 2;
    assert(!probe_parse_csw(csw, 13, 7, 0, 0, &out)); // phase error requires reset
    csw[12] = 3;
    assert(!probe_parse_csw(csw, 13, 7, 0, 0, &out));
    csw[12] = 0;
    assert(probe_parse_csw(csw, 13, 7, 0, 0, &out));
}

static void test_responses(void)
{
    uint8_t inquiry[36] = {5, 0x80, 5, 2, 31};
    memcpy(inquiry + 8, "TEST    SYNTHETIC DRIVE 1.00", 28);
    probe_inquiry_t identity;
    assert(probe_parse_inquiry(inquiry, sizeof(inquiry), &identity));
    assert(identity.peripheral_type == 5 && identity.qualifier == 0);
    assert(strcmp(identity.vendor, "TEST    ") == 0);
    assert(strcmp(identity.revision, "1.00") == 0);
    assert(!probe_parse_inquiry(inquiry, 35, &identity));
    inquiry[4] = 30;
    assert(!probe_parse_inquiry(inquiry, 36, &identity));
    inquiry[4] = 31;
    inquiry[8] = '\n';
    assert(probe_parse_inquiry(inquiry, 36, &identity) && identity.vendor[0] == '?');

    uint8_t fixed[18] = {0xf0, 0, 2, 0, 0, 0, 0, 10, 0, 0, 0, 0, 0x3a, 0};
    probe_sense_t sense;
    assert(probe_parse_sense(fixed, sizeof(fixed), &sense));
    assert(sense.key == 2 && sense.asc == 0x3a && sense.ascq == 0);
    assert(!probe_parse_sense(fixed, 13, &sense));
    fixed[7] = 0;
    assert(!probe_parse_sense(fixed, sizeof(fixed), &sense));
    uint8_t descriptor[8] = {0x72, 6, 0x28, 0, 0, 0, 0, 0};
    assert(probe_parse_sense(descriptor, sizeof(descriptor), &sense));
    assert(sense.key == 6 && sense.asc == 0x28 && sense.ascq == 0);
    descriptor[0] = 0;
    assert(!probe_parse_sense(descriptor, sizeof(descriptor), &sense));
    assert(!probe_parse_sense(NULL, 0, &sense));
}

static void test_parser_bounds(void)
{
    // Deterministic malformed/truncated descriptor and response corpus under ASan/UBSan.
    uint8_t bytes[96];
    uint32_t seed = 0x6d317573;
    for (unsigned iteration = 0; iteration < 10000; ++iteration) {
        for (size_t i = 0; i < sizeof(bytes); ++i) {
            seed = seed * 1664525u + 1013904223u;
            bytes[i] = (uint8_t)(seed >> 24);
        }
        size_t size = iteration % (sizeof(bytes) + 1);
        if (size >= 9 && iteration % 2 == 0) {
            bytes[0] = 9;
            bytes[1] = 2;
            bytes[2] = (uint8_t)size;
            bytes[3] = 0;
        }
        uint8_t *bounded = malloc(size ? size : 1);
        assert(bounded);
        memcpy(bounded, bytes, size);
        probe_interface_t interface;
        probe_inquiry_t inquiry;
        probe_sense_t sense;
        probe_csw_t csw;
        probe_toc_t toc;
        size_t toc_size;
        probe_find_interface(bounded, size, &interface);
        probe_parse_inquiry(bounded, size, &inquiry);
        probe_parse_sense(bounded, size, &sense);
        probe_parse_csw(bounded, size, iteration, 36, iteration % 65, &csw);
        probe_toc_size_from_header(bounded, size, &toc_size);
        probe_parse_toc(bounded, size, &toc);
        free(bounded);
    }
}

int main(void)
{
    test_descriptors();
    test_cbw();
    test_csw();
    test_responses();
    test_toc();
    test_read_cd();
    test_parser_bounds();
    puts("PASS: protocol fixtures, malformed responses and 10000 bounds cases (not hardware tests)");
    return 0;
}
