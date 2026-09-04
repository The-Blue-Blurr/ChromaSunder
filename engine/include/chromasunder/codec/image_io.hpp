#pragma once

#include "chromasunder/codec/image_codec.hpp"
#include "chromasunder/processing/mask.hpp"

#include <filesystem>

namespace chromasunder::codec {

enum class ImageFileFormat { png, jpeg };

[[nodiscard]] DecodeResult decode_image_file(const std::filesystem::path& path);
[[nodiscard]] Error encode_image_atomic(const image::AnyImage& image,
                                        const std::filesystem::path& destination,
                                        ImageFileFormat format,
                                        const EncodeOptions& options = {});

struct AuxiliaryResult {
  std::optional<processing::BinaryImage> image;
  Error error;
};

[[nodiscard]] AuxiliaryResult load_auxiliary_image(const std::filesystem::path& path,
                                                   std::size_t canonical_width,
                                                   std::size_t canonical_height);

}  // namespace chromasunder::codec
