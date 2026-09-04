#include <cstdint>
#include <iostream>
#include <limits>

#include "chromasunder/c_api.h"
#include "chromasunder/smoke.hpp"

int main() {
  if (cs_abi_version() != 1U) {
    std::cerr << "unexpected ABI version\n";
    return 1;
  }
  if (cs_smoke_add(20, 22) != 42) {
    std::cerr << "C ABI smoke addition failed\n";
    return 1;
  }
  if (chromasunder::smoke_add(-5, 3) != -2) {
    std::cerr << "C++ smoke addition failed\n";
    return 1;
  }
  if (cs_smoke_add(std::numeric_limits<std::int16_t>::max(), 1) != 32768) {
    std::cerr << "fixed-width integer behavior failed\n";
    return 1;
  }
  if (cs_smoke_add(std::numeric_limits<std::int32_t>::max(), 1) !=
      std::numeric_limits<std::int32_t>::max()) {
    std::cerr << "overflow handling failed\n";
    return 1;
  }
  return 0;
}
