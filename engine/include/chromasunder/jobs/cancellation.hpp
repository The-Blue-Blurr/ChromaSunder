#pragma once

#include <atomic>
#include <memory>

namespace chromasunder::jobs {

class CancellationToken {
 public:
  CancellationToken() : cancelled_(std::make_shared<std::atomic_bool>(false)) {}

  void cancel() const noexcept { cancelled_->store(true, std::memory_order_release); }
  [[nodiscard]] bool is_cancelled() const noexcept {
    return cancelled_->load(std::memory_order_acquire);
  }

 private:
  std::shared_ptr<std::atomic_bool> cancelled_;
};

}  // namespace chromasunder::jobs
