#include "chromasunder/codec/image_codec.hpp"

#include "chromasunder/codec/orientation.hpp"
#include "chromasunder/color/color_management.hpp"
#include "chromasunder/image/image_buffer.hpp"

#include <png.h>

#include <bit>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <span>
#include <new>
#include <stdexcept>
#include <utility>
#include <vector>

namespace chromasunder::codec {
namespace {

struct MemoryReader {
  const std::uint8_t* data;
  std::size_t size;
  std::size_t offset;
};

struct PngDecodeResources {
  void* raw_pixels;
  png_bytep* rows;
  std::uint8_t* profile;
  std::uint8_t* exif;
};

void free_resources(PngDecodeResources* resources) {
  if (!resources) return;
  std::free(resources->raw_pixels);
  std::free(resources->rows);
  std::free(resources->profile);
  std::free(resources->exif);
  std::free(resources);
}

void read_memory(png_structp png, png_bytep destination, png_size_t count) {
  auto* reader = static_cast<MemoryReader*>(png_get_io_ptr(png));
  if (!reader || count > reader->size - reader->offset) png_error(png, "truncated PNG");
  std::memcpy(destination, reader->data + reader->offset, count);
  reader->offset += count;
}

FILE* open_file(const std::filesystem::path& path, const char* mode) {
#ifdef _WIN32
  const auto wide_mode = mode[0] == 'w' ? L"wb" : L"rb";
  return _wfopen(path.c_str(), wide_mode);
#else
  return std::fopen(path.c_str(), mode);
#endif
}

template <image::ChannelType Channel>
DecodeResult finish_decode(void* raw_pixels, std::size_t width, std::size_t height,
                           std::uint16_t orientation, std::vector<std::uint8_t> profile,
                           bool tagged) {
  auto [buffer, error] = image::ImageBuffer<Channel>::create(width, height);
  if (error) return {{}, std::move(error)};
  std::memcpy(buffer->pixels().data(), raw_pixels, buffer->size_bytes());
  auto oriented = apply_orientation(*buffer, orientation);
  if (oriented.error) return {{}, oriented.error};
  if (auto color_error = color::convert_to_srgb(*oriented.image, profile))
    return {{}, color_error};
  ColorProfile working{color::srgb_profile_bytes(), tagged};
  return {DecodedImage{image::AnyImage{std::move(*oriented.image)}, std::move(working), orientation},
          {}};
}

template <image::ChannelType Channel>
Error encode_png_buffer(const image::ImageBuffer<Channel>& image,
                        const std::filesystem::path& destination) {
  if (image.width() > PNG_UINT_32_MAX || image.height() > PNG_UINT_32_MAX) {
    return {ErrorCode::encode_failed, "PNG dimensions exceed codec limits."};
  }
  std::vector<png_bytep> rows;
  try {
    rows.resize(image.height());
  } catch (const std::bad_alloc&) {
    return {ErrorCode::allocation_failed, "PNG row allocation failed."};
  } catch (const std::length_error&) {
    return {ErrorCode::size_overflow, "PNG row count exceeds storage limits."};
  }
  for (std::size_t y = 0; y < image.height(); ++y) {
    rows[y] = reinterpret_cast<png_bytep>(
        const_cast<image::RgbaPixel<Channel>*>(image.view().row(y).data()));
  }
  FILE* file = open_file(destination, "wb");
  if (!file) return {ErrorCode::io_failed, "Could not open PNG destination."};
  png_structp png = png_create_write_struct(PNG_LIBPNG_VER_STRING, nullptr, nullptr, nullptr);
  png_infop info = png ? png_create_info_struct(png) : nullptr;
  if (!png || !info) {
    if (png) png_destroy_write_struct(&png, nullptr);
    std::fclose(file);
    return {ErrorCode::encode_failed, "Could not initialize PNG encoder."};
  }
  if (setjmp(png_jmpbuf(png))) {
    png_destroy_write_struct(&png, &info);
    std::fclose(file);
    return {ErrorCode::encode_failed, "PNG encoding failed."};
  }
  png_init_io(png, file);
  png_set_IHDR(png, info, static_cast<png_uint_32>(image.width()),
               static_cast<png_uint_32>(image.height()), sizeof(Channel) == 1 ? 8 : 16,
               PNG_COLOR_TYPE_RGBA, PNG_INTERLACE_NONE, PNG_COMPRESSION_TYPE_DEFAULT,
               PNG_FILTER_TYPE_DEFAULT);
  png_set_sRGB_gAMA_and_cHRM(png, info, PNG_sRGB_INTENT_RELATIVE);
  png_set_rows(png, info, rows.data());
  constexpr int transform = sizeof(Channel) == 2 && std::endian::native == std::endian::little
                                ? PNG_TRANSFORM_SWAP_ENDIAN
                                : PNG_TRANSFORM_IDENTITY;
  png_write_png(png, info, transform, nullptr);
  png_destroy_write_struct(&png, &info);
  const auto flush_result = std::fflush(file);
  const auto close_result = std::fclose(file);
  if (flush_result != 0 || close_result != 0) {
    return {ErrorCode::io_failed, "Could not flush PNG output."};
  }
  return {};
}

}  // namespace

DecodeResult PngCodec::decode(std::span<const std::uint8_t> bytes) const {
  if (bytes.size() < 8 || png_sig_cmp(bytes.data(), 0, 8) != 0) {
    return {{}, {ErrorCode::decode_failed, "Input is not a valid PNG signature."}};
  }
  png_structp png = png_create_read_struct(PNG_LIBPNG_VER_STRING, nullptr, nullptr, nullptr);
  png_infop info = png ? png_create_info_struct(png) : nullptr;
  if (!png || !info) {
    if (png) png_destroy_read_struct(&png, nullptr, nullptr);
    return {{}, {ErrorCode::decode_failed, "Could not initialize PNG decoder."}};
  }
  MemoryReader reader{bytes.data(), bytes.size(), 0};
  auto* resources = static_cast<PngDecodeResources*>(std::calloc(1, sizeof(PngDecodeResources)));
  if (!resources) {
    png_destroy_read_struct(&png, &info, nullptr);
    return {{}, {ErrorCode::allocation_failed, "PNG decode allocation failed."}};
  }
  std::size_t profile_size = 0;
  std::size_t exif_size = 0;
  png_uint_32 width = 0;
  png_uint_32 height = 0;
  int bit_depth = 0;
  if (setjmp(png_jmpbuf(png))) {
    png_destroy_read_struct(&png, &info, nullptr);
    free_resources(resources);
    return {{}, {ErrorCode::decode_failed, "PNG is invalid or truncated."}};
  }
  png_set_read_fn(png, &reader, read_memory);
  png_read_info(png, info);
  int color_type = 0;
  int interlace = 0;
  int compression = 0;
  int filter = 0;
  png_get_IHDR(png, info, &width, &height, &bit_depth, &color_type, &interlace,
               &compression, &filter);
  if (bit_depth != 8 && bit_depth != 16) png_error(png, "unsupported PNG depth");
  png_charp profile_name = nullptr;
  int profile_compression = 0;
  png_bytep profile_data = nullptr;
  png_uint_32 profile_length = 0;
  if (png_get_iCCP(png, info, &profile_name, &profile_compression, &profile_data,
                   &profile_length) != 0 &&
      profile_length != 0) {
    profile_size = profile_length;
    resources->profile = static_cast<std::uint8_t*>(std::malloc(profile_size));
    if (!resources->profile) png_error(png, "profile allocation failed");
    std::memcpy(resources->profile, profile_data, profile_size);
  }
#ifdef PNG_eXIf_SUPPORTED
  png_bytep exif_data = nullptr;
  png_uint_32 exif_length = 0;
  if (png_get_eXIf_1(png, info, &exif_length, &exif_data) != 0 && exif_length != 0) {
    exif_size = exif_length;
    resources->exif = static_cast<std::uint8_t*>(std::malloc(exif_size));
    if (!resources->exif) png_error(png, "EXIF allocation failed");
    std::memcpy(resources->exif, exif_data, exif_size);
  }
#endif
  if (color_type == PNG_COLOR_TYPE_PALETTE) png_set_palette_to_rgb(png);
  if (color_type == PNG_COLOR_TYPE_GRAY && bit_depth < 8) png_set_expand_gray_1_2_4_to_8(png);
  if (png_get_valid(png, info, PNG_INFO_tRNS) != 0) png_set_tRNS_to_alpha(png);
  if (color_type == PNG_COLOR_TYPE_GRAY || color_type == PNG_COLOR_TYPE_GRAY_ALPHA)
    png_set_gray_to_rgb(png);
  if ((color_type & PNG_COLOR_MASK_ALPHA) == 0 &&
      png_get_valid(png, info, PNG_INFO_tRNS) == 0)
    png_set_add_alpha(png, bit_depth == 16 ? 65535U : 255U, PNG_FILLER_AFTER);
  if (bit_depth == 16) {
    if constexpr (std::endian::native == std::endian::little) png_set_swap(png);
  }
  png_read_update_info(png, info);
  const auto row_bytes = png_get_rowbytes(png, info);
  const auto expected_row_bytes = static_cast<std::size_t>(width) *
                                  (bit_depth == 8 ? sizeof(image::RgbaPixel<std::uint8_t>)
                                                  : sizeof(image::RgbaPixel<std::uint16_t>));
  if (row_bytes != expected_row_bytes) png_error(png, "unexpected canonical PNG row size");
  if (height != 0 && row_bytes > static_cast<std::size_t>(-1) / height)
    png_error(png, "PNG size overflow");
  resources->raw_pixels = std::malloc(row_bytes * height);
  resources->rows = static_cast<png_bytep*>(std::malloc(sizeof(png_bytep) * height));
  if (!resources->raw_pixels || !resources->rows) png_error(png, "pixel allocation failed");
  for (png_uint_32 y = 0; y < height; ++y)
    resources->rows[y] = static_cast<png_bytep>(resources->raw_pixels) + y * row_bytes;
  png_read_image(png, resources->rows);
  png_read_end(png, info);
  png_destroy_read_struct(&png, &info, nullptr);

  std::vector<std::uint8_t> profile;
  try {
    if (profile_size != 0)
      profile.assign(resources->profile, resources->profile + profile_size);
  } catch (const std::bad_alloc&) {
    free_resources(resources);
    return {{}, {ErrorCode::allocation_failed, "PNG profile allocation failed."}};
  } catch (const std::length_error&) {
    free_resources(resources);
    return {{}, {ErrorCode::size_overflow, "PNG profile exceeds storage limits."}};
  }
  const auto orientation = parse_exif_orientation({resources->exif, exif_size});
  std::free(resources->profile);
  resources->profile = nullptr;
  std::free(resources->exif);
  resources->exif = nullptr;
  std::free(resources->rows);
  resources->rows = nullptr;
  DecodeResult result = bit_depth == 8
                            ? finish_decode<std::uint8_t>(resources->raw_pixels, width, height, orientation,
                                                          std::move(profile), profile_size != 0)
                            : finish_decode<std::uint16_t>(resources->raw_pixels, width, height, orientation,
                                                           std::move(profile), profile_size != 0);
  free_resources(resources);
  return result;
}

Error PngCodec::encode(const image::AnyImage& image, const std::filesystem::path& destination,
                       const EncodeOptions&) const {
  return std::visit([&](const auto& buffer) { return encode_png_buffer(buffer, destination); },
                    image);
}

}  // namespace chromasunder::codec
