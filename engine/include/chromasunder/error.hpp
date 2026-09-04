#pragma once

#include <cstddef>
#include <string>

namespace chromasunder {

enum class ErrorCode {
  none,
  invalid_settings,
  missing_interval_image,
  dimension_mismatch,
  size_overflow,
  allocation_failed,
  insufficient_memory_budget,
  cancelled,
  decode_failed,
  encode_failed,
  unsupported_format,
  color_transform_failed,
  io_failed,
};

struct Error {
  ErrorCode code{ErrorCode::none};
  std::string message;
  std::size_t estimated_bytes{0};
  std::size_t allowed_bytes{0};

  [[nodiscard]] explicit operator bool() const noexcept { return code != ErrorCode::none; }
};

}  // namespace chromasunder
