#pragma once

#include <cstddef>
#include <compare>
#include <concepts>
#include <cstdint>
#include <type_traits>

namespace chromasunder::image {

enum class PixelFormat { rgba8, rgba16 };

template <typename Channel>
concept ChannelType = std::same_as<Channel, std::uint8_t> ||
                      std::same_as<Channel, std::uint16_t>;

template <ChannelType Channel>
struct RgbaPixel {
  Channel r{};
  Channel g{};
  Channel b{};
  Channel a{};

  auto operator<=>(const RgbaPixel&) const = default;
};

template <ChannelType Channel>
inline constexpr PixelFormat pixel_format_v =
    std::same_as<Channel, std::uint8_t> ? PixelFormat::rgba8 : PixelFormat::rgba16;

[[nodiscard]] constexpr std::size_t bytes_per_pixel(PixelFormat format) noexcept {
  return format == PixelFormat::rgba8 ? 4U : 8U;
}

}  // namespace chromasunder::image
