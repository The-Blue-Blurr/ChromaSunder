#ifndef CHROMASUNDER_SMOKE_HPP
#define CHROMASUNDER_SMOKE_HPP

#include <cstdint>
#include <limits>

namespace chromasunder {

[[nodiscard]] constexpr std::int32_t smoke_add(std::int32_t a, std::int32_t b) noexcept {
  const auto result = static_cast<std::int64_t>(a) + static_cast<std::int64_t>(b);
  if (result > std::numeric_limits<std::int32_t>::max()) {
    return std::numeric_limits<std::int32_t>::max();
  }
  if (result < std::numeric_limits<std::int32_t>::min()) {
    return std::numeric_limits<std::int32_t>::min();
  }
  return static_cast<std::int32_t>(result);
}

}  // namespace chromasunder

#endif
