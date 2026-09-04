#pragma once

#include "chromasunder/image/pixel_format.hpp"

#include <cassert>
#include <cstddef>
#include <span>

namespace chromasunder::image {

template <ChannelType Channel>
class ImageView {
 public:
  using Pixel = RgbaPixel<Channel>;

  constexpr ImageView() = default;
  constexpr ImageView(const Pixel* data, std::size_t width, std::size_t height,
                      std::size_t stride_pixels) noexcept
      : data_(data), width_(width), height_(height), stride_pixels_(stride_pixels) {}

  [[nodiscard]] constexpr std::size_t width() const noexcept { return width_; }
  [[nodiscard]] constexpr std::size_t height() const noexcept { return height_; }
  [[nodiscard]] constexpr std::size_t stride_pixels() const noexcept { return stride_pixels_; }
  [[nodiscard]] constexpr std::size_t stride_bytes() const noexcept {
    return stride_pixels_ * sizeof(Pixel);
  }
  [[nodiscard]] constexpr PixelFormat format() const noexcept { return pixel_format_v<Channel>; }
  [[nodiscard]] std::span<const Pixel> row(std::size_t y) const noexcept {
    assert(y < height_);
    return {data_ + y * stride_pixels_, width_};
  }
  [[nodiscard]] const Pixel& at(std::size_t x, std::size_t y) const noexcept {
    assert(x < width_ && y < height_);
    return data_[y * stride_pixels_ + x];
  }

 private:
  const Pixel* data_{nullptr};
  std::size_t width_{0};
  std::size_t height_{0};
  std::size_t stride_pixels_{0};
};

template <ChannelType Channel>
class MutableImageView {
 public:
  using Pixel = RgbaPixel<Channel>;

  constexpr MutableImageView() = default;
  constexpr MutableImageView(Pixel* data, std::size_t width, std::size_t height,
                             std::size_t stride_pixels) noexcept
      : data_(data), width_(width), height_(height), stride_pixels_(stride_pixels) {}

  [[nodiscard]] constexpr std::size_t width() const noexcept { return width_; }
  [[nodiscard]] constexpr std::size_t height() const noexcept { return height_; }
  [[nodiscard]] constexpr std::size_t stride_pixels() const noexcept { return stride_pixels_; }
  [[nodiscard]] constexpr std::size_t stride_bytes() const noexcept {
    return stride_pixels_ * sizeof(Pixel);
  }
  [[nodiscard]] constexpr PixelFormat format() const noexcept { return pixel_format_v<Channel>; }
  [[nodiscard]] std::span<Pixel> row(std::size_t y) const noexcept {
    assert(y < height_);
    return {data_ + y * stride_pixels_, width_};
  }
  [[nodiscard]] Pixel& at(std::size_t x, std::size_t y) const noexcept {
    assert(x < width_ && y < height_);
    return data_[y * stride_pixels_ + x];
  }
  [[nodiscard]] ImageView<Channel> read_only() const noexcept {
    return {data_, width_, height_, stride_pixels_};
  }

 private:
  Pixel* data_{nullptr};
  std::size_t width_{0};
  std::size_t height_{0};
  std::size_t stride_pixels_{0};
};

}  // namespace chromasunder::image
