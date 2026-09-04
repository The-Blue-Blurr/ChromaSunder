#pragma once

#include <atomic>
#include <cstddef>

namespace chromasunder::jobs {

enum class RenderStage {
  preparing_image,
  generating_paths,
  sorting,
  building_preview,
  encoding,
  completed,
};

struct ProgressSnapshot {
  RenderStage stage{RenderStage::preparing_image};
  std::size_t completed_units{0};
  std::size_t total_units{0};

  [[nodiscard]] double fraction() const noexcept {
    return total_units == 0 ? 0.0
                            : static_cast<double>(completed_units) /
                                  static_cast<double>(total_units);
  }
};

class ProgressState {
 public:
  void reset(RenderStage stage, std::size_t total_units) noexcept {
    stage_.store(stage, std::memory_order_release);
    completed_.store(0, std::memory_order_release);
    total_.store(total_units, std::memory_order_release);
  }
  void add_completed(std::size_t units) noexcept {
    completed_.fetch_add(units, std::memory_order_acq_rel);
  }
  void complete(RenderStage stage = RenderStage::completed) noexcept {
    completed_.store(total_.load(std::memory_order_acquire), std::memory_order_release);
    stage_.store(stage, std::memory_order_release);
  }
  [[nodiscard]] ProgressSnapshot snapshot() const noexcept {
    return {stage_.load(std::memory_order_acquire),
            completed_.load(std::memory_order_acquire),
            total_.load(std::memory_order_acquire)};
  }

 private:
  std::atomic<RenderStage> stage_{RenderStage::preparing_image};
  std::atomic_size_t completed_{0};
  std::atomic_size_t total_{0};
};

}  // namespace chromasunder::jobs
