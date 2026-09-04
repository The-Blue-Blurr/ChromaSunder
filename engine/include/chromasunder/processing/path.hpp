#pragma once

#include "chromasunder/processing/settings.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <numbers>
#include <vector>

namespace chromasunder::processing {

struct Coordinate {
  std::size_t x{};
  std::size_t y{};
  auto operator<=>(const Coordinate&) const = default;
};

class PathDescriptor {
 public:
  enum class MajorAxis { x, y };

  PathDescriptor() = default;
  PathDescriptor(std::uint64_t stable_id, MajorAxis axis, std::size_t width,
                 std::size_t height, bool primary_reverse, std::int64_t slope_q32,
                 std::int64_t path_id, std::size_t begin, std::size_t end) noexcept
      : stable_id_(stable_id), axis_(axis), width_(width), height_(height),
        primary_reverse_(primary_reverse), slope_q32_(slope_q32), path_id_(path_id),
        begin_(begin), end_(end) {}

  [[nodiscard]] std::uint64_t stable_id() const noexcept { return stable_id_; }
  [[nodiscard]] std::size_t size() const noexcept { return end_ - begin_; }
  [[nodiscard]] Coordinate position(std::size_t index) const noexcept {
    const auto u = begin_ + index;
    const auto offset = rounded_offset(u);
    const auto secondary = path_id_ + offset;
    if (axis_ == MajorAxis::x) {
      const auto x = primary_reverse_ ? width_ - 1 - u : u;
      return {x, static_cast<std::size_t>(secondary)};
    }
    const auto y = primary_reverse_ ? height_ - 1 - u : u;
    return {static_cast<std::size_t>(secondary), y};
  }

 private:
  [[nodiscard]] std::int64_t rounded_offset(std::size_t u) const noexcept {
    const auto value = slope_q32_ * static_cast<std::int64_t>(u);
    constexpr std::int64_t half = 1LL << 31U;
    return value >= 0 ? (value + half) / (1LL << 32U)
                      : -((-value + half) / (1LL << 32U));
  }

  std::uint64_t stable_id_{0};
  MajorAxis axis_{MajorAxis::x};
  std::size_t width_{0};
  std::size_t height_{0};
  bool primary_reverse_{false};
  std::int64_t slope_q32_{0};
  std::int64_t path_id_{0};
  std::size_t begin_{0};
  std::size_t end_{0};
};

class PathProvider {
 public:
  virtual ~PathProvider() = default;
  [[nodiscard]] virtual std::size_t path_count() const noexcept = 0;
  [[nodiscard]] virtual const PathDescriptor& path(std::size_t index) const = 0;
};

class StraightDirectionalPathProvider final : public PathProvider {
 public:
  StraightDirectionalPathProvider(std::size_t width, std::size_t height, double angle_degrees);

  [[nodiscard]] std::size_t path_count() const noexcept override { return paths_.size(); }
  [[nodiscard]] const PathDescriptor& path(std::size_t index) const override {
    return paths_.at(index);
  }
  [[nodiscard]] double normalized_angle_degrees() const noexcept { return angle_; }

 private:
  double angle_{0.0};
  std::vector<PathDescriptor> paths_;
};

}  // namespace chromasunder::processing
