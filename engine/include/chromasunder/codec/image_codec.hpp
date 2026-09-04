#pragma once

#include "chromasunder/error.hpp"
#include "chromasunder/image/any_image.hpp"

#include <cstdint>
#include <filesystem>
#include <optional>
#include <span>
#include <string_view>
#include <vector>

namespace chromasunder::codec {

struct ColorProfile {
  std::vector<std::uint8_t> bytes;
  bool source_was_tagged{false};
};

struct DecodedImage {
  image::AnyImage pixels;
  ColorProfile working_profile;
  std::uint16_t applied_orientation{1};
};

struct DecodeResult {
  std::optional<DecodedImage> image;
  Error error;
};

struct EncodeOptions {
  int jpeg_quality{90};
};

class ImageCodec {
 public:
  virtual ~ImageCodec() = default;
  [[nodiscard]] virtual DecodeResult decode(std::span<const std::uint8_t> bytes) const = 0;
  [[nodiscard]] virtual Error encode(const image::AnyImage& image,
                                     const std::filesystem::path& destination,
                                     const EncodeOptions& options = {}) const = 0;
};

class PngCodec final : public ImageCodec {
 public:
  [[nodiscard]] DecodeResult decode(std::span<const std::uint8_t> bytes) const override;
  [[nodiscard]] Error encode(const image::AnyImage& image,
                             const std::filesystem::path& destination,
                             const EncodeOptions& options = {}) const override;
};

class JpegCodec final : public ImageCodec {
 public:
  [[nodiscard]] DecodeResult decode(std::span<const std::uint8_t> bytes) const override;
  [[nodiscard]] Error encode(const image::AnyImage& image,
                             const std::filesystem::path& destination,
                             const EncodeOptions& options = {}) const override;
};

[[nodiscard]] std::vector<std::uint8_t> jpeg_rgb8_scratch(const image::AnyImage& image);

}  // namespace chromasunder::codec
