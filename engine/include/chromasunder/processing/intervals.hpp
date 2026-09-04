#pragma once

#include "chromasunder/image/pixel_format.hpp"
#include "chromasunder/processing/rng.hpp"
#include "chromasunder/processing/settings.hpp"
#include "chromasunder/processing/sorting.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <vector>

namespace chromasunder::processing {

struct Interval {
  std::size_t start{};
  std::size_t end{};
  auto operator<=>(const Interval&) const = default;
};

inline void append_interval(std::vector<Interval>& result, std::size_t start,
                            std::size_t end) {
  if (end >= start + 2) result.push_back({start, end});
}

template <image::ChannelType Channel>
[[nodiscard]] std::vector<Interval> detect_intervals(
    std::span<const image::RgbaPixel<Channel>> pixels, IntervalMode mode, double lower,
    double upper, std::size_t characteristic_length, SplitMix64& rng,
    std::span<const std::uint8_t> interval_bits = {}) {
  std::vector<Interval> result;
  const auto length = pixels.size();
  if (mode == IntervalMode::none) {
    append_interval(result, 0, length);
    return result;
  }
  if (mode == IntervalMode::threshold) {
    const auto lower_key = normalized_lower_key(lower);
    const auto upper_key = normalized_key(upper);
    constexpr auto denominator =
        2ULL * static_cast<std::uint64_t>(std::numeric_limits<Channel>::max());
    std::size_t start = 0;
    bool active = false;
    for (std::size_t index = 0; index <= length; ++index) {
      const auto numerator = index < length
                                 ? static_cast<std::uint64_t>(lightness_sum(pixels[index])) *
                                       key_scale
                                 : 0;
      const bool enabled = index < length && numerator >= lower_key * denominator &&
                           numerator <= upper_key * denominator;
      if (enabled && !active) {
        start = index;
        active = true;
      } else if (!enabled && active) {
        append_interval(result, start, index);
        active = false;
      }
    }
    return result;
  }
  if (mode == IntervalMode::edges) {
    if (length < 2) return result;
    const auto threshold = normalized_lower_key(lower);
    constexpr auto denominator =
        2ULL * static_cast<std::uint64_t>(std::numeric_limits<Channel>::max());
    std::size_t start = 0;
    auto previous = lightness_sum(pixels.front());
    for (std::size_t index = 1; index < length; ++index) {
      const auto current = lightness_sum(pixels[index]);
      const auto difference = current > previous ? current - previous : previous - current;
      if (static_cast<std::uint64_t>(difference) * key_scale >= threshold * denominator) {
        append_interval(result, start, index);
        start = index;
      }
      previous = current;
    }
    append_interval(result, start, length);
    return result;
  }
  if (mode == IntervalMode::random || mode == IntervalMode::waves) {
    std::size_t start = 0;
    while (start < length) {
      std::size_t size = 1;
      if (mode == IntervalMode::random) {
        size = std::max<std::size_t>(
            1, static_cast<std::size_t>(static_cast<double>(characteristic_length) *
                                       rng.uniform_unit()));
      } else {
        const auto variation = static_cast<std::size_t>(rng.bounded(11));
        size = characteristic_length > std::numeric_limits<std::size_t>::max() - variation
                   ? std::numeric_limits<std::size_t>::max()
                   : characteristic_length + variation;
      }
      const auto end = std::min(length, start + std::min(size, length - start));
      append_interval(result, start, end);
      start = end;
    }
    return result;
  }
  if (mode == IntervalMode::file) {
    std::size_t start = 0;
    bool active = false;
    for (std::size_t index = 0; index <= length; ++index) {
      const bool enabled = index < interval_bits.size() && interval_bits[index] != 0;
      if (enabled && !active) {
        start = index;
        active = true;
      } else if (!enabled && active) {
        append_interval(result, start, index);
        active = false;
      }
    }
    return result;
  }
  if (mode == IntervalMode::file_edges && !interval_bits.empty()) {
    const auto threshold = normalized_lower_key(lower);
    std::vector<std::size_t> boundaries{0};
    std::uint64_t previous = 0;
    for (std::size_t index = 0; index < length; ++index) {
      const auto current = index < interval_bits.size() && interval_bits[index] != 0 ? key_scale : 0;
      const auto difference = current > previous ? current - previous : previous - current;
      if (difference >= threshold && boundaries.back() != index) boundaries.push_back(index);
      previous = current;
    }
    if (boundaries.back() != length) boundaries.push_back(length);
    for (std::size_t index = 1; index < boundaries.size(); ++index) {
      append_interval(result, boundaries[index - 1], boundaries[index]);
    }
  }
  return result;
}

}  // namespace chromasunder::processing
