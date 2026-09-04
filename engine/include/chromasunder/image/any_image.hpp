#pragma once

#include "chromasunder/image/image_buffer.hpp"

#include <cstdint>
#include <variant>

namespace chromasunder::image {

using AnyImage = std::variant<ImageBuffer<std::uint8_t>, ImageBuffer<std::uint16_t>>;

}  // namespace chromasunder::image
