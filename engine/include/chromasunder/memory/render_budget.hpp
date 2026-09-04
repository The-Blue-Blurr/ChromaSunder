#pragma once

#include "chromasunder/error.hpp"
#include "chromasunder/image/pixel_format.hpp"

#include <cstddef>
#include <limits>

namespace chromasunder::memory {

struct RenderMemoryInputs {
  std::size_t width{};
  std::size_t height{};
  image::PixelFormat format{image::PixelFormat::rgba8};
  std::size_t previous_render_bytes{0};
  bool has_mask{false};
  bool has_interval_image{false};
  std::size_t worker_count{1};
  std::size_t codec_allowance_bytes{0};
  std::size_t safety_margin_bytes{0};
};

struct RenderMemoryEstimate {
  std::size_t source_bytes{};
  std::size_t previous_render_bytes{};
  std::size_t candidate_bytes{};
  std::size_t mask_bytes{};
  std::size_t interval_image_bytes{};
  std::size_t worker_scratch_bytes{};
  std::size_t path_metadata_bytes{};
  std::size_t task_queue_bytes{};
  std::size_t codec_allowance_bytes{};
  std::size_t safety_margin_bytes{};
  std::size_t total_bytes{};
};

[[nodiscard]] Error estimate_render_memory(const RenderMemoryInputs& inputs,
                                           RenderMemoryEstimate& estimate) noexcept;

struct MemoryBudget {
  std::size_t allowed_bytes{std::numeric_limits<std::size_t>::max()};

  [[nodiscard]] Error check(const RenderMemoryEstimate& estimate) const noexcept {
    if (estimate.total_bytes > allowed_bytes) {
      return {ErrorCode::insufficient_memory_budget,
              "Estimated render memory exceeds the configured budget.", estimate.total_bytes,
              allowed_bytes};
    }
    return {};
  }
};

}  // namespace chromasunder::memory
