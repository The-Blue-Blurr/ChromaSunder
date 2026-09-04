#pragma once

#include "chromasunder/image/pixel_format.hpp"
#include "chromasunder/processing/settings.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace chromasunder::processing {

inline constexpr std::uint64_t key_scale = 1ULL << 40U;

template <image::ChannelType Channel>
[[nodiscard]] constexpr std::uint32_t lightness_sum(
    const image::RgbaPixel<Channel>& pixel) noexcept {
  const auto maximum = std::max({pixel.r, pixel.g, pixel.b});
  const auto minimum = std::min({pixel.r, pixel.g, pixel.b});
  return static_cast<std::uint32_t>(maximum) + static_cast<std::uint32_t>(minimum);
}

template <image::ChannelType Channel>
[[nodiscard]] constexpr std::uint64_t hue_key(
    const image::RgbaPixel<Channel>& pixel) noexcept {
  const auto maximum = std::max({pixel.r, pixel.g, pixel.b});
  const auto minimum = std::min({pixel.r, pixel.g, pixel.b});
  const auto delta = static_cast<std::int64_t>(maximum) - minimum;
  if (delta == 0) return 0;

  std::int64_t sector_numerator{};
  std::int64_t sector{};
  if (pixel.r == maximum) {
    sector_numerator = static_cast<std::int64_t>(pixel.g) - pixel.b;
    sector = 0;
  } else if (pixel.g == maximum) {
    sector_numerator = static_cast<std::int64_t>(pixel.b) - pixel.r;
    sector = 2;
  } else {
    sector_numerator = static_cast<std::int64_t>(pixel.r) - pixel.g;
    sector = 4;
  }
  auto numerator = sector * delta + sector_numerator;
  const auto denominator = 6 * delta;
  if (numerator < 0) numerator += denominator;
  return static_cast<std::uint64_t>(numerator) * key_scale /
         static_cast<std::uint64_t>(denominator);
}

template <image::ChannelType Channel>
[[nodiscard]] constexpr std::uint64_t saturation_key(
    const image::RgbaPixel<Channel>& pixel) noexcept {
  const auto maximum = std::max({pixel.r, pixel.g, pixel.b});
  const auto minimum = std::min({pixel.r, pixel.g, pixel.b});
  const auto delta = static_cast<std::uint64_t>(maximum) - minimum;
  if (delta == 0) return 0;
  constexpr auto channel_max = static_cast<std::uint64_t>(std::numeric_limits<Channel>::max());
  const auto sum = static_cast<std::uint64_t>(maximum) + minimum;
  const auto denominator = sum <= channel_max ? sum : 2 * channel_max - sum;
  return delta * key_scale / denominator;
}

template <image::ChannelType Channel>
[[nodiscard]] constexpr std::uint64_t sorting_key(
    const image::RgbaPixel<Channel>& pixel, SortingMode mode) noexcept {
  switch (mode) {
    case SortingMode::lightness:
      return lightness_sum(pixel);
    case SortingMode::hue:
      return hue_key(pixel);
    case SortingMode::saturation:
      return saturation_key(pixel);
    case SortingMode::intensity:
      return static_cast<std::uint64_t>(pixel.r) + pixel.g + pixel.b;
    case SortingMode::minimum:
      return std::min({pixel.r, pixel.g, pixel.b});
  }
  return 0;
}

template <image::ChannelType Channel>
void stable_sort_pixels(std::vector<image::RgbaPixel<Channel>>& pixels, SortingMode mode) {
  struct Entry {
    image::RgbaPixel<Channel> pixel;
    std::uint64_t key;
  };
  std::vector<Entry> entries;
  entries.reserve(pixels.size());
  for (const auto& pixel : pixels) entries.push_back({pixel, sorting_key(pixel, mode)});
  std::stable_sort(entries.begin(), entries.end(),
                   [](const Entry& left, const Entry& right) { return left.key < right.key; });
  for (std::size_t index = 0; index < entries.size(); ++index) pixels[index] = entries[index].pixel;
}

[[nodiscard]] inline std::uint64_t normalized_key(double value) noexcept {
  if (value <= 0.0) return 0;
  if (value >= 1.0) return key_scale;
  return static_cast<std::uint64_t>(value * static_cast<double>(key_scale));
}

[[nodiscard]] inline std::uint64_t normalized_lower_key(double value) noexcept {
  if (value <= 0.0) return 0;
  if (value >= 1.0) return key_scale;
  return static_cast<std::uint64_t>(
      std::ceil(value * static_cast<double>(key_scale)));
}

template <image::ChannelType Channel>
[[nodiscard]] constexpr std::uint64_t lightness_key(
    const image::RgbaPixel<Channel>& pixel) noexcept {
  constexpr auto channel_max = static_cast<std::uint64_t>(std::numeric_limits<Channel>::max());
  return static_cast<std::uint64_t>(lightness_sum(pixel)) * key_scale / (2 * channel_max);
}

}  // namespace chromasunder::processing
