#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum {
    PROBE_CBW_SIZE = 31,
    PROBE_CSW_SIZE = 13,
    PROBE_TOC_HEADER_SIZE = 4,
    PROBE_MAX_TRACKS = 99,
    PROBE_MAX_TOC_DATA = PROBE_TOC_HEADER_SIZE + 8 * (PROBE_MAX_TRACKS + 1),
    PROBE_CD_SECTOR_SIZE = 2352,
    PROBE_MAX_READ_SECTORS = 8,
    PROBE_MAX_DATA = PROBE_CD_SECTOR_SIZE * PROBE_MAX_READ_SECTORS,
};

typedef enum {
    PROBE_INQUIRY,
    PROBE_TEST_UNIT_READY,
    PROBE_REQUEST_SENSE,
    PROBE_READ_TOC,
    PROBE_READ_CD,
    PROBE_ALLOW_REMOVAL,
    PROBE_EJECT,
    PROBE_READ_CDTEXT,
} probe_command_t;

typedef struct {
    uint8_t number;
    uint8_t subclass;
    uint8_t ep_in;
    uint8_t ep_out;
    uint16_t mps_in;
    uint16_t mps_out;
} probe_interface_t;

typedef struct {
    uint8_t status;
    uint32_t residue;
    size_t relevant_size;
} probe_csw_t;

typedef struct {
    uint8_t peripheral_type;
    uint8_t qualifier;
    char vendor[9];
    char product[17];
    char revision[5];
} probe_inquiry_t;

typedef struct {
    uint8_t key;
    uint8_t asc;
    uint8_t ascq;
} probe_sense_t;

typedef struct {
    uint8_t number;
    uint8_t control;
    uint32_t start_lba;
    uint32_t end_lba; // Exclusive; the final track ends at lead-out.
} probe_track_t;

typedef struct {
    uint8_t first_track;
    uint8_t last_track;
    uint8_t track_count;
    uint8_t audio_tracks;
    uint8_t data_tracks;
    uint32_t lead_out_lba;
    probe_track_t tracks[PROBE_MAX_TRACKS];
} probe_toc_t;

// Accept only alternate-setting 0, BOT, and SCSI / ATAPI command sets.
bool probe_find_interface(const uint8_t *config, size_t size, probe_interface_t *out);
size_t probe_data_size(probe_command_t command);
const char *probe_command_name(probe_command_t command);
// TOC defaults to its four-byte header; its full length is obtained from that response.
// No arbitrary CDB or Data-Out API: only the explicit queries and allow-removal/eject commands, LUN 0.
bool probe_make_cbw(probe_command_t command, uint8_t subclass, uint32_t tag,
                    size_t data_size, uint8_t out[PROBE_CBW_SIZE]);
// CD-DA only, 1..8 sectors entirely inside one validated audio track; no cross-track reads.
bool probe_make_read_cd_cbw(uint8_t subclass, uint32_t tag, const probe_track_t *track,
                            uint32_t lba, uint8_t sectors, uint8_t out[PROBE_CBW_SIZE]);
bool probe_parse_csw(const uint8_t *data, size_t size, uint32_t tag,
                     size_t requested, size_t received, probe_csw_t *out);
bool probe_parse_inquiry(const uint8_t *data, size_t size, probe_inquiry_t *out);
bool probe_parse_sense(const uint8_t *data, size_t size, probe_sense_t *out);
bool probe_toc_size_from_header(const uint8_t *data, size_t size, size_t *total_size);
// Format 5: four-byte header followed by complete 18-byte CD-Text packs.
// Empty (four bytes) is valid; oversized replies are rejected before requesting data.
bool probe_cdtext_size_from_header(const uint8_t *data, size_t size, size_t *total_size);
// Format 0, MSF=0: complete sequential CD tracks followed by one lead-out (0xAA).
bool probe_parse_toc(const uint8_t *data, size_t size, probe_toc_t *out);
