#include "chromasunder/codec/image_codec.hpp"

#include "chromasunder/codec/orientation.hpp"
#include "chromasunder/color/color_management.hpp"
#include "chromasunder/image/image_buffer.hpp"

#include <jpeglib.h>

#include <algorithm>
#include <csetjmp>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <climits>
#include <span>
#include <new>
#include <stdexcept>
#include <utility>
#include <vector>

namespace chromasunder::codec {
namespace {

struct JpegErrorManager {
  jpeg_error_mgr base;
  std::jmp_buf jump;
};

struct JpegDecodeResources {
  std::uint8_t* raw_pixels;
  std::uint8_t* scanline;
};

struct JpegEncodeResources {
  std::uint8_t* marker;
};

void jpeg_error_exit(j_common_ptr common) {
  auto* error = reinterpret_cast<JpegErrorManager*>(common->err);
  std::longjmp(error->jump, 1);
}

void jpeg_emit_message(j_common_ptr common, int message_level) {
  if (message_level < 0) jpeg_error_exit(common);
}

FILE* open_file(const std::filesystem::path& path, const char* mode) {
#ifdef _WIN32
  const auto wide_mode = mode[0] == 'w' ? L"wb" : L"rb";
  return _wfopen(path.c_str(), wide_mode);
#else
  return std::fopen(path.c_str(), mode);
#endif
}

struct JpegMetadata {
  std::uint16_t orientation{1};
  std::vector<std::vector<std::uint8_t>> icc_chunks;
  std::size_t expected_chunks{0};
  bool saw_icc{false};
};

JpegMetadata parse_metadata(std::span<const std::uint8_t> bytes) {
  JpegMetadata metadata;
  if (bytes.size() < 2 || bytes[0] != 0xFF || bytes[1] != 0xD8) return metadata;
  std::size_t offset = 2;
  while (offset + 4 <= bytes.size()) {
    while (offset < bytes.size() && bytes[offset] == 0xFF) ++offset;
    if (offset >= bytes.size()) break;
    const auto marker = bytes[offset++];
    if (marker == 0xDA || marker == 0xD9) break;
    if (marker == 0x01 || (marker >= 0xD0 && marker <= 0xD7)) continue;
    if (offset + 2 > bytes.size()) break;
    const auto length = static_cast<std::size_t>((bytes[offset] << 8U) | bytes[offset + 1]);
    if (length < 2 || length > bytes.size() - offset) break;
    const auto payload = bytes.subspan(offset + 2, length - 2);
    if (marker == 0xE1 && payload.size() >= 6 &&
        std::memcmp(payload.data(), "Exif\0\0", 6) == 0) {
      metadata.orientation = parse_exif_orientation(payload);
    }
    constexpr char icc_signature[] = "ICC_PROFILE\0";
    if (marker == 0xE2 && payload.size() >= 14 &&
        std::memcmp(payload.data(), icc_signature, 12) == 0) {
      metadata.saw_icc = true;
      const auto sequence = payload[12];
      const auto count = payload[13];
      if (sequence != 0 && count != 0) {
        metadata.expected_chunks = count;
        if (metadata.icc_chunks.size() < count) metadata.icc_chunks.resize(count);
        if (sequence <= count)
          metadata.icc_chunks[sequence - 1] =
              std::vector<std::uint8_t>(payload.begin() + 14, payload.end());
      }
    }
    offset += length;
  }
  return metadata;
}

std::vector<std::uint8_t> combine_icc(const JpegMetadata& metadata) {
  if (metadata.expected_chunks == 0 || metadata.icc_chunks.size() != metadata.expected_chunks)
    return {};
  std::size_t size = 0;
  for (const auto& chunk : metadata.icc_chunks) {
    if (chunk.empty()) return {};
    size += chunk.size();
  }
  std::vector<std::uint8_t> profile;
  profile.reserve(size);
  for (const auto& chunk : metadata.icc_chunks)
    profile.insert(profile.end(), chunk.begin(), chunk.end());
  return profile;
}

void write_icc_markers(j_compress_ptr compressor, std::span<const std::uint8_t> profile,
                       JpegEncodeResources* resources) {
  constexpr std::size_t maximum_chunk = 65519;
  const auto count = (profile.size() + maximum_chunk - 1) / maximum_chunk;
  if (count == 0 || count > 255) return;
  constexpr std::uint8_t signature[12] = {'I', 'C', 'C', '_', 'P', 'R',
                                          'O', 'F', 'I', 'L', 'E', 0};
  for (std::size_t index = 0; index < count; ++index) {
    const auto start = index * maximum_chunk;
    const auto size = std::min(maximum_chunk, profile.size() - start);
    resources->marker = static_cast<std::uint8_t*>(std::malloc(size + 14));
    if (!resources->marker) jpeg_error_exit(reinterpret_cast<j_common_ptr>(compressor));
    std::memcpy(resources->marker, signature, 12);
    resources->marker[12] = static_cast<std::uint8_t>(index + 1);
    resources->marker[13] = static_cast<std::uint8_t>(count);
    std::memcpy(resources->marker + 14, profile.data() + start, size);
    jpeg_write_marker(compressor, JPEG_APP0 + 2, resources->marker,
                      static_cast<unsigned int>(size + 14));
    std::free(resources->marker);
    resources->marker = nullptr;
  }
}

template <image::ChannelType Channel>
void append_flattened(const image::ImageBuffer<Channel>& image, std::vector<std::uint8_t>& result) {
  constexpr auto maximum = static_cast<std::uint64_t>(std::numeric_limits<Channel>::max());
  constexpr auto denominator = maximum * maximum;
  result.reserve(image.width() * image.height() * 3);
  for (const auto& pixel : image.pixels()) {
    for (const auto channel : {pixel.r, pixel.g, pixel.b}) {
      const auto numerator = static_cast<std::uint64_t>(channel) * pixel.a * 255U;
      result.push_back(static_cast<std::uint8_t>((numerator + denominator / 2U) / denominator));
    }
  }
}

}  // namespace

std::vector<std::uint8_t> jpeg_rgb8_scratch(const image::AnyImage& image) {
  std::vector<std::uint8_t> result;
  std::visit([&](const auto& buffer) { append_flattened(buffer, result); }, image);
  return result;
}

DecodeResult JpegCodec::decode(std::span<const std::uint8_t> bytes) const {
  if (bytes.size() < 2 || bytes[0] != 0xFF || bytes[1] != 0xD8) {
    return {{}, {ErrorCode::decode_failed, "Input is not a JPEG."}};
  }
  JpegMetadata metadata;
  std::vector<std::uint8_t> profile;
  try {
    metadata = parse_metadata(bytes);
    profile = combine_icc(metadata);
  } catch (const std::bad_alloc&) {
    return {{}, {ErrorCode::allocation_failed, "JPEG metadata allocation failed."}};
  } catch (const std::length_error&) {
    return {{}, {ErrorCode::size_overflow, "JPEG metadata exceeds storage limits."}};
  }
  if (metadata.saw_icc && profile.empty()) {
    return {{}, {ErrorCode::color_transform_failed, "JPEG ICC marker sequence is incomplete."}};
  }
  if (bytes.size() > ULONG_MAX) {
    return {{}, {ErrorCode::size_overflow, "JPEG input exceeds codec limits."}};
  }
  const auto profile_space = color::inspect_profile(profile);
  if (profile_space == color::ProfileColorSpace::invalid ||
      profile_space == color::ProfileColorSpace::unsupported) {
    return {{}, {ErrorCode::color_transform_failed, "JPEG ICC profile is invalid or unsupported."}};
  }
  jpeg_decompress_struct decoder{};
  JpegErrorManager error{};
  decoder.err = jpeg_std_error(&error.base);
  error.base.error_exit = jpeg_error_exit;
  error.base.emit_message = jpeg_emit_message;
  auto* resources = static_cast<JpegDecodeResources*>(std::calloc(1, sizeof(JpegDecodeResources)));
  if (!resources)
    return {{}, {ErrorCode::allocation_failed, "JPEG decode allocation failed."}};
  if (setjmp(error.jump)) {
    std::free(resources->raw_pixels);
    std::free(resources->scanline);
    std::free(resources);
    jpeg_destroy_decompress(&decoder);
    return {{}, {ErrorCode::decode_failed, "JPEG is invalid or truncated."}};
  }
  jpeg_create_decompress(&decoder);
  jpeg_mem_src(&decoder, bytes.data(), static_cast<unsigned long>(bytes.size()));
  jpeg_read_header(&decoder, TRUE);
  decoder.out_color_space = profile_space == color::ProfileColorSpace::cmyk
                                ? JCS_CMYK
                            : profile_space == color::ProfileColorSpace::gray ? JCS_GRAYSCALE
                                                                              : JCS_RGB;
  jpeg_start_decompress(&decoder);
  const auto width = static_cast<std::size_t>(decoder.output_width);
  const auto height = static_cast<std::size_t>(decoder.output_height);
  const auto components = static_cast<std::size_t>(decoder.output_components);
  if (components == 0 || (width != 0 && height > static_cast<std::size_t>(-1) / width) ||
      width * height > static_cast<std::size_t>(-1) / components)
    error.base.error_exit(reinterpret_cast<j_common_ptr>(&decoder));
  resources->raw_pixels =
      static_cast<std::uint8_t*>(std::malloc(width * height * components));
  resources->scanline = static_cast<std::uint8_t*>(std::malloc(width * components));
  if (!resources->raw_pixels || !resources->scanline) {
    error.base.error_exit(reinterpret_cast<j_common_ptr>(&decoder));
  }
  while (decoder.output_scanline < decoder.output_height) {
    JSAMPROW row = resources->scanline;
    jpeg_read_scanlines(&decoder, &row, 1);
    const auto y = static_cast<std::size_t>(decoder.output_scanline - 1);
    std::memcpy(resources->raw_pixels + y * width * components, resources->scanline,
                width * components);
  }
  std::free(resources->scanline);
  resources->scanline = nullptr;
  jpeg_finish_decompress(&decoder);
  const bool adobe_cmyk = decoder.saw_Adobe_marker != 0 && components == 4;
  jpeg_destroy_decompress(&decoder);
  if (profile_space == color::ProfileColorSpace::cmyk) {
    if (adobe_cmyk) {
      for (std::size_t index = 0; index < width * height * 4; ++index)
        resources->raw_pixels[index] = static_cast<std::uint8_t>(255U - resources->raw_pixels[index]);
    }
    auto converted = color::convert_cmyk8_to_srgb(
        {resources->raw_pixels, width * height * 4}, width, height, profile);
    std::free(resources->raw_pixels);
    std::free(resources);
    if (converted.error) return {{}, converted.error};
    auto oriented = apply_orientation(*converted.image, metadata.orientation);
    if (oriented.error) return {{}, oriented.error};
    return {DecodedImage{image::AnyImage{std::move(*oriented.image)},
                         ColorProfile{color::srgb_profile_bytes(), true},
                         metadata.orientation},
            {}};
  }
  auto [buffer, allocation_error] = image::ImageBuffer<std::uint8_t>::create(width, height);
  if (allocation_error) {
    std::free(resources->raw_pixels);
    std::free(resources);
    return {{}, allocation_error};
  }
  for (std::size_t index = 0; index < width * height; ++index) {
    if (components == 1) {
      const auto gray = resources->raw_pixels[index];
      buffer->pixels()[index] = {gray, gray, gray, 255};
    } else {
      buffer->pixels()[index] = {resources->raw_pixels[index * components],
                                 resources->raw_pixels[index * components + 1],
                                 resources->raw_pixels[index * components + 2], 255};
    }
  }
  std::free(resources->raw_pixels);
  std::free(resources);
  auto oriented = apply_orientation(*buffer, metadata.orientation);
  if (oriented.error) return {{}, oriented.error};
  if (auto color_error = color::convert_to_srgb(*oriented.image, profile))
    return {{}, color_error};
  return {DecodedImage{image::AnyImage{std::move(*oriented.image)},
                       ColorProfile{color::srgb_profile_bytes(), !profile.empty()},
                       metadata.orientation},
          {}};
}

Error JpegCodec::encode(const image::AnyImage& image, const std::filesystem::path& destination,
                        const EncodeOptions& options) const {
  if (options.jpeg_quality < 1 || options.jpeg_quality > 100) {
    return {ErrorCode::invalid_settings, "JPEG quality must be in [1,100]."};
  }
  const auto width = std::visit([](const auto& buffer) { return buffer.width(); }, image);
  const auto height = std::visit([](const auto& buffer) { return buffer.height(); }, image);
  if (width > std::numeric_limits<JDIMENSION>::max() ||
      height > std::numeric_limits<JDIMENSION>::max()) {
    return {ErrorCode::encode_failed, "JPEG dimensions exceed codec limits."};
  }
  std::vector<std::uint8_t> scratch;
  std::vector<std::uint8_t> profile;
  try {
    scratch = jpeg_rgb8_scratch(image);
    profile = color::srgb_profile_bytes();
  } catch (const std::bad_alloc&) {
    return {ErrorCode::allocation_failed, "JPEG export scratch allocation failed."};
  } catch (const std::length_error&) {
    return {ErrorCode::size_overflow, "JPEG export scratch exceeds storage limits."};
  }
  FILE* file = open_file(destination, "wb");
  if (!file) return {ErrorCode::io_failed, "Could not open JPEG destination."};
  jpeg_compress_struct compressor{};
  JpegErrorManager error{};
  compressor.err = jpeg_std_error(&error.base);
  error.base.error_exit = jpeg_error_exit;
  error.base.emit_message = jpeg_emit_message;
  auto* resources = static_cast<JpegEncodeResources*>(std::calloc(1, sizeof(JpegEncodeResources)));
  if (!resources) {
    std::fclose(file);
    return {ErrorCode::allocation_failed, "JPEG encode allocation failed."};
  }
  if (setjmp(error.jump)) {
    std::free(resources->marker);
    std::free(resources);
    jpeg_destroy_compress(&compressor);
    std::fclose(file);
    return {ErrorCode::encode_failed, "JPEG encoding failed."};
  }
  jpeg_create_compress(&compressor);
  jpeg_stdio_dest(&compressor, file);
  compressor.image_width = static_cast<JDIMENSION>(width);
  compressor.image_height = static_cast<JDIMENSION>(height);
  compressor.input_components = 3;
  compressor.in_color_space = JCS_RGB;
  jpeg_set_defaults(&compressor);
  jpeg_set_quality(&compressor, options.jpeg_quality, TRUE);
  jpeg_start_compress(&compressor, TRUE);
  write_icc_markers(&compressor, profile, resources);
  while (compressor.next_scanline < compressor.image_height) {
    JSAMPROW row = scratch.data() + static_cast<std::size_t>(compressor.next_scanline) * width * 3U;
    jpeg_write_scanlines(&compressor, &row, 1);
  }
  jpeg_finish_compress(&compressor);
  jpeg_destroy_compress(&compressor);
  std::free(resources);
  const auto flush_result = std::fflush(file);
  const auto close_result = std::fclose(file);
  if (flush_result != 0 || close_result != 0) {
    return {ErrorCode::io_failed, "Could not flush JPEG output."};
  }
  return {};
}

}  // namespace chromasunder::codec
