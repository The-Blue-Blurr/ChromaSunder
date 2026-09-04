#pragma once

#include "chromasunder/error.hpp"
#include "chromasunder/image/any_image.hpp"
#include "chromasunder/jobs/cancellation.hpp"
#include "chromasunder/jobs/progress.hpp"
#include "chromasunder/jobs/thread_pool.hpp"
#include "chromasunder/memory/render_budget.hpp"
#include "chromasunder/processing/mask.hpp"
#include "chromasunder/processing/settings.hpp"

#include <cstdint>
#include <mutex>
#include <memory>
#include <optional>
#include <variant>

namespace chromasunder::processing {

using AnyImage = image::AnyImage;

struct RenderRequest {
  const AnyImage& source;
  PixelSortSettings settings;
  const BinaryImage* mask{nullptr};
  const BinaryImage* interval_image{nullptr};
  memory::MemoryBudget memory_budget{};
  std::size_t codec_allowance_bytes{0};
  std::size_t safety_margin_bytes{0};
  std::size_t previous_completed_bytes{0};
};

struct RenderOutcome {
  std::optional<AnyImage> image;
  Error error;
  memory::RenderMemoryEstimate memory_estimate;

  [[nodiscard]] bool succeeded() const noexcept { return image.has_value() && !error; }
};

class RenderBackend {
 public:
  virtual ~RenderBackend() = default;
  [[nodiscard]] virtual RenderOutcome render(const RenderRequest& request,
                                             const jobs::CancellationToken& cancellation,
                                             jobs::ProgressState& progress) = 0;
};

class CpuRenderBackend final : public RenderBackend {
 public:
  explicit CpuRenderBackend(std::size_t worker_count = jobs::ThreadPool::automatic_worker_count(),
                            std::size_t worker_cap = 0)
      : pool_(worker_count, worker_cap) {}

  [[nodiscard]] RenderOutcome render(const RenderRequest& request,
                                     const jobs::CancellationToken& cancellation,
                                     jobs::ProgressState& progress) override;
  [[nodiscard]] std::size_t worker_count() const noexcept { return pool_.worker_count(); }

 private:
  jobs::ThreadPool pool_;
};

class FullRenderStore {
 public:
  [[nodiscard]] std::shared_ptr<const AnyImage> last_completed() const {
    std::lock_guard lock(mutex_);
    return last_completed_;
  }
  [[nodiscard]] Error render_and_promote(RenderBackend& backend, const RenderRequest& request,
                                         const jobs::CancellationToken& cancellation,
                                         jobs::ProgressState& progress);

 private:
  mutable std::mutex mutex_;
  std::shared_ptr<const AnyImage> last_completed_;
};

}  // namespace chromasunder::processing
