#pragma once

#include "chromasunder/error.hpp"

#include <cmath>
#include <cstddef>
#include <cstdint>

namespace chromasunder::processing {

enum class IntervalMode { threshold, edges, random, waves, file, file_edges, none };
enum class SortingMode { lightness, hue, saturation, intensity, minimum };

struct PixelSortSettings {
  IntervalMode interval_mode{IntervalMode::threshold};
  SortingMode sorting_mode{SortingMode::lightness};
  double lower_threshold{0.25};
  double upper_threshold{0.80};
  std::size_t characteristic_length{50};
  double angle_degrees{0.0};
  double randomness_percentage{0.0};
  std::uint64_t seed{0};
};

[[nodiscard]] inline Error validate_settings(const PixelSortSettings& settings,
                                             bool has_interval_image = false) {
  if (!std::isfinite(settings.lower_threshold) || settings.lower_threshold < 0.0 ||
      settings.lower_threshold > 1.0) {
    return {ErrorCode::invalid_settings, "Lower threshold must be finite and in [0,1]."};
  }
  if (!std::isfinite(settings.upper_threshold) || settings.upper_threshold < 0.0 ||
      settings.upper_threshold > 1.0) {
    return {ErrorCode::invalid_settings, "Upper threshold must be finite and in [0,1]."};
  }
  if (settings.lower_threshold > settings.upper_threshold) {
    return {ErrorCode::invalid_settings, "Lower threshold must not exceed upper threshold."};
  }
  if (settings.characteristic_length < 1) {
    return {ErrorCode::invalid_settings, "Characteristic length must be at least 1."};
  }
  if (!std::isfinite(settings.angle_degrees)) {
    return {ErrorCode::invalid_settings, "Angle must be finite."};
  }
  if (!std::isfinite(settings.randomness_percentage) ||
      settings.randomness_percentage < 0.0 || settings.randomness_percentage > 100.0) {
    return {ErrorCode::invalid_settings, "Randomness must be finite and in [0,100]."};
  }
  if ((settings.interval_mode == IntervalMode::file ||
       settings.interval_mode == IntervalMode::file_edges) &&
      !has_interval_image) {
    return {ErrorCode::missing_interval_image,
            "An interval image is required for the selected interval mode."};
  }
  return {};
}

[[nodiscard]] inline double normalized_angle(double angle) noexcept {
  auto value = std::fmod(angle, 360.0);
  if (value < 0.0) value += 360.0;
  return value == 360.0 ? 0.0 : value;
}

}  // namespace chromasunder::processing
