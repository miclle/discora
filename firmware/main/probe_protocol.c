#include "probe_protocol.h"

#include <string.h>

static uint16_t read_le16(const uint8_t *p)
{
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static uint32_t read_le32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint32_t read_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static void write_le32(uint8_t *p, uint32_t value)
{
    for (size_t i = 0; i < 4; ++i) {
        p[i] = (uint8_t)(value >> (8 * i));
    }
}

static bool supported_subclass(uint8_t subclass)
{
    return subclass == 0x02 || subclass == 0x05 || subclass == 0x06;
}

bool probe_find_interface(const uint8_t *config, size_t size, probe_interface_t *out)
{
    if (!config || !out || size < 9 || config[0] != 9 || config[1] != 2 ||
        read_le16(config + 2) != size) {
        return false;
    }

    probe_interface_t current = {0};
    probe_interface_t selected = {0};
    bool candidate = false;
    bool found = false;
    unsigned endpoints = 0;
    for (size_t offset = 9; offset < size;) {
        if (size - offset < 2) {
            return false;
        }
        const uint8_t *d = config + offset;
        if (d[0] < 2 || d[0] > size - offset) {
            return false;
        }
        if (d[1] == 4) {
            if (candidate && endpoints == 2 && current.ep_in && current.ep_out && !found) {
                selected = current;
                found = true;
            }
            if (d[0] < 9) {
                return false;
            }
            current = (probe_interface_t){.number = d[2], .subclass = d[6]};
            candidate = d[3] == 0 && d[4] == 2 && d[5] == 8 &&
                        supported_subclass(d[6]) && d[7] == 0x50;
            endpoints = 0;
        } else if (d[1] == 5) {
            if (d[0] < 7) {
                return false;
            }
            if (candidate) {
                ++endpoints;
                uint16_t mps = read_le16(d + 4);
                if ((d[3] & 3) != 2 || (d[2] & 0x70) || !(d[2] & 0x0f) ||
                    (mps != 8 && mps != 16 && mps != 32 && mps != 64)) {
                    candidate = false;
                } else if (d[2] & 0x80) {
                    if (current.ep_in) {
                        candidate = false;
                    }
                    current.ep_in = d[2];
                    current.mps_in = mps;
                } else {
                    if (current.ep_out) {
                        candidate = false;
                    }
                    current.ep_out = d[2];
                    current.mps_out = mps;
                }
            }
        }
        offset += d[0];
    }
    if (candidate && endpoints == 2 && current.ep_in && current.ep_out && !found) {
        selected = current;
        found = true;
    }
    if (found) {
        *out = selected;
    }
    return found;
}

size_t probe_data_size(probe_command_t command)
{
    switch (command) {
    case PROBE_INQUIRY: return 36;
    case PROBE_REQUEST_SENSE: return 18;
    case PROBE_TEST_UNIT_READY: return 0;
    case PROBE_READ_TOC: return PROBE_TOC_HEADER_SIZE;
    default: return 0;
    }
}

const char *probe_command_name(probe_command_t command)
{
    switch (command) {
    case PROBE_INQUIRY: return "INQUIRY";
    case PROBE_TEST_UNIT_READY: return "TEST UNIT READY";
    case PROBE_REQUEST_SENSE: return "REQUEST SENSE";
    case PROBE_READ_TOC: return "READ TOC";
    case PROBE_READ_CD: return "READ CD";
    default: return "INVALID";
    }
}

bool probe_make_cbw(probe_command_t command, uint8_t subclass, uint32_t tag,
                    size_t data_size, uint8_t out[PROBE_CBW_SIZE])
{
    uint8_t opcode;
    switch (command) {
    case PROBE_INQUIRY: opcode = 0x12; break;
    case PROBE_TEST_UNIT_READY: opcode = 0x00; break;
    case PROBE_REQUEST_SENSE: opcode = 0x03; break;
    case PROBE_READ_TOC: opcode = 0x43; break;
    default: return false;
    }
    if (!out || !supported_subclass(subclass)) {
        return false;
    }
    if (command == PROBE_READ_TOC) {
        if (data_size < PROBE_TOC_HEADER_SIZE || data_size > PROBE_MAX_TOC_DATA) {
            return false;
        }
    } else if (data_size != probe_data_size(command)) {
        return false;
    }
    memset(out, 0, PROBE_CBW_SIZE);
    write_le32(out, 0x43425355);
    write_le32(out + 4, tag);
    write_le32(out + 8, (uint32_t)data_size);
    out[12] = data_size ? 0x80 : 0;
    // ATAPI command sets use 12-byte packets; SCSI uses the native CDB length.
    out[14] = subclass == 0x06 ? (command == PROBE_READ_TOC ? 10 : 6) : 12;
    out[15] = opcode;
    if (command == PROBE_READ_TOC) {
        // Format 0, MSF=0, starting track 0 (all tracks). Allocation is big-endian.
        out[22] = (uint8_t)(data_size >> 8);
        out[23] = (uint8_t)data_size;
    } else {
        out[19] = (uint8_t)data_size;
    }
    return true;
}

bool probe_make_read_cd_cbw(uint8_t subclass, uint32_t tag, const probe_track_t *track,
                            uint32_t lba, uint8_t sectors, uint8_t out[PROBE_CBW_SIZE])
{
    if (!out || !track || !supported_subclass(subclass) || track->number < 1 ||
        track->number > PROBE_MAX_TRACKS || (track->control & 0x04) ||
        track->start_lba >= track->end_lba || track->end_lba > INT32_MAX ||
        lba < track->start_lba || lba >= track->end_lba || sectors == 0 ||
        sectors > PROBE_MAX_READ_SECTORS || sectors > track->end_lba - lba) {
        return false;
    }
    memset(out, 0, PROBE_CBW_SIZE);
    write_le32(out, 0x43425355);
    write_le32(out + 4, tag);
    write_le32(out + 8, (uint32_t)sectors * PROBE_CD_SECTOR_SIZE);
    out[12] = 0x80;
    out[14] = 12; // READ CD has a native 12-byte CDB for all accepted subclasses.
    out[15] = 0xbe;
    out[16] = 0x04; // Expected Sector Type=CD-DA; DAP=0, RelAdr=0.
    out[17] = (uint8_t)(lba >> 24);
    out[18] = (uint8_t)(lba >> 16);
    out[19] = (uint8_t)(lba >> 8);
    out[20] = (uint8_t)lba;
    out[23] = sectors; // 24-bit big-endian transfer length, bounded to eight sectors.
    out[24] = 0x10; // User data only: 2352 bytes/sector, no C2 or sub-channel bytes.
    return true;
}

bool probe_parse_csw(const uint8_t *data, size_t size, uint32_t tag,
                     size_t requested, size_t received, probe_csw_t *out)
{
    if (!data || !out || size != PROBE_CSW_SIZE || read_le32(data) != 0x53425355 ||
        read_le32(data + 4) != tag || data[12] > 1 || received > requested) {
        return false;
    }
    uint32_t residue = read_le32(data + 8);
    if (residue > requested || requested - residue > received) {
        return false;
    }
    *out = (probe_csw_t){.status = data[12], .residue = residue,
                         .relevant_size = requested - residue};
    return true;
}

static void copy_identity(char *dst, const uint8_t *src, size_t size)
{
    for (size_t i = 0; i < size; ++i) {
        dst[i] = src[i] >= 0x20 && src[i] <= 0x7e ? (char)src[i] : '?';
    }
    dst[size] = '\0';
}

bool probe_parse_inquiry(const uint8_t *data, size_t size, probe_inquiry_t *out)
{
    if (!data || !out || size < 36 || data[4] < 31) {
        return false;
    }
    out->peripheral_type = data[0] & 0x1f;
    out->qualifier = data[0] >> 5;
    copy_identity(out->vendor, data + 8, 8);
    copy_identity(out->product, data + 16, 16);
    copy_identity(out->revision, data + 32, 4);
    return true;
}

bool probe_parse_sense(const uint8_t *data, size_t size, probe_sense_t *out)
{
    if (!data || !out || size < 8) {
        return false;
    }
    uint8_t format = data[0] & 0x7f;
    if ((format == 0x70 || format == 0x71) && size >= 14 && data[7] >= 6) {
        *out = (probe_sense_t){.key = data[2] & 0x0f, .asc = data[12], .ascq = data[13]};
        return true;
    }
    if (format == 0x72 || format == 0x73) {
        *out = (probe_sense_t){.key = data[1] & 0x0f, .asc = data[2], .ascq = data[3]};
        return true;
    }
    return false;
}

bool probe_toc_size_from_header(const uint8_t *data, size_t size, size_t *total_size)
{
    if (!data || !total_size || size < PROBE_TOC_HEADER_SIZE || data[2] < 1 ||
        data[3] > PROBE_MAX_TRACKS || data[3] < data[2]) {
        return false;
    }
    size_t reported = ((size_t)data[0] << 8 | data[1]) + 2;
    size_t expected = PROBE_TOC_HEADER_SIZE + 8 * ((size_t)data[3] - data[2] + 2);
    if (reported != expected || reported > PROBE_MAX_TOC_DATA) {
        return false;
    }
    *total_size = reported;
    return true;
}

bool probe_parse_toc(const uint8_t *data, size_t size, probe_toc_t *out)
{
    size_t total;
    if (!out || !probe_toc_size_from_header(data, size, &total) || size != total) {
        return false;
    }
    size_t tracks = (size_t)data[3] - data[2] + 1;
    uint32_t previous = 0;
    for (size_t i = 0; i <= tracks; ++i) {
        const uint8_t *d = data + PROBE_TOC_HEADER_SIZE + 8 * i;
        uint8_t number = i == tracks ? 0xaa : (uint8_t)(data[2] + i);
        uint32_t lba = read_be32(d + 4);
        if (d[2] != number || (d[1] >> 4) != 1 || lba > INT32_MAX ||
            (i && lba <= previous)) {
            return false;
        }
        previous = lba;
    }
    // Publish only after validating the entire response, including the lead-out.
    memset(out, 0, sizeof(*out));
    out->first_track = data[2];
    out->last_track = data[3];
    out->track_count = (uint8_t)tracks;
    out->lead_out_lba = previous;
    for (size_t i = 0; i < tracks; ++i) {
        const uint8_t *d = data + PROBE_TOC_HEADER_SIZE + 8 * i;
        out->tracks[i] = (probe_track_t){
            .number = d[2], .control = d[1] & 0x0f,
            .start_lba = read_be32(d + 4), .end_lba = read_be32(d + 12),
        };
        if (d[1] & 0x04) {
            ++out->data_tracks;
        } else {
            ++out->audio_tracks;
        }
    }
    return true;
}
