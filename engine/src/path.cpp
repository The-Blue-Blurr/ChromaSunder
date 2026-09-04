#include "chromasunder/processing/path.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <numbers>
#include <vector>

namespace chromasunder::processing {
namespace {

constexpr double cardinal_snap_epsilon = 1e-9;
constexpr double q32_scale = 4294967296.0;

std::int64_t rounded_offset(std::int64_t slope_q32, std::size_t u) {
  const auto value = slope_q32 * static_cast<std::int64_t>(u);
  constexpr std::int64_t half = 1LL << 31U;
  return value >= 0 ? (value + half) / (1LL << 32U)
                    : -((-value + half) / (1LL << 32U));
}

bool near(double value, double target) { return std::abs(value - target) <= cardinal_snap_epsilon; }

}  // namespace

StraightDirectionalPathProvider::StraightDirectionalPathProvider(std::size_t width,
                                                                 std::size_t height,
                                                                 double angle_degrees)
    : angle_(normalized_angle(angle_degrees)) {
  if (!std::isfinite(angle_degrees) || width == 0 || height == 0 ||
      width > static_cast<std::size_t>(std::numeric_limits<std::int32_t>::max()) ||
      height > static_cast<std::size_t>(std::numeric_limits<std::int32_t>::max()))
    return;

  const bool cardinal_0 = near(angle_, 0.0);
  const bool cardinal_90 = near(angle_, 90.0);
  const bool cardinal_180 = near(angle_, 180.0);
  const bool cardinal_270 = near(angle_, 270.0);
  if (cardinal_0 || cardinal_180) {
    const bool reverse = cardinal_180;
    for (std::size_t order = 0; order < height; ++order) {
      const auto y = reverse ? height - 1 - order : order;
      paths_.emplace_back(y, PathDescriptor::MajorAxis::x, width, height, reverse, 0,
                          static_cast<std::int64_t>(y), 0, width);
    }
    return;
  }
  if (cardinal_90 || cardinal_270) {
    const bool reverse_primary = cardinal_90;
    for (std::size_t order = 0; order < width; ++order) {
      const auto x = cardinal_270 ? width - 1 - order : order;
      paths_.emplace_back(x, PathDescriptor::MajorAxis::y, width, height, reverse_primary, 0,
                          static_cast<std::int64_t>(x), 0, height);
    }
    return;
  }

  const auto radians = angle_ * std::numbers::pi / 180.0;
  const auto dx = std::cos(radians);
  const auto dy = -std::sin(radians);
  const bool x_major = std::abs(dx) >= std::abs(dy);
  const bool reverse = x_major ? dx < 0.0 : dy < 0.0;
  const auto primary_length = x_major ? width : height;
  const auto secondary_length = x_major ? height : width;
  const auto slope = x_major ? dy / std::abs(dx) : dx / std::abs(dy);
  const auto slope_q32 = static_cast<std::int64_t>(std::round(slope * q32_scale));

  auto minimum_id = std::numeric_limits<std::int64_t>::max();
  auto maximum_id = std::numeric_limits<std::int64_t>::min();
  for (std::size_t u = 0; u < primary_length; ++u) {
    const auto offset = rounded_offset(slope_q32, u);
    minimum_id = std::min(minimum_id, -offset);
    maximum_id = std::max(maximum_id,
                          static_cast<std::int64_t>(secondary_length - 1) - offset);
  }
  struct Range {
    std::size_t begin{std::numeric_limits<std::size_t>::max()};
    std::size_t end{0};
  };
  std::vector<Range> ranges(static_cast<std::size_t>(maximum_id - minimum_id + 1));
  for (std::size_t u = 0; u < primary_length; ++u) {
    const auto offset = rounded_offset(slope_q32, u);
    for (std::size_t secondary = 0; secondary < secondary_length; ++secondary) {
      const auto path_id = static_cast<std::int64_t>(secondary) - offset;
      auto& range = ranges[static_cast<std::size_t>(path_id - minimum_id)];
      range.begin = std::min(range.begin, u);
      range.end = std::max(range.end, u + 1);
    }
  }
  paths_.reserve(ranges.size());
  for (std::size_t index = 0; index < ranges.size(); ++index) {
    const auto& range = ranges[index];
    if (range.begin == std::numeric_limits<std::size_t>::max()) continue;
    const auto path_id = minimum_id + static_cast<std::int64_t>(index);
    const auto stable_id = static_cast<std::uint64_t>(path_id - minimum_id);
    paths_.emplace_back(stable_id,
                        x_major ? PathDescriptor::MajorAxis::x : PathDescriptor::MajorAxis::y,
                        width, height, reverse, slope_q32, path_id, range.begin, range.end);
  }
}

}  // namespace chromasunder::processing
