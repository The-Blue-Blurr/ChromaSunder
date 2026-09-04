#pragma once

#include "chromasunder/image/image_buffer.hpp"

#include <cstdint>
#include <span>
#include <optional>

namespace chromasunder::codec {

[[nodiscard]] std::uint16_t parse_exif_orientation(std::span<const std::uint8_t> exif) noexcept;

template <image::ChannelType Channel>
struct OrientationResult {
  std::optional<image::ImageBuffer<Channel>> image;
  Error error;
};

template <image::ChannelType Channel>
[[nodiscard]] OrientationResult<Channel> apply_orientation(
    const image::ImageBuffer<Channel>& source, std::uint16_t orientation) {
  const bool swaps_dimensions = orientation >= 5 && orientation <= 8;
  const auto output_width = swaps_dimensions ? source.height() : source.width();
  const auto output_height = swaps_dimensions ? source.width() : source.height();
  auto [output, error] = image::ImageBuffer<Channel>::create(output_width, output_height);
  if (error) return {{}, error};
  for (std::size_t y = 0; y < source.height(); ++y) {
    for (std::size_t x = 0; x < source.width(); ++x) {
      std::size_t output_x = x;
      std::size_t output_y = y;
      switch (orientation) {
        case 2:
          output_x = source.width() - 1 - x;
          break;
        case 3:
          output_x = source.width() - 1 - x;
          output_y = source.height() - 1 - y;
          break;
        case 4:
          output_y = source.height() - 1 - y;
          break;
        case 5:
          output_x = y;
          output_y = x;
          break;
        case 6:
          output_x = source.height() - 1 - y;
          output_y = x;
          break;
        case 7:
          output_x = source.height() - 1 - y;
          output_y = source.width() - 1 - x;
          break;
        case 8:
          output_x = y;
          output_y = source.width() - 1 - x;
          break;
        default:
          break;
      }
      output->mutable_view().at(output_x, output_y) = source.view().at(x, y);
    }
  }
  return {std::move(*output), {}};
}

}  // namespace chromasunder::codec
