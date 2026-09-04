#pragma once

#include "chromasunder/error.hpp"

#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <limits>
#include <vector>

namespace chromasunder::processing {

class BinaryImage {
 public:
  BinaryImage() = default;
  BinaryImage(std::size_t width, std::size_t height, std::vector<std::uint8_t> bits)
      : width_(width), height_(height), bits_(std::move(bits)) {
    if ((width_ != 0 && height_ > std::numeric_limits<std::size_t>::max() / width_) ||
        width_ * height_ != bits_.size()) {
      throw std::invalid_argument("Binary image storage does not match its dimensions.");
    }
  }

  [[nodiscard]] std::size_t width() const noexcept { return width_; }
  [[nodiscard]] std::size_t height() const noexcept { return height_; }
  [[nodiscard]] std::size_t size_bytes() const noexcept { return bits_.size(); }
  [[nodiscard]] bool at(std::size_t x, std::size_t y) const noexcept {
    return bits_[y * width_ + x] != 0;
  }
  [[nodiscard]] std::span<const std::uint8_t> bits() const noexcept { return bits_; }

 private:
  std::size_t width_{0};
  std::size_t height_{0};
  std::vector<std::uint8_t> bits_;
};

[[nodiscard]] inline Error validate_auxiliary_dimensions(const BinaryImage& image,
                                                         std::size_t width,
                                                         std::size_t height) {
  if (image.width() != width || image.height() != height) {
    return {ErrorCode::dimension_mismatch,
            "Auxiliary image dimensions must exactly match the canonical source."};
  }
  return {};
}

}  // namespace chromasunder::processing
