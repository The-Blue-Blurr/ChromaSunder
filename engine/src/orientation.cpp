#include "chromasunder/codec/orientation.hpp"

#include <cstddef>
#include <cstdint>
#include <span>

namespace chromasunder::codec {
namespace {

bool read_u16(std::span<const std::uint8_t> bytes, std::size_t offset, bool little,
              std::uint16_t& value) {
  if (offset + 2 > bytes.size()) return false;
  value = little ? static_cast<std::uint16_t>(bytes[offset] | (bytes[offset + 1] << 8U))
                 : static_cast<std::uint16_t>((bytes[offset] << 8U) | bytes[offset + 1]);
  return true;
}

bool read_u32(std::span<const std::uint8_t> bytes, std::size_t offset, bool little,
              std::uint32_t& value) {
  if (offset + 4 > bytes.size()) return false;
  if (little) {
    value = static_cast<std::uint32_t>(bytes[offset]) |
            (static_cast<std::uint32_t>(bytes[offset + 1]) << 8U) |
            (static_cast<std::uint32_t>(bytes[offset + 2]) << 16U) |
            (static_cast<std::uint32_t>(bytes[offset + 3]) << 24U);
  } else {
    value = (static_cast<std::uint32_t>(bytes[offset]) << 24U) |
            (static_cast<std::uint32_t>(bytes[offset + 1]) << 16U) |
            (static_cast<std::uint32_t>(bytes[offset + 2]) << 8U) | bytes[offset + 3];
  }
  return true;
}

}  // namespace

std::uint16_t parse_exif_orientation(std::span<const std::uint8_t> exif) noexcept {
  if (exif.size() >= 6 && exif[0] == 'E' && exif[1] == 'x' && exif[2] == 'i' &&
      exif[3] == 'f' && exif[4] == 0 && exif[5] == 0) {
    exif = exif.subspan(6);
  }
  if (exif.size() < 8) return 1;
  const bool little = exif[0] == 'I' && exif[1] == 'I';
  const bool big = exif[0] == 'M' && exif[1] == 'M';
  if (!little && !big) return 1;
  std::uint16_t marker{};
  std::uint32_t ifd_offset{};
  if (!read_u16(exif, 2, little, marker) || marker != 42 ||
      !read_u32(exif, 4, little, ifd_offset))
    return 1;
  std::uint16_t count{};
  if (!read_u16(exif, ifd_offset, little, count)) return 1;
  for (std::size_t index = 0; index < count; ++index) {
    const auto offset = static_cast<std::size_t>(ifd_offset) + 2 + index * 12;
    std::uint16_t tag{};
    std::uint16_t type{};
    std::uint32_t item_count{};
    if (!read_u16(exif, offset, little, tag) || !read_u16(exif, offset + 2, little, type) ||
        !read_u32(exif, offset + 4, little, item_count))
      return 1;
    if (tag == 0x0112 && type == 3 && item_count == 1) {
      std::uint16_t orientation{};
      if (read_u16(exif, offset + 8, little, orientation) && orientation >= 1 &&
          orientation <= 8)
        return orientation;
      return 1;
    }
  }
  return 1;
}

}  // namespace chromasunder::codec
