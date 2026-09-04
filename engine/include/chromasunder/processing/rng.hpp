#pragma once

#include <cstdint>
#include <limits>

namespace chromasunder::processing {

inline constexpr std::uint64_t rng_semantics_version = 1;

class SplitMix64 {
 public:
  explicit constexpr SplitMix64(std::uint64_t seed) noexcept : state_(seed) {}

  [[nodiscard]] constexpr std::uint64_t next_u64() noexcept {
    state_ += 0x9E3779B97F4A7C15ULL;
    auto value = state_;
    value = (value ^ (value >> 30U)) * 0xBF58476D1CE4E5B9ULL;
    value = (value ^ (value >> 27U)) * 0x94D049BB133111EBULL;
    return value ^ (value >> 31U);
  }

  [[nodiscard]] double uniform_unit() noexcept {
    return static_cast<double>(next_u64() >> 11U) * 0x1.0p-53;
  }

  [[nodiscard]] std::uint64_t bounded(std::uint64_t exclusive_upper) noexcept {
    if (exclusive_upper == 0) return 0;
    const auto threshold = static_cast<std::uint64_t>(-exclusive_upper) % exclusive_upper;
    while (true) {
      const auto value = next_u64();
      if (value >= threshold) return value % exclusive_upper;
    }
  }

  [[nodiscard]] bool percentage(double percentage) noexcept {
    return percentage >= 100.0 || (percentage > 0.0 && uniform_unit() * 100.0 < percentage);
  }

 private:
  std::uint64_t state_;
};

[[nodiscard]] constexpr std::uint64_t mix_seed(std::uint64_t value) noexcept {
  value = (value ^ (value >> 30U)) * 0xBF58476D1CE4E5B9ULL;
  value = (value ^ (value >> 27U)) * 0x94D049BB133111EBULL;
  return value ^ (value >> 31U);
}

[[nodiscard]] constexpr std::uint64_t derive_path_seed(std::uint64_t global_seed,
                                                       std::uint64_t stable_path_id) noexcept {
  const auto versioned = stable_path_id ^ (rng_semantics_version * 0xD6E8FEB86659FD93ULL);
  return mix_seed(global_seed ^ mix_seed(versioned));
}

}  // namespace chromasunder::processing
