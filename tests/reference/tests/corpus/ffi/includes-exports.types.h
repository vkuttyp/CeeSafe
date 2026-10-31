/* C types for ffi/includes-exports.cee. Like a kernel header that includes the generated definition of a type
 * CeeSafe owns (ADR 0030), this header includes the program's own ceesafe_exports.h. */
#ifndef INCLUDES_EXPORTS_TYPES_H
#define INCLUDES_EXPORTS_TYPES_H

#include <stdint.h>

typedef struct {
    uint32_t taken;
} ie_lock_t;

#include "ceesafe_exports.h" /* struct ie_box */

uint32_t ie_sum(const struct ie_box *b);

#endif
