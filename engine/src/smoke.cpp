#include "chromasunder/c_api.h"

#include "chromasunder/smoke.hpp"
#include "chromasunder/version.hpp"

extern "C" {

std::uint32_t cs_abi_version() { return chromasunder::abi_version; }

std::int32_t cs_smoke_add(std::int32_t a, std::int32_t b) {
  return chromasunder::smoke_add(a, b);
}

}
