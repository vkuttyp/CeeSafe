/*
 * diff_gpt.c - C9's differential test: CosmoOS's gpt.c (renamed c_gpt_*) against CeeSafe's port (gpt_*), on the
 * same inputs. For the parser, both see the same disk through the same reader and must give the same result,
 * the same reason, the same table (every byte of it, prefilled alike), the same scratch buffer afterwards, and
 * the same reads in the same order. The disks are tables gpt_build makes, then damaged: bytes flipped, fields
 * rewritten with the checksums made valid again (to reach the checks behind them), sizes changed, reads failed.
 * For the writer, the same parts must give the same answer and the same bytes. CRC-32, GUID text and the
 * build-size helpers are compared on random inputs. Deterministic: seeded xorshift.
 *
 * Usage: diff_gpt [cases] [seed]
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <kernel/gpt.h>

enum gpt_result c_gpt_parse(uint32_t ss, uint64_t nsectors, gpt_read_fn read, void *ctx, void *scratch, struct gpt_table *out,
                            const char **why);
bool c_gpt_build(uint32_t ss, uint64_t nsectors, const uint8_t disk_guid[16], const struct gpt_build_part *parts, unsigned nparts,
                 uint8_t *head, uint8_t *tail);
uint64_t c_gpt_build_first_usable(uint32_t ss);
uint64_t c_gpt_build_last_usable(uint32_t ss, uint64_t nsectors);
uint32_t c_gpt_crc32(const void *data, size_t len);
uint32_t c_gpt_crc32_update(uint32_t crc, const void *data, size_t len);
void c_gpt_guid_format(const uint8_t guid[16], char out[GPT_GUID_TEXT]);
bool c_gpt_guid_parse(const char *text, uint8_t guid[16]);
extern const uint8_t c_gpt_type_esp[16], c_gpt_type_cosmo_root[16];

static uint64_t state;
static uint64_t next(void) {
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    return state;
}
static uint64_t below(uint64_t n) { return next() % n; }

enum { MAX_SECTORS = 600, MAX_READS = 16 };

struct disk {
    uint32_t ss;
    uint64_t n;
    uint8_t *data;
    unsigned reads, fail_at;
    struct { uint64_t lba; uint32_t count; } log[MAX_READS];
};

static int disk_read(void *ctx, uint64_t lba, uint32_t count, void *buf) {
    struct disk *d = ctx;
    if (d->reads < MAX_READS) {
        d->log[d->reads].lba = lba;
        d->log[d->reads].count = count;
    }
    d->reads++;
    if (d->fail_at && d->reads == d->fail_at)
        return -1;
    if (lba >= d->n || d->n - lba < count)
        return -1;
    memcpy(buf, d->data + lba * d->ss, (size_t)count * d->ss);
    return 0;
}

static uint8_t disk_c[MAX_SECTORS * 512 + 64 * 4096], disk_n[sizeof disk_c];
static uint8_t scratch_c[GPT_SCRATCH_BYTES], scratch_n[GPT_SCRATCH_BYTES];
/* Large enough for either sector size: 4096-byte sectors need more (6 and 5 sectors against 34 and 33). */
static uint8_t head_c[GPT_BUILD_HEAD_SECTORS(4096) * 4096], head_n[sizeof head_c];
static uint8_t tail_c[GPT_BUILD_TAIL_SECTORS(4096) * 4096], tail_n[sizeof tail_c];
_Static_assert(sizeof head_c >= GPT_BUILD_HEAD_SECTORS(512) * 512, "head buffer");
static struct gpt_build_part parts[40];

static unsigned long mismatches;

static void report(const char *what, unsigned long n) {
    if (mismatches++ < 20)
        printf("%s mismatch: case %lu\n", what, n);
}

/* Random parts, mostly in the usable range and apart, sometimes not. */
static unsigned random_parts(uint32_t ss, uint64_t n) {
    unsigned count = (unsigned)below(next() % 8 == 0 ? 40 : 6);
    uint64_t first = c_gpt_build_first_usable(ss), last = c_gpt_build_last_usable(ss, n);
    uint64_t at = first;
    memset(parts, 0, sizeof parts);
    if (next() % 16 == 0 && last - first >= 40) { /* GPT_MAX_PARTS and a few more, all valid: one sector each */
        count = GPT_MAX_PARTS - 1 + (unsigned)below(4);
        for (unsigned i = 0; i < count; i++) {
            parts[i].index = i + 1;
            parts[i].first_lba = parts[i].last_lba = first + i;
            memcpy(parts[i].type, c_gpt_type_esp, 16);
            for (unsigned k = 0; k < 16; k++)
                parts[i].uuid[k] = (uint8_t)next();
        }
        return count;
    }
    for (unsigned i = 0; i < count; i++) {
        struct gpt_build_part *p = &parts[i];
        p->index = next() % 16 == 0 ? (uint32_t)below(140) : i + 1 + (uint32_t)below(3) * (i + 1);
        uint64_t len = 1 + below(8);
        p->first_lba = next() % 16 == 0 ? below(n + 4) : at;
        p->last_lba = next() % 16 == 0 ? below(n + 4) : p->first_lba + len - 1;
        if (p->last_lba > last && next() % 2)
            p->last_lba = last;
        at = p->last_lba + 1 + below(3);
        memcpy(p->type, next() % 2 ? c_gpt_type_esp : c_gpt_type_cosmo_root, 16);
        if (next() % 32 == 0)
            memset(p->type, 0, 16);
        for (unsigned k = 0; k < 16; k++)
            p->uuid[k] = (uint8_t)next();
        if (next() % 16 == 0)
            memset(p->uuid, 0, 16);
        if (i > 0 && next() % 16 == 0)
            memcpy(p->uuid, parts[i - 1].uuid, 16);
    }
    return count;
}

static void put32(uint8_t *p, uint32_t v) {
    for (unsigned i = 0; i < 4; i++)
        p[i] = (uint8_t)(v >> (8 * i));
}
static void put64(uint8_t *p, uint64_t v) {
    put32(p, (uint32_t)v);
    put32(p + 4, (uint32_t)(v >> 32));
}
static uint32_t get32(const uint8_t *p) { return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }

/* Makes the header at `lba` and its entry array valid again after a change: the array's CRC (over as much of it as
 * lies on the disk), then the header's own. */
static void reseal(uint8_t *data, uint32_t ss, uint64_t n, uint64_t lba) {
    uint8_t *h = data + lba * ss;
    uint64_t entries = (uint64_t)get32(h + 72) | (uint64_t)get32(h + 76) << 32;
    uint64_t bytes = (uint64_t)get32(h + 80) * get32(h + 84);
    if (entries < n && bytes <= GPT_MAX_ENTRY_BYTES && (n - entries) * ss >= bytes)
        put32(h + 88, c_gpt_crc32(data + entries * ss, (size_t)bytes));
    uint32_t size = get32(h + 12);
    if (size >= 92 && size <= ss) {
        put32(h + 16, 0);
        put32(h + 16, c_gpt_crc32(h, size));
    }
}

/* One field of a header, rewritten with a value near the edges its checks test. */
static void rewrite_field(uint8_t *h, uint32_t ss, uint64_t n) {
    static const unsigned offsets[] = { 8, 12, 24, 32, 40, 48, 56, 72, 80, 84 };
    unsigned off = offsets[below(sizeof offsets / sizeof offsets[0])];
    uint64_t choices[] = { 0, 1, 2, 3, n - 2, n - 1, n, n + 1, ss, 91, 92, 128, 256, 129, 255, 33, 34, 0x10000, 0x20000,
                           n - GPT_BUILD_ARRAY_SECTORS(ss) /* an array ending on the backup header */,
                           UINT64_MAX, (uint64_t)below(n), get32(h + off) + 1, get32(h + off) - 1 };
    uint64_t v = choices[below(sizeof choices / sizeof choices[0])];
    if (off == 8 || off == 12 || off == 80 || off == 84)
        put32(h + off, (uint32_t)v);
    else if (off == 56)
        h[off + below(16)] ^= (uint8_t)(1 + below(255));
    else
        put64(h + off, v);
}

static bool same_parse(unsigned long c, uint32_t ss, uint64_t n, unsigned fail_at, bool null_why) {
    static struct gpt_table tc, tn;
    struct disk dc = { ss, n, disk_c, 0, fail_at, { { 0, 0 } } }, dn = { ss, n, disk_n, 0, fail_at, { { 0, 0 } } };
    memset(&tc, 0x5A, sizeof tc);
    memset(&tn, 0x5A, sizeof tn);
    memset(scratch_c, 0xA5, sizeof scratch_c);
    memset(scratch_n, 0xA5, sizeof scratch_n);
    const char *why_c = "unset", *why_n = "unset";
    enum gpt_result rc = c_gpt_parse(ss, n, disk_read, &dc, scratch_c, &tc, null_why ? NULL : &why_c);
    enum gpt_result rn = gpt_parse(ss, n, disk_read, &dn, scratch_n, &tn, null_why ? NULL : &why_n);
    bool same = rc == rn && strcmp(why_c, why_n) == 0 && memcmp(&tc, &tn, sizeof tc) == 0
                && memcmp(scratch_c, scratch_n, sizeof scratch_c) == 0 && dc.reads == dn.reads
                && memcmp(dc.log, dn.log, sizeof dc.log) == 0;
    if (!same) {
        report("parse", c);
        if (mismatches <= 20)
            printf("  ss %u n %llu fail_at %u: C %d '%s' reads %u, CeeSafe %d '%s' reads %u\n", ss, (unsigned long long)n, fail_at, rc,
                   why_c, dc.reads, rn, why_n, dn.reads);
    }
    return same;
}

int main(int argc, char **argv) {
    unsigned long cases = argc > 1 ? strtoul(argv[1], NULL, 10) : 20000;
    state = argc > 2 ? strtoull(argv[2], NULL, 10) : 1;
    unsigned long results[4] = { 0 }, built = 0;
    static const char *reasons[64];
    static unsigned long reason_counts[64];
    unsigned nreasons = 0;

    if (memcmp(c_gpt_type_esp, gpt_type_esp, 16) != 0 || memcmp(c_gpt_type_cosmo_root, gpt_type_cosmo_root, 16) != 0)
        report("type GUID", 0);

    for (unsigned long c = 0; c < cases; c++) {
        uint32_t ss = next() % 4 ? 512 : 4096;
        uint64_t min = GPT_BUILD_HEAD_SECTORS(ss) + GPT_BUILD_TAIL_SECTORS(ss) + 1;
        uint64_t n = min - 2 + below((ss == 512 ? MAX_SECTORS : 64) - min + 2);

        /* The writer. */
        unsigned np = random_parts(ss, n);
        uint8_t guid[16];
        for (unsigned k = 0; k < 16; k++)
            guid[k] = (uint8_t)next();
        uint32_t build_ss = next() % 64 == 0 ? 1024 : ss;
        memset(head_c, 0x33, sizeof head_c);
        memset(head_n, 0x33, sizeof head_n);
        memset(tail_c, 0x44, sizeof tail_c);
        memset(tail_n, 0x44, sizeof tail_n);
        bool bc = c_gpt_build(build_ss, n, guid, parts, np, head_c, tail_c);
        bool bn = gpt_build(build_ss, n, guid, parts, np, head_n, tail_n);
        if (bc != bn || memcmp(head_c, head_n, sizeof head_c) != 0 || memcmp(tail_c, tail_n, sizeof tail_c) != 0)
            report("build", c);
        if (c_gpt_build_first_usable(ss) != gpt_build_first_usable(ss) || c_gpt_build_last_usable(ss, n) != gpt_build_last_usable(ss, n))
            report("usable range", c);

        /* The disk: the table just built, or garbage behind a protective MBR, or nothing. */
        size_t bytes = (size_t)n * ss;
        memset(disk_c, 0, bytes);
        unsigned shape = (unsigned)below(16);
        if (bc && shape < 14) {
            memcpy(disk_c, head_c, (size_t)GPT_BUILD_HEAD_SECTORS(ss) * ss);
            memcpy(disk_c + (n - GPT_BUILD_TAIL_SECTORS(ss)) * ss, tail_c, (size_t)GPT_BUILD_TAIL_SECTORS(ss) * ss);
        } else if (shape == 14) {
            for (size_t i = 0; i < bytes; i++)
                disk_c[i] = (uint8_t)next();
            disk_c[510] = 0x55;
            disk_c[511] = 0xAA;
            disk_c[446 + 4] = 0xEE;
        }
        /* Damage. */
        switch (below(6)) {
        case 0:
            break; /* as built */
        case 1: /* flipped bytes, checksums left wrong */
            for (unsigned k = 1 + (unsigned)below(4); k > 0; k--)
                disk_c[below(bytes)] ^= (uint8_t)(1 << below(8));
            break;
        case 2: /* a header field rewritten, both copies resealed: the checks behind the CRCs */
        case 3: {
            uint64_t lba = next() % 2 ? 1 : n - 1;
            rewrite_field(disk_c + lba * ss, ss, n);
            if (next() % 4 == 0)
                rewrite_field(disk_c + (n - 1 - lba + 1 == n ? n - 1 : 1) * ss, ss, n);
            reseal(disk_c, ss, n, 1);
            reseal(disk_c, ss, n, n - 1);
            break;
        }
        case 4: { /* an entry rewritten in both arrays, resealed */
            uint64_t e = (uint64_t)below(GPT_BUILD_ENTRIES);
            unsigned off = (unsigned)below(56);
            uint8_t v = (uint8_t)next();
            disk_c[2 * ss + e * 128 + off] = v;
            disk_c[(n - 1 - GPT_BUILD_ARRAY_SECTORS(ss)) * ss + e * 128 + off] = v;
            reseal(disk_c, ss, n, 1);
            reseal(disk_c, ss, n, n - 1);
            break;
        }
        default: /* the MBR damaged */
            disk_c[446 + 16 * below(4) + below(16)] ^= (uint8_t)next();
            if (next() % 4 == 0)
                disk_c[510 + below(2)] ^= 0xFF;
            break;
        }
        memcpy(disk_n, disk_c, bytes);
        uint64_t parse_n = next() % 16 == 0 ? n - 1 - below(2) : n; /* a disk that seems shorter */
        uint32_t parse_ss = next() % 64 == 0 ? (uint32_t)(next() % 2 ? 1024 : 0) : ss;
        if (parse_ss != ss)
            parse_n = n * ss / 1024 + 1; /* any size: the sector size is refused first */
        unsigned fail_at = next() % 8 == 0 ? 1 + (unsigned)below(6) : 0;
        if (next() % 64 == 0)
            parse_n = below(6);
        if (same_parse(c, parse_ss, parse_n, fail_at, next() % 16 == 0)) {
            const char *why = NULL;
            static struct gpt_table t;
            struct disk d = { parse_ss, parse_n, disk_c, 0, fail_at, { { 0, 0 } } };
            enum gpt_result r = c_gpt_parse(parse_ss, parse_n, disk_read, &d, scratch_c, &t, &why);
            results[r]++;
            if (r == GPT_BAD) {
                unsigned i = 0;
                while (i < nreasons && strcmp(reasons[i], why) != 0)
                    i++;
                if (i == nreasons && nreasons < 64)
                    reasons[nreasons++] = why;
                if (i < 64)
                    reason_counts[i]++;
            }
        }
        built += bc;

        /* CRC-32 and GUID text. */
        size_t len = (size_t)below(300);
        uint32_t crc = (uint32_t)next();
        if (c_gpt_crc32_update(crc, disk_c, len) != gpt_crc32_update(crc, disk_c, len) || c_gpt_crc32(disk_c + 7, len) != gpt_crc32(disk_n + 7, len))
            report("crc32", c);
        char text_c[GPT_GUID_TEXT], text_n[GPT_GUID_TEXT];
        c_gpt_guid_format(guid, text_c);
        gpt_guid_format(guid, text_n);
        if (memcmp(text_c, text_n, sizeof text_c) != 0)
            report("guid format", c);
        char input[40];
        memcpy(input, text_c, sizeof text_c);
        unsigned edits = (unsigned)below(3);
        for (unsigned k = 0; k < edits; k++)
            input[below(37)] = "0aF-gx:\0 9Z"[below(11)];
        if (next() % 8 == 0)
            for (unsigned k = 0; k < 36; k++)
                if (input[k] >= 'a' && input[k] <= 'f')
                    input[k] = (char)(input[k] - 'a' + 'A');
        uint8_t g_c[16], g_n[16];
        memset(g_c, 0x77, 16);
        memset(g_n, 0x77, 16);
        if (c_gpt_guid_parse(input, g_c) != gpt_guid_parse(input, g_n) || memcmp(g_c, g_n, 16) != 0)
            report("guid parse", c);
    }
    printf("parse results: %lu OK, %lu NONE, %lu BAD, %lu IO; %lu tables built; %u reasons:\n", results[0], results[1], results[2],
           results[3], built, nreasons);
    for (unsigned i = 0; i < nreasons; i++)
        printf("  %6lu %s\n", reason_counts[i], reasons[i]);
    printf("%lu cases, %lu mismatches\n", cases, mismatches);
    return mismatches != 0;
}
