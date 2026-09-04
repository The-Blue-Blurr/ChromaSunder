#pragma once

#include "chromasunder/error.hpp"
#include "chromasunder/image/image_view.hpp"
#include "chromasunder/jobs/cancellation.hpp"
#include "chromasunder/jobs/progress.hpp"
#include "chromasunder/jobs/thread_pool.hpp"
#include "chromasunder/processing/intervals.hpp"
#include "chromasunder/processing/mask.hpp"
#include "chromasunder/processing/path.hpp"
#include "chromasunder/processing/settings.hpp"
#include "chromasunder/processing/sorting.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <span>
#include <limits>
#include <vector>

namespace chromasunder::processing {

template <image::ChannelType Channel>
class ProcessingStage {
 public:
  virtual ~ProcessingStage() = default;
  [[nodiscard]] virtual Error process(image::ImageView<Channel> source,
                                      image::MutableImageView<Channel> output,
                                      const PixelSortSettings& settings,
                                      const BinaryImage* mask,
                                      const BinaryImage* interval_image,
                                      jobs::ThreadPool& pool,
                                      const jobs::CancellationToken& cancellation,
                                      jobs::ProgressState& progress) const = 0;
};

template <image::ChannelType Channel>
class PixelSortStage final : public ProcessingStage<Channel> {
 public:
  [[nodiscard]] Error process(image::ImageView<Channel> source,
                              image::MutableImageView<Channel> output,
                              const PixelSortSettings& settings, const BinaryImage* mask,
                              const BinaryImage* interval_image, jobs::ThreadPool& pool,
                              const jobs::CancellationToken& cancellation,
                              jobs::ProgressState& progress) const override {
    if (source.width() != output.width() || source.height() != output.height()) {
      return {ErrorCode::dimension_mismatch, "Source and output dimensions differ."};
    }
    if (const auto error = validate_settings(settings, interval_image != nullptr)) return error;
    if (mask) {
      if (const auto error = validate_auxiliary_dimensions(*mask, source.width(), source.height()))
        return error;
    }
    if (interval_image) {
      if (const auto error =
              validate_auxiliary_dimensions(*interval_image, source.width(), source.height()))
        return error;
    }

    progress.reset(jobs::RenderStage::preparing_image, source.width() * source.height());
    for (std::size_t y = 0; y < source.height(); ++y) {
      std::copy(source.row(y).begin(), source.row(y).end(), output.row(y).begin());
    }
    if (cancellation.is_cancelled()) return {ErrorCode::cancelled, "Render cancelled."};

    progress.reset(jobs::RenderStage::generating_paths, source.width() * source.height());
    StraightDirectionalPathProvider paths(source.width(), source.height(), settings.angle_degrees);
    progress.complete(jobs::RenderStage::sorting);
    progress.reset(jobs::RenderStage::sorting, source.width() * source.height());

    pool.parallel_for(paths.path_count(), [&](std::size_t path_index) {
      const auto& path = paths.path(path_index);
      if (cancellation.is_cancelled()) return;
      std::vector<image::RgbaPixel<Channel>> path_pixels;
      std::vector<std::uint8_t> mask_bits;
      std::vector<std::uint8_t> interval_bits;
      path_pixels.reserve(path.size());
      if (mask) mask_bits.reserve(path.size());
      if (interval_image) interval_bits.reserve(path.size());
      for (std::size_t index = 0; index < path.size(); ++index) {
        const auto coordinate = path.position(index);
        path_pixels.push_back(source.at(coordinate.x, coordinate.y));
        if (mask) mask_bits.push_back(mask->at(coordinate.x, coordinate.y));
        if (interval_image)
          interval_bits.push_back(interval_image->at(coordinate.x, coordinate.y));
      }
      SplitMix64 rng(derive_path_seed(settings.seed, path.stable_id()));
      const auto intervals = detect_intervals<Channel>(
          path_pixels, settings.interval_mode, settings.lower_threshold,
          settings.upper_threshold, settings.characteristic_length, rng, interval_bits);
      for (const auto interval : intervals) {
        if (cancellation.is_cancelled()) return;
        if (rng.percentage(settings.randomness_percentage)) continue;
        std::vector<std::size_t> positions;
        std::vector<image::RgbaPixel<Channel>> sortable;
        positions.reserve(interval.end - interval.start);
        sortable.reserve(interval.end - interval.start);
        for (auto index = interval.start; index < interval.end; ++index) {
          if (mask && mask_bits[index] == 0) continue;
          positions.push_back(index);
          sortable.push_back(path_pixels[index]);
        }
        if (positions.size() < 2) continue;
        stable_sort_pixels(sortable, settings.sorting_mode);
        for (std::size_t index = 0; index < positions.size(); ++index) {
          const auto coordinate = path.position(positions[index]);
          output.at(coordinate.x, coordinate.y) = sortable[index];
        }
      }
      progress.add_completed(path.size());
    });
    if (cancellation.is_cancelled()) return {ErrorCode::cancelled, "Render cancelled."};
    progress.complete();
    return {};
  }
};

}  // namespace chromasunder::processing
