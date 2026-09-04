#pragma once

#include "chromasunder/error.hpp"
#include "chromasunder/image/image_buffer.hpp"

#include <cstdint>
#include <span>
#include <vector>
#include <optional>

namespace chromasunder::color {

[[nodiscard]] std::vector<std::uint8_t> srgb_profile_bytes();

enum class ProfileColorSpace { untagged, rgb, gray, cmyk, unsupported, invalid };

[[nodiscard]] ProfileColorSpace inspect_profile(
    std::span<const std::uint8_t> source_profile) noexcept;

struct Cmyk8Result {
  std::optional<image::ImageBuffer<std::uint8_t>> image;
  Error error;
};

[[nodiscard]] Cmyk8Result convert_cmyk8_to_srgb(
    std::span<const std::uint8_t> cmyk, std::size_t width, std::size_t height,
    std::span<const std::uint8_t> source_profile);

template <image::ChannelType Channel>
[[nodiscard]] Error convert_to_srgb(image::ImageBuffer<Channel>& image,
                                    std::span<const std::uint8_t> source_profile);

extern template Error convert_to_srgb<std::uint8_t>(
    image::ImageBuffer<std::uint8_t>&, std::span<const std::uint8_t>);
extern template Error convert_to_srgb<std::uint16_t>(
    image::ImageBuffer<std::uint16_t>&, std::span<const std::uint8_t>);

}  // namespace chromasunder::color
