#include "chromasunder/memory/render_budget.hpp"

#include <algorithm>
#include <cstddef>
#include <limits>

namespace chromasunder::memory {
namespace {

bool checked_add(std::size_t& total, std::size_t value) {
  if (value > std::numeric_limits<std::size_t>::max() - total) return false;
  total += value;
  return true;
}

bool checked_multiply(std::size_t left, std::size_t right, std::size_t& result) {
  if (left != 0 && right > std::numeric_limits<std::size_t>::max() / left) return false;
  result = left * right;
  return true;
}

}  // namespace

Error estimate_render_memory(const RenderMemoryInputs& inputs,
                             RenderMemoryEstimate& estimate) noexcept {
  estimate = {};
  std::size_t pixels{};
  if (!checked_multiply(inputs.width, inputs.height, pixels)) {
    return {ErrorCode::size_overflow, "Image dimensions overflow memory estimation."};
  }
  if (!checked_multiply(pixels, image::bytes_per_pixel(inputs.format), estimate.source_bytes)) {
    return {ErrorCode::size_overflow, "Source byte size overflows memory estimation."};
  }
  estimate.candidate_bytes = estimate.source_bytes;
  estimate.previous_render_bytes = inputs.previous_render_bytes;
  estimate.mask_bytes = inputs.has_mask ? pixels : 0;
  estimate.interval_image_bytes = inputs.has_interval_image ? pixels : 0;
  const auto longest_path = std::max(inputs.width, inputs.height);
  // Path pixels + sortable pixels + mask/interval bytes + interval/index metadata,
  // keyed entries, and a full-size stable-sort temporary buffer.
  const auto scratch_per_pixel = 2 * image::bytes_per_pixel(inputs.format) + 50;
  if (!checked_multiply(longest_path, scratch_per_pixel,
                        estimate.worker_scratch_bytes) ||
      !checked_multiply(estimate.worker_scratch_bytes, std::max<std::size_t>(1, inputs.worker_count),
                        estimate.worker_scratch_bytes)) {
    return {ErrorCode::size_overflow, "Worker scratch size overflows memory estimation."};
  }
  if (!checked_add(estimate.path_metadata_bytes, inputs.width) ||
      !checked_add(estimate.path_metadata_bytes, inputs.height) ||
      !checked_multiply(estimate.path_metadata_bytes, 96, estimate.path_metadata_bytes)) {
    return {ErrorCode::size_overflow, "Path metadata size overflows memory estimation."};
  }
  if (!checked_multiply(std::max<std::size_t>(1, inputs.worker_count), 256,
                        estimate.task_queue_bytes)) {
    return {ErrorCode::size_overflow, "Task queue size overflows memory estimation."};
  }
  estimate.codec_allowance_bytes = inputs.codec_allowance_bytes;
  estimate.safety_margin_bytes = inputs.safety_margin_bytes;
  estimate.total_bytes = 0;
  if (!checked_add(estimate.total_bytes, estimate.source_bytes) ||
      !checked_add(estimate.total_bytes, estimate.previous_render_bytes) ||
      !checked_add(estimate.total_bytes, estimate.candidate_bytes) ||
      !checked_add(estimate.total_bytes, estimate.mask_bytes) ||
      !checked_add(estimate.total_bytes, estimate.interval_image_bytes) ||
      !checked_add(estimate.total_bytes, estimate.worker_scratch_bytes) ||
      !checked_add(estimate.total_bytes, estimate.path_metadata_bytes) ||
      !checked_add(estimate.total_bytes, estimate.task_queue_bytes) ||
      !checked_add(estimate.total_bytes, estimate.codec_allowance_bytes) ||
      !checked_add(estimate.total_bytes, estimate.safety_margin_bytes)) {
    return {ErrorCode::size_overflow, "Total render estimate overflows."};
  }
  return {};
}

}  // namespace chromasunder::memory
