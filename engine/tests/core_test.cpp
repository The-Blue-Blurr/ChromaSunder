#include "chromasunder/image/image_buffer.hpp"
#include "chromasunder/jobs/cancellation.hpp"
#include "chromasunder/jobs/progress.hpp"
#include "chromasunder/memory/render_budget.hpp"
#include "chromasunder/processing/intervals.hpp"
#include "chromasunder/processing/path.hpp"
#include "chromasunder/processing/render_backend.hpp"
#include "chromasunder/processing/rng.hpp"
#include "chromasunder/processing/settings.hpp"
#include "chromasunder/processing/sorting.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <limits>
#include <numbers>
#include <optional>
#include <set>
#include <span>
#include <string_view>
#include <chrono>
#include <thread>
#include <tuple>
#include <utility>
#include <variant>
#include <vector>

namespace {

using chromasunder::ErrorCode;
using chromasunder::image::ImageBuffer;
using chromasunder::image::RgbaPixel;
using chromasunder::processing::AnyImage;
using chromasunder::processing::BinaryImage;
using chromasunder::processing::CpuRenderBackend;
using chromasunder::processing::FullRenderStore;
using chromasunder::processing::Interval;
using chromasunder::processing::IntervalMode;
using chromasunder::processing::PixelSortSettings;
using chromasunder::processing::RenderRequest;
using chromasunder::processing::SortingMode;
using chromasunder::processing::SplitMix64;
using chromasunder::processing::StraightDirectionalPathProvider;

int failures = 0;

void expect(bool condition, std::string_view message) {
  if (!condition) {
    std::cerr << "FAIL: " << message << '\n';
    ++failures;
  }
}

template <typename T>
ImageBuffer<T> make_image(std::size_t width, std::size_t height,
                          std::vector<RgbaPixel<T>> pixels) {
  auto [image, error] = ImageBuffer<T>::create(width, height);
  expect(!error, "image allocation succeeds");
  std::copy(pixels.begin(), pixels.end(), image->pixels().begin());
  return std::move(*image);
}

template <typename T>
std::uint64_t image_hash(const ImageBuffer<T>& image) {
  std::uint64_t hash = 1469598103934665603ULL;
  for (const auto& pixel : image.pixels()) {
    for (const auto channel : {pixel.r, pixel.g, pixel.b, pixel.a}) {
      for (std::size_t byte = 0; byte < sizeof(T); ++byte) {
        hash ^= static_cast<std::uint8_t>(static_cast<std::uint64_t>(channel) >> (byte * 8U));
        hash *= 1099511628211ULL;
      }
    }
  }
  return hash;
}

template <typename T>
std::vector<RgbaPixel<T>> representative_pixels(std::size_t width, std::size_t height) {
  std::vector<RgbaPixel<T>> result;
  result.reserve(width * height);
  constexpr auto maximum = std::numeric_limits<T>::max();
  for (std::size_t index = 0; index < width * height; ++index) {
    const auto scale = static_cast<std::uint64_t>(maximum);
    result.push_back({static_cast<T>((index * 7919U + 17U) % (scale + 1U)),
                      static_cast<T>((index * 3571U + 101U) % (scale + 1U)),
                      static_cast<T>((index * 1237U + 509U) % (scale + 1U)),
                      static_cast<T>((index * 1879U + 3U) % (scale + 1U))});
  }
  return result;
}

template <typename T>
ImageBuffer<T> render(const ImageBuffer<T>& source, PixelSortSettings settings,
                      std::size_t workers, const BinaryImage* mask = nullptr,
                      const BinaryImage* interval_image = nullptr) {
  AnyImage any_source = source;
  CpuRenderBackend backend(workers);
  chromasunder::jobs::CancellationToken cancellation;
  chromasunder::jobs::ProgressState progress;
  auto outcome = backend.render(
      RenderRequest{any_source, settings, mask, interval_image}, cancellation, progress);
  expect(outcome.succeeded(), "render succeeds");
  return std::get<ImageBuffer<T>>(std::move(*outcome.image));
}

void test_image_types_and_validation() {
  auto [empty, empty_error] = ImageBuffer<std::uint8_t>::create(0, 0);
  expect(empty.has_value() && !empty_error && empty->size_bytes() == 0,
         "empty image is represented safely");
  auto [overflow, overflow_error] = ImageBuffer<std::uint16_t>::create(
      std::numeric_limits<std::size_t>::max(), 2);
  expect(!overflow && overflow_error.code == ErrorCode::size_overflow,
         "image dimension overflow is typed");
  bool invalid_binary_rejected = false;
  try {
    [[maybe_unused]] BinaryImage invalid(2, 2, {1, 0});
  } catch (const std::invalid_argument&) {
    invalid_binary_rejected = true;
  }
  expect(invalid_binary_rejected, "binary image storage invariant is enforced");

  PixelSortSettings settings;
  expect(!chromasunder::processing::validate_settings(settings), "default settings validate");
  settings.lower_threshold = -0.01;
  expect(chromasunder::processing::validate_settings(settings).code ==
             ErrorCode::invalid_settings,
         "negative lower threshold rejected");
  settings.lower_threshold = 0.8;
  settings.upper_threshold = 0.2;
  expect(chromasunder::processing::validate_settings(settings).code ==
             ErrorCode::invalid_settings,
         "inverted thresholds rejected");
  settings = {};
  settings.randomness_percentage = 100.01;
  expect(chromasunder::processing::validate_settings(settings).code ==
             ErrorCode::invalid_settings,
         "randomness over 100 rejected");
  settings = {};
  settings.characteristic_length = 0;
  expect(chromasunder::processing::validate_settings(settings).code ==
             ErrorCode::invalid_settings,
         "zero characteristic length rejected");
  settings = {};
  settings.angle_degrees = std::numeric_limits<double>::infinity();
  expect(chromasunder::processing::validate_settings(settings).code ==
             ErrorCode::invalid_settings,
         "infinite angle rejected");
  settings = {};
  settings.interval_mode = IntervalMode::file;
  expect(chromasunder::processing::validate_settings(settings).code ==
             ErrorCode::missing_interval_image,
         "file mode requires interval image");
}

void test_sorting() {
  using P8 = RgbaPixel<std::uint8_t>;
  using P16 = RgbaPixel<std::uint16_t>;
  expect(chromasunder::processing::sorting_key(P16{65535, 65535, 65535, 0},
                                               SortingMode::intensity) == 196605,
         "U16 intensity does not overflow");
  expect(chromasunder::processing::hue_key(P8{255, 0, 0, 0}) == 0,
         "red hue is zero");
  expect(chromasunder::processing::hue_key(P8{0, 255, 0, 0}) ==
             chromasunder::processing::key_scale / 3,
         "green hue is one third");
  expect(chromasunder::processing::hue_key(P8{0, 0, 255, 0}) ==
             chromasunder::processing::key_scale * 2 / 3,
         "blue hue is two thirds");
  expect(chromasunder::processing::saturation_key(P8{80, 80, 80, 0}) == 0,
         "achromatic saturation is zero");
  expect(chromasunder::processing::saturation_key(P8{255, 0, 0, 0}) ==
             chromasunder::processing::key_scale,
         "primary saturation is one");

  std::vector<P8> tied{{20, 10, 0, 11}, {0, 10, 20, 22}, {15, 5, 10, 33}};
  chromasunder::processing::stable_sort_pixels(tied, SortingMode::intensity);
  expect(tied[0].a == 11 && tied[1].a == 22 && tied[2].a == 33,
         "stable ties preserve incoming order and alpha");

  std::vector<P16> precise{{256, 1, 255, 4321}, {1, 2, 3, 1234}};
  chromasunder::processing::stable_sort_pixels(precise, SortingMode::intensity);
  expect(precise[1].r == 256 && precise[1].a == 4321,
         "U16-only values and alpha move exactly");
}

void test_intervals() {
  using Pixel = RgbaPixel<std::uint8_t>;
  SplitMix64 rng(1);
  const std::vector<Pixel> pixels{{0, 0, 0, 1},       {64, 64, 64, 2},
                                  {128, 128, 128, 3}, {255, 255, 255, 4},
                                  {64, 64, 64, 5}};
  expect(chromasunder::processing::detect_intervals<std::uint8_t>(
             pixels, IntervalMode::none, 0, 1, 3, rng) == std::vector<Interval>{{0, 5}},
         "none emits whole path");
  expect(chromasunder::processing::detect_intervals<std::uint8_t>(
             std::span<const Pixel>{pixels}.first(1), IntervalMode::none, 0, 1, 3, rng)
             .empty(),
         "none drops one pixel path");
  const std::vector<Pixel> threshold_pixels{{255, 0, 0, 0}, {0, 255, 0, 0},
                                             {0, 0, 255, 0}, {255, 255, 255, 0}};
  const auto threshold = chromasunder::processing::detect_intervals<std::uint8_t>(
      threshold_pixels, IntervalMode::threshold, 0.5, 0.5, 3, rng);
  expect(threshold == std::vector<Interval>{{0, 3}}, "threshold boundaries are inclusive");

  const std::vector<Pixel> edge_pixels{{0, 0, 0, 0}, {255, 255, 255, 0},
                                        {255, 255, 255, 0}, {0, 0, 0, 0}};
  const auto edges = chromasunder::processing::detect_intervals<std::uint8_t>(
      edge_pixels, IntervalMode::edges, 1.0, 1, 3, rng);
  expect(edges == std::vector<Interval>{{1, 3}},
         "edges use inclusive adjacent boundaries and drop singleton regions");

  const std::vector<std::uint8_t> bits{0, 0, 1, 1, 1, 0, 0, 0};
  std::vector<Pixel> binary_pixels(bits.size());
  const auto file = chromasunder::processing::detect_intervals<std::uint8_t>(
      binary_pixels, IntervalMode::file, 0.5, 1, 3, rng, bits);
  expect(file == std::vector<Interval>{{2, 5}}, "file emits true runs only");
  const auto file_edges = chromasunder::processing::detect_intervals<std::uint8_t>(
      binary_pixels, IntervalMode::file_edges, 0.5, 1, 3, rng, bits);
  expect(file_edges == std::vector<Interval>({{0, 2}, {2, 5}, {5, 8}}),
         "file edges preserve V1 transition boundaries");

  SplitMix64 random_a(99);
  SplitMix64 random_b(99);
  expect(chromasunder::processing::detect_intervals<std::uint8_t>(
             binary_pixels, IntervalMode::random, 0, 1, 4, random_a) ==
             chromasunder::processing::detect_intervals<std::uint8_t>(
                 binary_pixels, IntervalMode::random, 0, 1, 4, random_b),
         "random intervals repeat for the same RNG state");
  SplitMix64 waves_a(101);
  SplitMix64 waves_b(101);
  expect(chromasunder::processing::detect_intervals<std::uint8_t>(
             binary_pixels, IntervalMode::waves, 0, 1, 2, waves_a) ==
             chromasunder::processing::detect_intervals<std::uint8_t>(
                 binary_pixels, IntervalMode::waves, 0, 1, 2, waves_b),
         "waves repeat for the same RNG state");
}

void test_paths() {
  const std::array<double, 42> angles{
      0,   1,   15,  44,  45,  46,  89,  90,  91,  135, 179, 180, 181, 225,
      269, 270, 271, 315, 359, -1,  -45, -90, -180, -270, 360, 361, 405, 719,
      0.1, 12.5, 33.3, 77.7, 123.4, 166.6, 200.2, 244.8, 288.9, 333.3,
      89.999, 90.001, 269.999, 270.001};
  const std::array<std::pair<std::size_t, std::size_t>, 9> dimensions{
      std::pair{1U, 1U}, {1U, 9U}, {9U, 1U}, {2U, 2U}, {3U, 2U},
      {7U, 5U}, {8U, 7U}, {16U, 9U}, {31U, 24U}};
  std::size_t cases = 0;
  for (const auto [width, height] : dimensions) {
    for (const auto angle : angles) {
      StraightDirectionalPathProvider provider(width, height, angle);
      std::vector<unsigned> visits(width * height, 0);
      for (std::size_t path_index = 0; path_index < provider.path_count(); ++path_index) {
        const auto& path = provider.path(path_index);
        std::optional<chromasunder::processing::Coordinate> previous;
        for (std::size_t index = 0; index < path.size(); ++index) {
          const auto coordinate = path.position(index);
          expect(coordinate.x < width && coordinate.y < height, "path coordinate is in bounds");
          if (coordinate.x < width && coordinate.y < height)
            ++visits[coordinate.y * width + coordinate.x];
          if (previous) {
            const auto radians = chromasunder::processing::normalized_angle(angle) *
                                 std::numbers::pi / 180.0;
            const auto movement_x = static_cast<double>(coordinate.x) - previous->x;
            const auto movement_y = static_cast<double>(coordinate.y) - previous->y;
            const auto projection = movement_x * std::cos(radians) -
                                    movement_y * std::sin(radians);
            expect(projection > 0.0, "path traversal advances in the requested direction");
          }
          previous = coordinate;
        }
      }
      expect(std::all_of(visits.begin(), visits.end(), [](unsigned count) { return count == 1; }),
             "directional paths cover each pixel exactly once");
      ++cases;
    }
  }
  expect(cases == angles.size() * dimensions.size(), "all path property cases executed");

  StraightDirectionalPathProvider horizontal(3, 2, 0);
  expect(horizontal.path(0).position(0) == chromasunder::processing::Coordinate{0, 0} &&
             horizontal.path(0).position(2) == chromasunder::processing::Coordinate{2, 0},
         "zero degrees traverses left to right");
  StraightDirectionalPathProvider upward(2, 3, 90);
  expect(upward.path(0).position(0) == chromasunder::processing::Coordinate{0, 2} &&
             upward.path(0).position(2) == chromasunder::processing::Coordinate{0, 0},
         "90 degrees traverses bottom to top");
}

void test_render_mask_precision_and_determinism() {
  using Pixel = RgbaPixel<std::uint8_t>;
  auto source = make_image<std::uint8_t>(
      6, 1, {{250, 0, 0, 10}, {10, 0, 0, 20}, {200, 0, 0, 30},
             {20, 0, 0, 40}, {150, 0, 0, 50}, {30, 0, 0, 60}});
  BinaryImage mask(6, 1, {1, 0, 1, 0, 0, 1});
  PixelSortSettings settings;
  settings.interval_mode = IntervalMode::none;
  settings.sorting_mode = SortingMode::intensity;
  auto output = render(source, settings, 1, &mask);
  expect(output.pixels()[0] == Pixel{30, 0, 0, 60} &&
             output.pixels()[2] == Pixel{200, 0, 0, 30} &&
             output.pixels()[5] == Pixel{250, 0, 0, 10},
         "enabled pixels sort across mask gaps with alpha attached");
  expect(output.pixels()[1] == source.pixels()[1] && output.pixels()[3] == source.pixels()[3] &&
             output.pixels()[4] == source.pixels()[4],
         "masked-off pixels remain untouched");

  auto source16 = make_image<std::uint16_t>(
      4, 1, {{32768, 1, 256, 65534}, {255, 257, 0, 1}, {65534, 2, 3, 32767},
             {1, 65535, 256, 42}});
  auto output16 = render(source16, settings, 2);
  auto expected16 = std::vector(source16.pixels().begin(), source16.pixels().end());
  std::stable_sort(expected16.begin(), expected16.end(), [](const auto& left, const auto& right) {
    return static_cast<std::uint64_t>(left.r) + left.g + left.b <
           static_cast<std::uint64_t>(right.r) + right.g + right.b;
  });
  expect(std::equal(output16.pixels().begin(), output16.pixels().end(), expected16.begin()),
         "U16 render preserves exact non-U8 channel values");

  auto deterministic_source = make_image<std::uint8_t>(
      97, 61, representative_pixels<std::uint8_t>(97, 61));
  settings.interval_mode = IntervalMode::random;
  settings.sorting_mode = SortingMode::hue;
  settings.characteristic_length = 13;
  settings.angle_degrees = 45;
  settings.randomness_percentage = 37.5;
  settings.seed = 0x123456789ABCDEF0ULL;
  const auto one = render(deterministic_source, settings, 1);
  const auto two = render(deterministic_source, settings, 2);
  const auto many = render(deterministic_source, settings, 7);
  expect(std::equal(one.pixels().begin(), one.pixels().end(), two.pixels().begin()) &&
             std::equal(one.pixels().begin(), one.pixels().end(), many.pixels().begin()),
         "one, two, and N workers produce identical bytes");
  expect(image_hash(one) == image_hash(many), "deterministic render hashes match");
  expect(image_hash(one) == 0x7FD90D050A0A69C1ULL,
         "random deterministic hash matches the cross-platform contract");
  auto different_settings = settings;
  different_settings.seed++;
  const auto different = render(deterministic_source, different_settings, 3);
  expect(!std::equal(one.pixels().begin(), one.pixels().end(), different.pixels().begin()),
         "different seed changes a discriminating render");

  auto multiset_before =
      std::vector(deterministic_source.pixels().begin(), deterministic_source.pixels().end());
  auto multiset_after = std::vector(one.pixels().begin(), one.pixels().end());
  std::sort(multiset_before.begin(), multiset_before.end());
  std::sort(multiset_after.begin(), multiset_after.end());
  expect(multiset_before == multiset_after, "direct paths preserve the exact RGBA multiset");

  std::cout << "determinism_fnv1a64=" << std::hex << image_hash(one) << std::dec << '\n';
  settings.interval_mode = IntervalMode::waves;
  const auto waves_one = render(deterministic_source, settings, 1);
  const auto waves_many = render(deterministic_source, settings, 7);
  expect(std::equal(waves_one.pixels().begin(), waves_one.pixels().end(),
                    waves_many.pixels().begin()),
         "waves and interval skipping are worker-count deterministic");
  expect(image_hash(waves_one) == 0xEC2E6D4BBF6AA2C1ULL,
         "waves deterministic hash matches the cross-platform contract");
  std::cout << "waves_determinism_fnv1a64=" << std::hex << image_hash(waves_one) << std::dec
            << '\n';
}

void test_memory_progress_and_transactions() {
  chromasunder::memory::RenderMemoryEstimate estimate;
  auto error = chromasunder::memory::estimate_render_memory(
      {100, 50, chromasunder::image::PixelFormat::rgba16, 40000, true, true, 4, 1000, 2000},
      estimate);
  expect(!error && estimate.source_bytes == 40000 && estimate.candidate_bytes == 40000 &&
             estimate.previous_render_bytes == 40000 && estimate.mask_bytes == 5000 &&
             estimate.interval_image_bytes == 5000 && estimate.total_bytes > 132000,
         "memory estimate accounts for retained, candidate, auxiliaries, scratch, codec, margin");
  chromasunder::memory::MemoryBudget tiny{estimate.total_bytes - 1};
  expect(tiny.check(estimate).code == ErrorCode::insufficient_memory_budget &&
             tiny.check(estimate).estimated_bytes == estimate.total_bytes,
         "memory budget returns an actionable typed error");

  auto source = make_image<std::uint8_t>(20, 10, representative_pixels<std::uint8_t>(20, 10));
  AnyImage any_source = source;
  PixelSortSettings settings;
  settings.interval_mode = IntervalMode::none;
  CpuRenderBackend backend(2);
  FullRenderStore store;
  chromasunder::jobs::CancellationToken first_token;
  chromasunder::jobs::ProgressState progress;
  expect(!store.render_and_promote(backend, RenderRequest{any_source, settings}, first_token,
                                   progress),
         "first full render promotes");
  const auto first_hash = image_hash(std::get<ImageBuffer<std::uint8_t>>(*store.last_completed()));
  expect(progress.snapshot().stage == chromasunder::jobs::RenderStage::completed &&
             progress.snapshot().fraction() == 1.0,
         "progress is tied to completed pixel work");

  chromasunder::jobs::CancellationToken cancelled;
  cancelled.cancel();
  settings.angle_degrees = 45;
  expect(store.render_and_promote(backend, RenderRequest{any_source, settings}, cancelled, progress)
                 .code == ErrorCode::cancelled,
         "cancelled candidate returns typed cancellation");
  expect(image_hash(std::get<ImageBuffer<std::uint8_t>>(*store.last_completed())) == first_hash,
         "cancelled candidate cannot replace completed render");

  RenderRequest over_budget{any_source, settings};
  over_budget.memory_budget.allowed_bytes = 1;
  expect(store.render_and_promote(backend, over_budget, first_token, progress).code ==
             ErrorCode::insufficient_memory_budget,
         "unsafe render is rejected before candidate allocation");
  expect(image_hash(std::get<ImageBuffer<std::uint8_t>>(*store.last_completed())) == first_hash,
         "failed candidate cannot replace completed render");

  auto large = make_image<std::uint8_t>(2000, 1000,
                                        representative_pixels<std::uint8_t>(2000, 1000));
  AnyImage large_source = std::move(large);
  PixelSortSettings slow_settings;
  slow_settings.interval_mode = IntervalMode::none;
  slow_settings.sorting_mode = SortingMode::hue;
  slow_settings.angle_degrees = 45;
  chromasunder::jobs::CancellationToken asynchronous;
  chromasunder::Error asynchronous_error;
  std::thread render_thread([&] {
    asynchronous_error = store.render_and_promote(
        backend, RenderRequest{large_source, slow_settings}, asynchronous, progress);
  });
  std::this_thread::sleep_for(std::chrono::milliseconds(1));
  asynchronous.cancel();
  render_thread.join();
  expect(asynchronous_error.code == ErrorCode::cancelled,
         "cancellation from another thread safely stops in-progress work");
  expect(image_hash(std::get<ImageBuffer<std::uint8_t>>(*store.last_completed())) == first_hash,
         "mid-work cancellation preserves the prior completed render");
}

}  // namespace

int main() {
  test_image_types_and_validation();
  test_sorting();
  test_intervals();
  test_paths();
  test_render_mask_precision_and_determinism();
  test_memory_progress_and_transactions();
  if (failures != 0) {
    std::cerr << failures << " native core assertion(s) failed\n";
    return 1;
  }
  std::cout << "native core assertions passed\n";
  return 0;
}
