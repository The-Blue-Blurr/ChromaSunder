#include "chromasunder/image/image_buffer.hpp"
#include "chromasunder/jobs/cancellation.hpp"
#include "chromasunder/jobs/progress.hpp"
#include "chromasunder/processing/mask.hpp"
#include "chromasunder/processing/path.hpp"
#include "chromasunder/processing/render_backend.hpp"
#include "chromasunder/processing/settings.hpp"

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <optional>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <variant>
#include <vector>

#ifndef _WIN32
#include <sys/resource.h>
#endif

namespace {

using Clock = std::chrono::steady_clock;
using chromasunder::image::AnyImage;
using chromasunder::image::ImageBuffer;
using chromasunder::image::RgbaPixel;
using chromasunder::processing::BinaryImage;
using chromasunder::processing::CpuRenderBackend;
using chromasunder::processing::IntervalMode;
using chromasunder::processing::PixelSortSettings;
using chromasunder::processing::RenderRequest;
using chromasunder::processing::SortingMode;

struct BenchmarkCase {
  std::string name;
  std::size_t width;
  std::size_t height;
  bool u16;
  SortingMode sorting;
  IntervalMode interval;
  double angle;
  bool mask;
  bool interval_image;
};

double milliseconds(Clock::time_point start, Clock::time_point end) {
  return std::chrono::duration<double, std::milli>(end - start).count();
}

std::size_t peak_resident_bytes() {
#ifdef _WIN32
  return 0;
#elif defined(__linux__)
  std::ifstream status("/proc/self/status");
  std::string key;
  while (status >> key) {
    if (key == "VmHWM:") {
      std::size_t kibibytes = 0;
      status >> kibibytes;
      return kibibytes * 1024U;
    }
    std::string ignored;
    std::getline(status, ignored);
  }
  return 0;
#else
  rusage usage{};
  return getrusage(RUSAGE_SELF, &usage) == 0
             ? static_cast<std::size_t>(usage.ru_maxrss) * 1024U
             : 0;
#endif
}

template <typename Channel>
ImageBuffer<Channel> make_source(std::size_t width, std::size_t height) {
  auto [image, error] = ImageBuffer<Channel>::create(width, height);
  if (error) throw std::runtime_error(error.message);
  constexpr auto maximum = static_cast<std::uint64_t>(std::numeric_limits<Channel>::max());
  for (std::size_t index = 0; index < image->pixels().size(); ++index) {
    image->pixels()[index] = {
        static_cast<Channel>((index * 7919U + 17U) % (maximum + 1U)),
        static_cast<Channel>((index * 3571U + 101U) % (maximum + 1U)),
        static_cast<Channel>((index * 1237U + 509U) % (maximum + 1U)),
        static_cast<Channel>((index * 1879U + 3U) % (maximum + 1U))};
  }
  return std::move(*image);
}

struct Measurement {
  double prepare_ms{};
  double path_ms{};
  double sort_ms{};
  double total_ms{};
  std::size_t peak_rss{};
  std::size_t estimate{};
  std::uint64_t hash{};
};

std::uint64_t hash_image(const AnyImage& image) {
  std::uint64_t hash = 1469598103934665603ULL;
  std::visit(
      [&](const auto& buffer) {
        for (const auto& pixel : buffer.pixels()) {
          for (const auto channel : {pixel.r, pixel.g, pixel.b, pixel.a}) {
            for (std::size_t byte = 0; byte < sizeof(channel); ++byte) {
              hash ^= static_cast<std::uint8_t>(
                  static_cast<std::uint64_t>(channel) >> (byte * 8U));
              hash *= 1099511628211ULL;
            }
          }
        }
      },
      image);
  return hash;
}

Measurement run_case(const BenchmarkCase& item, std::size_t workers) {
  const auto total_start = Clock::now();
  AnyImage source = item.u16 ? AnyImage{make_source<std::uint16_t>(item.width, item.height)}
                             : AnyImage{make_source<std::uint8_t>(item.width, item.height)};
  std::optional<BinaryImage> mask;
  std::optional<BinaryImage> intervals;
  if (item.mask || item.interval_image) {
    std::vector<std::uint8_t> bits(item.width * item.height);
    for (std::size_t index = 0; index < bits.size(); ++index)
      bits[index] = ((index * 17U + index / item.width) % 5U) != 0 ? 1 : 0;
    if (item.mask) mask.emplace(item.width, item.height, bits);
    if (item.interval_image) intervals.emplace(item.width, item.height, std::move(bits));
  }
  const auto prepared = Clock::now();
  chromasunder::processing::StraightDirectionalPathProvider provider(item.width, item.height,
                                                                      item.angle);
  const auto paths_ready = Clock::now();
  PixelSortSettings settings;
  settings.sorting_mode = item.sorting;
  settings.interval_mode = item.interval;
  settings.lower_threshold = 0.21;
  settings.upper_threshold = 0.8;
  settings.characteristic_length = 43;
  settings.angle_degrees = item.angle;
  settings.randomness_percentage = item.interval == IntervalMode::none ? 0 : 15;
  settings.seed = 0xC07A5A7D3E2B1901ULL;
  CpuRenderBackend backend(workers);
  chromasunder::jobs::CancellationToken cancellation;
  chromasunder::jobs::ProgressState progress;
  auto outcome = backend.render(RenderRequest{source, settings, mask ? &*mask : nullptr,
                                               intervals ? &*intervals : nullptr},
                                cancellation, progress);
  const auto sorted = Clock::now();
  if (!outcome.succeeded()) throw std::runtime_error(outcome.error.message);
  return {milliseconds(total_start, prepared), milliseconds(prepared, paths_ready),
          milliseconds(paths_ready, sorted), milliseconds(total_start, sorted),
          peak_resident_bytes(), outcome.memory_estimate.total_bytes, hash_image(*outcome.image)};
}

std::string sorting_name(SortingMode mode) {
  switch (mode) {
    case SortingMode::lightness: return "lightness";
    case SortingMode::hue: return "hue";
    case SortingMode::saturation: return "saturation";
    case SortingMode::intensity: return "intensity";
    case SortingMode::minimum: return "minimum";
  }
  return "unknown";
}

std::string interval_name(IntervalMode mode) {
  switch (mode) {
    case IntervalMode::threshold: return "threshold";
    case IntervalMode::edges: return "edges";
    case IntervalMode::random: return "random";
    case IntervalMode::waves: return "waves";
    case IntervalMode::file: return "file";
    case IntervalMode::file_edges: return "file-edges";
    case IntervalMode::none: return "none";
  }
  return "unknown";
}

}  // namespace

int main(int argc, char** argv) {
  std::filesystem::path output;
  bool quick = false;
  for (int index = 1; index < argc; ++index) {
    const std::string_view argument(argv[index]);
    if (argument == "--quick") quick = true;
    if (argument == "--output" && index + 1 < argc) output = argv[++index];
  }
  const auto large_width = quick ? 600U : 6000U;
  const auto large_height = quick ? 400U : 4000U;
  const auto hd_width = quick ? 320U : 1920U;
  const auto hd_height = quick ? 180U : 1080U;
  const std::vector<BenchmarkCase> cases{
      {"hd-u8-lightness-none-0", hd_width, hd_height, false, SortingMode::lightness,
       IntervalMode::none, 0, false, false},
      {"hd-u8-hue-random-45", hd_width, hd_height, false, SortingMode::hue,
       IntervalMode::random, 45, false, false},
      {"hd-u8-saturation-waves-90", hd_width, hd_height, false, SortingMode::saturation,
       IntervalMode::waves, 90, false, false},
      {"hd-u8-mask-heavy", hd_width, hd_height, false, SortingMode::intensity,
       IntervalMode::none, 0, true, false},
      {"hd-u8-interval-heavy", hd_width, hd_height, false, SortingMode::minimum,
       IntervalMode::file_edges, 45, false, true},
      {"large-u8-lightness-0", large_width, large_height, false, SortingMode::lightness,
       IntervalMode::none, 0, false, false},
      {"large-u16-hue-45", large_width, large_height, true, SortingMode::hue,
       IntervalMode::random, 45, false, false},
  };
  const auto workers = chromasunder::jobs::ThreadPool::automatic_worker_count();
  std::ostream* destination = &std::cout;
  std::ofstream file;
  if (!output.empty()) {
    file.open(output);
    if (!file) {
      std::cerr << "could not open benchmark output\n";
      return 1;
    }
    destination = &file;
  }
  auto& json = *destination;
  json << "{\n  \"schema_version\": 1,\n  \"quick\": " << (quick ? "true" : "false")
       << ",\n  \"worker_count\": " << workers << ",\n  \"cases\": [\n";
  for (std::size_t index = 0; index < cases.size(); ++index) {
    const auto& item = cases[index];
    const auto measured = run_case(item, workers);
    json << "    {\"name\": \"" << item.name << "\", \"width\": " << item.width
         << ", \"height\": " << item.height << ", \"format\": \""
         << (item.u16 ? "RGBA16" : "RGBA8") << "\", \"sorting\": \""
         << sorting_name(item.sorting) << "\", \"interval\": \""
         << interval_name(item.interval) << "\", \"angle_degrees\": " << item.angle
         << ", \"decode_ms\": null, \"color_transform_ms\": null, \"prepare_ms\": "
         << std::fixed << std::setprecision(3) << measured.prepare_ms
         << ", \"path_generation_ms\": " << measured.path_ms
         << ", \"sorting_core_ms\": " << measured.sort_ms
         << ", \"encode_ms\": null, \"total_ms\": " << measured.total_ms
         << ", \"estimated_peak_bytes\": " << measured.estimate
         << ", \"process_peak_rss_bytes\": " << measured.peak_rss
         << ", \"fnv1a64\": \"" << std::hex << measured.hash << std::dec << "\"}"
         << (index + 1 == cases.size() ? "\n" : ",\n");
  }
  json << "  ]\n}\n";
  return 0;
}
