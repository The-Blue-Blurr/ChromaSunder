#pragma once

#include <condition_variable>
#include <cstddef>
#include <deque>
#include <functional>
#include <mutex>
#include <thread>
#include <vector>

namespace chromasunder::jobs {

class ThreadPool {
 public:
  explicit ThreadPool(std::size_t worker_count = automatic_worker_count(),
                      std::size_t worker_cap = 0);
  ~ThreadPool();
  ThreadPool(const ThreadPool&) = delete;
  ThreadPool& operator=(const ThreadPool&) = delete;

  [[nodiscard]] std::size_t worker_count() const noexcept { return workers_.size(); }
  void parallel_for(std::size_t count, const std::function<void(std::size_t)>& operation);

  [[nodiscard]] static std::size_t automatic_worker_count() noexcept;

 private:
  void worker_loop();

  std::vector<std::thread> workers_;
  std::deque<std::function<void()>> tasks_;
  std::mutex mutex_;
  std::condition_variable ready_;
  bool stopping_{false};
};

}  // namespace chromasunder::jobs
