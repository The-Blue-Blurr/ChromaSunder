#include "chromasunder/jobs/thread_pool.hpp"

#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <exception>
#include <functional>
#include <mutex>
#include <memory>
#include <thread>

namespace chromasunder::jobs {

std::size_t ThreadPool::automatic_worker_count() noexcept {
  const auto available = std::thread::hardware_concurrency();
  if (available <= 2) return 1;
  return static_cast<std::size_t>(available - 1);
}

ThreadPool::ThreadPool(std::size_t worker_count, std::size_t worker_cap) {
  worker_count = std::max<std::size_t>(1, worker_count);
  if (worker_cap != 0) worker_count = std::min(worker_count, worker_cap);
  workers_.reserve(worker_count);
  try {
    for (std::size_t index = 0; index < worker_count; ++index) {
      workers_.emplace_back([this] { worker_loop(); });
    }
  } catch (...) {
    {
      std::lock_guard lock(mutex_);
      stopping_ = true;
    }
    ready_.notify_all();
    for (auto& worker : workers_) worker.join();
    throw;
  }
}

ThreadPool::~ThreadPool() {
  {
    std::lock_guard lock(mutex_);
    stopping_ = true;
  }
  ready_.notify_all();
  for (auto& worker : workers_) worker.join();
}

void ThreadPool::parallel_for(std::size_t count,
                              const std::function<void(std::size_t)>& operation) {
  if (count == 0) return;
  struct Batch {
    explicit Batch(std::function<void(std::size_t)> value) : operation(std::move(value)) {}
    std::function<void(std::size_t)> operation;
    std::atomic_size_t next{0};
    std::size_t count{0};
    std::size_t remaining_workers{0};
    std::exception_ptr first_error;
    std::mutex mutex;
    std::condition_variable completion;
  };
  auto batch = std::make_shared<Batch>(operation);
  batch->count = count;
  const auto task_count = std::min(count, workers_.size());
  batch->remaining_workers = task_count;
  std::vector<std::function<void()>> batch_tasks;
  batch_tasks.reserve(task_count);
  for (std::size_t task = 0; task < task_count; ++task) {
    batch_tasks.emplace_back([batch] {
      while (true) {
        const auto index = batch->next.fetch_add(1, std::memory_order_relaxed);
        if (index >= batch->count) break;
        try {
          batch->operation(index);
        } catch (...) {
          std::lock_guard lock(batch->mutex);
          if (!batch->first_error) batch->first_error = std::current_exception();
        }
      }
      std::lock_guard lock(batch->mutex);
      --batch->remaining_workers;
      if (batch->remaining_workers == 0) batch->completion.notify_one();
    });
  }
  std::size_t enqueued = 0;
  std::exception_ptr enqueue_error;
  {
    std::lock_guard lock(mutex_);
    try {
      for (auto& task : batch_tasks) {
        tasks_.push_back(std::move(task));
        ++enqueued;
      }
    } catch (...) {
      enqueue_error = std::current_exception();
      std::lock_guard batch_lock(batch->mutex);
      batch->remaining_workers = enqueued;
    }
  }
  ready_.notify_all();
  if (enqueued != 0) {
    std::unique_lock completion_lock(batch->mutex);
    batch->completion.wait(completion_lock, [&] { return batch->remaining_workers == 0; });
  }
  if (enqueue_error) std::rethrow_exception(enqueue_error);
  if (batch->first_error) std::rethrow_exception(batch->first_error);
}

void ThreadPool::worker_loop() {
  while (true) {
    std::function<void()> task;
    {
      std::unique_lock lock(mutex_);
      ready_.wait(lock, [&] { return stopping_ || !tasks_.empty(); });
      if (stopping_ && tasks_.empty()) return;
      task = std::move(tasks_.front());
      tasks_.pop_front();
    }
    task();
  }
}

}  // namespace chromasunder::jobs
