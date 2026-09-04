#include "chromasunder/image/image_buffer.hpp"
#include "chromasunder/jobs/cancellation.hpp"
#include "chromasunder/jobs/progress.hpp"
#include "chromasunder/processing/render_backend.hpp"
#include "chromasunder/processing/settings.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <span>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

namespace {

using chromasunder::image::AnyImage;
using chromasunder::image::ImageBuffer;
using chromasunder::image::RgbaPixel;
using chromasunder::processing::BinaryImage;
using chromasunder::processing::CpuRenderBackend;
using chromasunder::processing::IntervalMode;
using chromasunder::processing::PixelSortSettings;
using chromasunder::processing::RenderRequest;
using chromasunder::processing::SortingMode;

std::uint32_t read_u32(std::span<const std::uint8_t> bytes, std::size_t& offset) {
  if (offset + 4 > bytes.size()) return 0;
  const auto value = static_cast<std::uint32_t>(bytes[offset]) |
                     (static_cast<std::uint32_t>(bytes[offset + 1]) << 8U) |
                     (static_cast<std::uint32_t>(bytes[offset + 2]) << 16U) |
                     (static_cast<std::uint32_t>(bytes[offset + 3]) << 24U);
  offset += 4;
  return value;
}

}  // namespace

int main() {
  const auto path = std::filesystem::path(CHROMASUNDER_TESTDATA_DIR) / "golden-v1" /
                    "native-cardinal-parity.bin";
  std::ifstream stream(path, std::ios::binary);
  const std::vector<std::uint8_t> bytes{std::istreambuf_iterator<char>(stream),
                                        std::istreambuf_iterator<char>()};
  if (bytes.size() < 20 || std::string_view(reinterpret_cast<const char*>(bytes.data()), 8) !=
                               std::string_view("CSPAR2\0\0", 8)) {
    std::cerr << "invalid parity pack: " << path << '\n';
    return 1;
  }
  std::size_t offset = 8;
  const auto width = read_u32(bytes, offset);
  const auto height = read_u32(bytes, offset);
  const auto case_count = read_u32(bytes, offset);
  const auto pixel_count = static_cast<std::size_t>(width) * height;
  const auto rgba_bytes = pixel_count * 4;
  const auto required = offset + rgba_bytes + pixel_count * 5 +
                        static_cast<std::size_t>(case_count) * (4 + rgba_bytes);
  if (bytes.size() != required || case_count != 400) {
    std::cerr << "parity pack has unexpected size or case count\n";
    return 1;
  }
  auto [source, source_error] = ImageBuffer<std::uint8_t>::create(width, height);
  if (source_error) return 1;
  for (std::size_t index = 0; index < pixel_count; ++index) {
    source->pixels()[index] = {bytes[offset + index * 4], bytes[offset + index * 4 + 1],
                               bytes[offset + index * 4 + 2], bytes[offset + index * 4 + 3]};
  }
  offset += rgba_bytes;
  std::array<BinaryImage, 4> masks;
  for (std::size_t index = 1; index < masks.size(); ++index) {
    masks[index] = BinaryImage(width, height,
                               {bytes.begin() + static_cast<std::ptrdiff_t>(offset),
                                bytes.begin() + static_cast<std::ptrdiff_t>(offset + pixel_count)});
    offset += pixel_count;
  }
  std::array<BinaryImage, 2> intervals;
  for (auto& interval : intervals) {
    interval = BinaryImage(width, height,
                           {bytes.begin() + static_cast<std::ptrdiff_t>(offset),
                            bytes.begin() + static_cast<std::ptrdiff_t>(offset + pixel_count)});
    offset += pixel_count;
  }

  const std::array<SortingMode, 5> sorting_modes{
      SortingMode::lightness, SortingMode::hue, SortingMode::saturation,
      SortingMode::intensity, SortingMode::minimum};
  const std::array<IntervalMode, 5> interval_modes{
      IntervalMode::none, IntervalMode::threshold, IntervalMode::edges,
      IntervalMode::file, IntervalMode::file_edges};
  const std::array<double, 4> angles{0, 90, 180, 270};
  AnyImage any_source{*source};
  CpuRenderBackend backend(4);
  std::size_t passed = 0;
  for (std::size_t case_index = 0; case_index < case_count; ++case_index) {
    const auto sorting_index = bytes[offset++];
    const auto interval_index = bytes[offset++];
    const auto angle_index = bytes[offset++];
    const auto mask_index = bytes[offset++];
    PixelSortSettings settings;
    settings.sorting_mode = sorting_modes.at(sorting_index);
    settings.interval_mode = interval_modes.at(interval_index);
    settings.lower_threshold = 0.21;
    settings.upper_threshold = 0.8;
    settings.characteristic_length = 3;
    settings.angle_degrees = angles.at(angle_index);
    settings.randomness_percentage = 0;
    settings.seed = 8675309;
    const BinaryImage* interval = interval_index == 3 ? &intervals[0]
                                  : interval_index == 4 ? &intervals[1]
                                                        : nullptr;
    chromasunder::jobs::CancellationToken cancellation;
    chromasunder::jobs::ProgressState progress;
    auto outcome = backend.render(
        RenderRequest{any_source, settings, mask_index == 0 ? nullptr : &masks[mask_index],
                      interval},
        cancellation, progress);
    if (!outcome.succeeded()) {
      std::cerr << "parity render failed at case " << case_index << ": "
                << outcome.error.message << '\n';
      return 1;
    }
    const auto actual = std::get<ImageBuffer<std::uint8_t>>(*outcome.image).pixels();
    bool equal = true;
    for (std::size_t pixel = 0; pixel < pixel_count; ++pixel) {
      const RgbaPixel<std::uint8_t> expected{
          bytes[offset + pixel * 4], bytes[offset + pixel * 4 + 1],
          bytes[offset + pixel * 4 + 2], bytes[offset + pixel * 4 + 3]};
      if (actual[pixel] != expected) {
        std::cerr << " first_pixel=" << pixel << " actual=" << static_cast<int>(actual[pixel].r)
                  << ',' << static_cast<int>(actual[pixel].g) << ','
                  << static_cast<int>(actual[pixel].b) << ','
                  << static_cast<int>(actual[pixel].a) << " expected="
                  << static_cast<int>(expected.r) << ',' << static_cast<int>(expected.g) << ','
                  << static_cast<int>(expected.b) << ',' << static_cast<int>(expected.a) << '\n';
        equal = false;
        break;
      }
    }
    if (!equal) {
      std::cerr << "V1 parity mismatch at case " << case_index << " sorting="
                << static_cast<int>(sorting_index) << " interval="
                << static_cast<int>(interval_index) << " angle="
                << static_cast<int>(angle_index) << " mask=" << static_cast<int>(mask_index)
                << '\n';
      return 1;
    }
    offset += rgba_bytes;
    ++passed;
  }
  std::cout << "v1_cardinal_parity_passed=" << passed << '/' << case_count << '\n';
  return passed == case_count ? 0 : 1;
}
