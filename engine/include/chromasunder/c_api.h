#ifndef CHROMASUNDER_C_API_H
#define CHROMASUNDER_C_API_H

#include <stdint.h>

#include "chromasunder/export.h"

#ifdef __cplusplus
extern "C" {
#endif

CS_API uint32_t cs_abi_version(void);
CS_API int32_t cs_smoke_add(int32_t a, int32_t b);

#ifdef __cplusplus
}
#endif

#endif
