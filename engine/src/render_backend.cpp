#include "chromasunder/processing/render_backend.hpp"

#include "chromasunder/processing/pixel_sort_stage.hpp"

#include <cstdint>
#include <new>
#include <stdexcept>
#include <type_traits>
#include <utility>
#include <variant>

namespace chromasunder::processing {

RenderOutcome CpuRenderBackend::render(const RenderRequest& request,
                                       const jobs::CancellationToken& cancellation,
                                       jobs::ProgressState& progress) {
  RenderOutcome outcome;
  outcome.error = std::visit(
      [&](const auto& source) {
        memory::RenderMemoryInputs inputs{
            source.width(), source.height(), source.format(), request.previous_completed_bytes,
            request.mask != nullptr, request.interval_image != nullptr, pool_.worker_count(),
            request.codec_allowance_bytes, request.safety_margin_bytes};
        if (auto error = memory::estimate_render_memory(inputs, outcome.memory_estimate)) return error;
        if (auto error = request.memory_budget.check(outcome.memory_estimate)) return error;
        if (cancellation.is_cancelled()) return Error{ErrorCode::cancelled, "Render cancelled."};

        using Buffer = std::remove_cvref_t<decltype(source)>;
        using Channel = std::conditional_t<
            std::same_as<Buffer, image::ImageBuffer<std::uint8_t>>, std::uint8_t, std::uint16_t>;
        auto [candidate, allocation_error] =
            image::ImageBuffer<Channel>::create(source.width(), source.height());
        if (allocation_error) return allocation_error;
        PixelSortStage<Channel> stage;
        if (auto error = stage.process(source.view(), candidate->mutable_view(), request.settings,
                                       request.mask, request.interval_image, pool_, cancellation,
                                       progress))
          return error;
        outcome.image = AnyImage{std::move(*candidate)};
        return Error{};
      },
      request.source);
  return outcome;
}

Error FullRenderStore::render_and_promote(RenderBackend& backend, const RenderRequest& request,
                                          const jobs::CancellationToken& cancellation,
                                          jobs::ProgressState& progress) {
  std::lock_guard lock(mutex_);
  RenderRequest transactional_request = request;
  if (last_completed_) {
    transactional_request.previous_completed_bytes = std::visit(
        [](const auto& image) { return image.size_bytes(); }, *last_completed_);
  }
  auto outcome = backend.render(transactional_request, cancellation, progress);
  if (!outcome.succeeded())
    return outcome.error ? outcome.error
                         : Error{ErrorCode::allocation_failed,
                                 "Render backend returned no completed candidate."};
  last_completed_ = std::make_shared<const AnyImage>(std::move(*outcome.image));
  return {};
}

}  // namespace chromasunder::processing
