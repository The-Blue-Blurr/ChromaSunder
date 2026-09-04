#include "chromasunder/codec/image_io.hpp"

#include "chromasunder/image/image_buffer.hpp"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <limits>
#include <new>
#include <stdexcept>
#include <system_error>
#include <type_traits>
#include <utility>
#include <variant>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace chromasunder::codec {
namespace {

std::atomic_uint64_t temporary_sequence{0};

std::pair<std::vector<std::uint8_t>, Error> read_bytes(const std::filesystem::path& path) {
  std::ifstream stream(path, std::ios::binary);
  if (!stream) return {{}, {ErrorCode::io_failed, "Could not open image file."}};
  stream.seekg(0, std::ios::end);
  const auto end = stream.tellg();
  if (end < 0) return {{}, {ErrorCode::io_failed, "Could not determine image size."}};
  stream.seekg(0, std::ios::beg);
  const auto length = static_cast<std::uintmax_t>(static_cast<std::streamoff>(end));
  if (length > static_cast<std::uintmax_t>(std::vector<std::uint8_t>{}.max_size())) {
    return {{}, {ErrorCode::size_overflow, "Image file exceeds storage limits."}};
  }
  std::vector<std::uint8_t> bytes;
  try {
    bytes.resize(static_cast<std::size_t>(length));
  } catch (const std::bad_alloc&) {
    return {{}, {ErrorCode::allocation_failed, "Image file allocation failed."}};
  } catch (const std::length_error&) {
    return {{}, {ErrorCode::size_overflow, "Image file exceeds storage limits."}};
  }
  if (!bytes.empty() && !stream.read(reinterpret_cast<char*>(bytes.data()), end)) {
    return {{}, {ErrorCode::io_failed, "Could not read complete image file."}};
  }
  return {std::move(bytes), {}};
}

Error replace_file(const std::filesystem::path& temporary,
                   const std::filesystem::path& destination) {
#ifdef _WIN32
  if (!MoveFileExW(temporary.c_str(), destination.c_str(),
                   MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
    return {ErrorCode::io_failed, "Could not atomically replace output file."};
  }
#else
  std::error_code error;
  std::filesystem::rename(temporary, destination, error);
  if (error) return {ErrorCode::io_failed, "Could not atomically replace output file."};
#endif
  return {};
}

}  // namespace

DecodeResult decode_image_file(const std::filesystem::path& path) {
  auto [bytes, read_error] = read_bytes(path);
  if (read_error) return {{}, read_error};
  if (bytes.size() >= 8 && bytes[0] == 0x89 && bytes[1] == 'P' && bytes[2] == 'N' &&
      bytes[3] == 'G') {
    return PngCodec{}.decode(bytes);
  }
  if (bytes.size() >= 2 && bytes[0] == 0xFF && bytes[1] == 0xD8) {
    return JpegCodec{}.decode(bytes);
  }
  return {{}, {ErrorCode::unsupported_format, "Only PNG and JPEG are supported."}};
}

Error encode_image_atomic(const image::AnyImage& image,
                          const std::filesystem::path& destination, ImageFileFormat format,
                          const EncodeOptions& options) {
  auto temporary = destination;
  const auto sequence = temporary_sequence.fetch_add(1, std::memory_order_relaxed);
#ifdef _WIN32
  const auto process = static_cast<std::uint64_t>(GetCurrentProcessId());
#else
  const auto process = static_cast<std::uint64_t>(getpid());
#endif
  temporary += ".tmp-" + std::to_string(process) + "-" + std::to_string(sequence);
  const auto encode_error = format == ImageFileFormat::png
                                ? PngCodec{}.encode(image, temporary, options)
                                : JpegCodec{}.encode(image, temporary, options);
  if (encode_error) {
    std::error_code ignored;
    std::filesystem::remove(temporary, ignored);
    return encode_error;
  }
  if (auto replace_error = replace_file(temporary, destination)) {
    std::error_code ignored;
    std::filesystem::remove(temporary, ignored);
    return replace_error;
  }
  return {};
}

AuxiliaryResult load_auxiliary_image(const std::filesystem::path& path,
                                     std::size_t canonical_width,
                                     std::size_t canonical_height) {
  auto decoded = decode_image_file(path);
  if (decoded.error) return {{}, decoded.error};
  return std::visit(
      [&](const auto& buffer) -> AuxiliaryResult {
        if (buffer.width() != canonical_width || buffer.height() != canonical_height) {
          return {{}, {ErrorCode::dimension_mismatch,
                       "Auxiliary image dimensions must exactly match the canonical source."}};
        }
        using Channel = std::remove_cvref_t<decltype(buffer.pixels().front().r)>;
        constexpr auto maximum = static_cast<std::uint64_t>(std::numeric_limits<Channel>::max());
        constexpr auto threshold = (maximum + 1U) / 2U;
        std::vector<std::uint8_t> bits;
        bits.reserve(buffer.pixels().size());
        for (const auto& pixel : buffer.pixels()) {
          const auto grayscale =
              (299U * static_cast<std::uint64_t>(pixel.r) +
               587U * static_cast<std::uint64_t>(pixel.g) +
               114U * static_cast<std::uint64_t>(pixel.b) + 500U) /
              1000U;
          bits.push_back(grayscale >= threshold ? 1 : 0);
        }
        return {processing::BinaryImage(buffer.width(), buffer.height(), std::move(bits)), {}};
      },
      decoded.image->pixels);
}

}  // namespace chromasunder::codec
