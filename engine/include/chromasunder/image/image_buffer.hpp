#pragma once

#include "chromasunder/error.hpp"
#include "chromasunder/image/image_view.hpp"

#include <cstddef>
#include <limits>
#include <new>
#include <optional>
#include <stdexcept>
#include <utility>
#include <vector>

namespace chromasunder::image {

template <typename T>
class HeapStorage {
 public:
  HeapStorage() = default;
  explicit HeapStorage(std::size_t count) : values_(count) {}

  [[nodiscard]] T* data() noexcept { return values_.data(); }
  [[nodiscard]] const T* data() const noexcept { return values_.data(); }
  [[nodiscard]] std::size_t size() const noexcept { return values_.size(); }
  [[nodiscard]] std::vector<T>& values() noexcept { return values_; }
  [[nodiscard]] const std::vector<T>& values() const noexcept { return values_; }

 private:
  std::vector<T> values_;
};

template <ChannelType Channel, template <typename> typename Storage = HeapStorage>
class ImageBuffer {
 public:
  using Pixel = RgbaPixel<Channel>;

  ImageBuffer() = default;

  [[nodiscard]] static std::pair<std::optional<ImageBuffer>, Error> create(
      std::size_t width, std::size_t height) noexcept {
    if (width != 0 && height > std::numeric_limits<std::size_t>::max() / width) {
      return {std::nullopt, {ErrorCode::size_overflow, "Image dimensions overflow."}};
    }
    const auto count = width * height;
    if (count > std::numeric_limits<std::size_t>::max() / sizeof(Pixel)) {
      return {std::nullopt, {ErrorCode::size_overflow, "Image byte size overflows."}};
    }
    try {
      if (count > std::vector<Pixel>{}.max_size()) {
        return {std::nullopt, {ErrorCode::size_overflow, "Image exceeds storage limits."}};
      }
      return {ImageBuffer(width, height, Storage<Pixel>(count)), {}};
    } catch (const std::bad_alloc&) {
      return {std::nullopt, {ErrorCode::allocation_failed, "Image allocation failed."}};
    } catch (const std::length_error&) {
      return {std::nullopt, {ErrorCode::size_overflow, "Image exceeds storage limits."}};
    }
  }

  [[nodiscard]] std::size_t width() const noexcept { return width_; }
  [[nodiscard]] std::size_t height() const noexcept { return height_; }
  [[nodiscard]] std::size_t stride_pixels() const noexcept { return width_; }
  [[nodiscard]] std::size_t stride_bytes() const noexcept { return width_ * sizeof(Pixel); }
  [[nodiscard]] std::size_t size_bytes() const noexcept { return storage_.size() * sizeof(Pixel); }
  [[nodiscard]] PixelFormat format() const noexcept { return pixel_format_v<Channel>; }
  [[nodiscard]] ImageView<Channel> view() const noexcept {
    return {storage_.data(), width_, height_, width_};
  }
  [[nodiscard]] MutableImageView<Channel> mutable_view() noexcept {
    return {storage_.data(), width_, height_, width_};
  }
  [[nodiscard]] std::span<Pixel> pixels() noexcept {
    return {storage_.data(), storage_.size()};
  }
  [[nodiscard]] std::span<const Pixel> pixels() const noexcept {
    return {storage_.data(), storage_.size()};
  }

 private:
  ImageBuffer(std::size_t width, std::size_t height, Storage<Pixel>&& storage)
      : width_(width), height_(height), storage_(std::move(storage)) {}

  std::size_t width_{0};
  std::size_t height_{0};
  Storage<Pixel> storage_;
};

}  // namespace chromasunder::image
