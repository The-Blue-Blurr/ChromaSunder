#include "chromasunder/color/color_management.hpp"

#include <lcms2.h>

#include <algorithm>
#include <cstdint>
#include <limits>
#include <new>
#include <span>
#include <vector>

namespace chromasunder::color {

ProfileColorSpace inspect_profile(std::span<const std::uint8_t> source_profile) noexcept {
  if (source_profile.empty()) return ProfileColorSpace::untagged;
  if (source_profile.size() > std::numeric_limits<cmsUInt32Number>::max())
    return ProfileColorSpace::invalid;
  cmsHPROFILE profile = cmsOpenProfileFromMem(source_profile.data(),
                                             static_cast<cmsUInt32Number>(source_profile.size()));
  if (!profile) return ProfileColorSpace::invalid;
  const auto signature = cmsGetColorSpace(profile);
  cmsCloseProfile(profile);
  if (signature == cmsSigRgbData) return ProfileColorSpace::rgb;
  if (signature == cmsSigGrayData) return ProfileColorSpace::gray;
  if (signature == cmsSigCmykData) return ProfileColorSpace::cmyk;
  return ProfileColorSpace::unsupported;
}
std::vector<std::uint8_t> srgb_profile_bytes() {
  cmsHPROFILE profile = cmsCreate_sRGBProfile();
  if (!profile) return {};
  cmsUInt32Number size = 0;
  cmsSaveProfileToMem(profile, nullptr, &size);
  std::vector<std::uint8_t> bytes(size);
  if (!cmsSaveProfileToMem(profile, bytes.data(), &size)) bytes.clear();
  cmsCloseProfile(profile);
  return bytes;
}

template <image::ChannelType Channel>
Error convert_to_srgb(image::ImageBuffer<Channel>& image,
                      std::span<const std::uint8_t> source_profile) {
  if (source_profile.empty()) return {};
  if (source_profile.size() > std::numeric_limits<cmsUInt32Number>::max()) {
    return {ErrorCode::color_transform_failed, "ICC profile is too large."};
  }
  cmsHPROFILE source = cmsOpenProfileFromMem(source_profile.data(),
                                             static_cast<cmsUInt32Number>(source_profile.size()));
  cmsHPROFILE destination = cmsCreate_sRGBProfile();
  if (!source || !destination) {
    if (source) cmsCloseProfile(source);
    if (destination) cmsCloseProfile(destination);
    return {ErrorCode::color_transform_failed, "Could not open the ICC color profile."};
  }
  const auto color_space = cmsGetColorSpace(source);
  if (color_space != cmsSigRgbData && color_space != cmsSigGrayData) {
    cmsCloseProfile(source);
    cmsCloseProfile(destination);
    return {ErrorCode::color_transform_failed,
            "Only RGB ICC profiles are supported for canonical RGBA input."};
  }
  constexpr auto rgba_format = sizeof(Channel) == 1 ? TYPE_RGBA_8 : TYPE_RGBA_16;
  const auto source_format = color_space == cmsSigGrayData
                                 ? (sizeof(Channel) == 1 ? TYPE_GRAYA_8 : TYPE_GRAYA_16)
                                 : rgba_format;
  cmsHTRANSFORM transform = cmsCreateTransform(source, source_format, destination, rgba_format,
                                               INTENT_RELATIVE_COLORIMETRIC,
                                               cmsFLAGS_COPY_ALPHA | cmsFLAGS_BLACKPOINTCOMPENSATION);
  if (!transform) {
    cmsCloseProfile(source);
    cmsCloseProfile(destination);
    return {ErrorCode::color_transform_failed, "Could not create the sRGB transform."};
  }
  if (color_space == cmsSigGrayData) {
    struct GrayAlpha {
      Channel gray;
      Channel alpha;
    };
    std::vector<GrayAlpha> gray;
    try {
      gray.reserve(image.pixels().size());
      for (const auto& pixel : image.pixels()) gray.push_back({pixel.r, pixel.a});
    } catch (const std::bad_alloc&) {
      cmsDeleteTransform(transform);
      cmsCloseProfile(source);
      cmsCloseProfile(destination);
      return {ErrorCode::allocation_failed, "Grayscale ICC scratch allocation failed."};
    }
    std::size_t offset = 0;
    while (offset < gray.size()) {
      const auto count = std::min<std::size_t>(gray.size() - offset,
                                               std::numeric_limits<cmsUInt32Number>::max());
      cmsDoTransform(transform, gray.data() + offset, image.pixels().data() + offset,
                     static_cast<cmsUInt32Number>(count));
      offset += count;
    }
  } else {
    std::size_t offset = 0;
    while (offset < image.pixels().size()) {
      const auto count = std::min<std::size_t>(image.pixels().size() - offset,
                                               std::numeric_limits<cmsUInt32Number>::max());
      cmsDoTransform(transform, image.pixels().data() + offset, image.pixels().data() + offset,
                     static_cast<cmsUInt32Number>(count));
      offset += count;
    }
  }
  cmsDeleteTransform(transform);
  cmsCloseProfile(source);
  cmsCloseProfile(destination);
  return {};
}

Cmyk8Result convert_cmyk8_to_srgb(std::span<const std::uint8_t> cmyk, std::size_t width,
                                  std::size_t height,
                                  std::span<const std::uint8_t> source_profile) {
  if (width != 0 && height > std::numeric_limits<std::size_t>::max() / width) {
    return {{}, {ErrorCode::size_overflow, "CMYK image dimensions overflow."}};
  }
  const auto pixels = width * height;
  if (pixels > std::numeric_limits<std::size_t>::max() / 4 || cmyk.size() != pixels * 4) {
    return {{}, {ErrorCode::decode_failed, "CMYK storage does not match image dimensions."}};
  }
  if (inspect_profile(source_profile) != ProfileColorSpace::cmyk) {
    return {{}, {ErrorCode::color_transform_failed, "A valid CMYK ICC profile is required."}};
  }
  auto [output, allocation_error] = image::ImageBuffer<std::uint8_t>::create(width, height);
  if (allocation_error) return {{}, allocation_error};
  cmsHPROFILE source = cmsOpenProfileFromMem(source_profile.data(),
                                             static_cast<cmsUInt32Number>(source_profile.size()));
  cmsHPROFILE destination = cmsCreate_sRGBProfile();
  cmsHTRANSFORM transform = source && destination
                                ? cmsCreateTransform(source, TYPE_CMYK_8, destination, TYPE_RGB_8,
                                                     INTENT_RELATIVE_COLORIMETRIC,
                                                     cmsFLAGS_BLACKPOINTCOMPENSATION)
                                : nullptr;
  if (!transform) {
    if (source) cmsCloseProfile(source);
    if (destination) cmsCloseProfile(destination);
    return {{}, {ErrorCode::color_transform_failed, "Could not create CMYK ICC transform."}};
  }
  std::vector<std::uint8_t> rgb;
  try {
    rgb.resize(pixels * 3);
  } catch (const std::bad_alloc&) {
    cmsDeleteTransform(transform);
    cmsCloseProfile(source);
    cmsCloseProfile(destination);
    return {{}, {ErrorCode::allocation_failed, "CMYK transform scratch allocation failed."}};
  }
  std::size_t offset = 0;
  while (offset < pixels) {
    const auto count = std::min<std::size_t>(pixels - offset,
                                             std::numeric_limits<cmsUInt32Number>::max());
    cmsDoTransform(transform, cmyk.data() + offset * 4, rgb.data() + offset * 3,
                   static_cast<cmsUInt32Number>(count));
    offset += count;
  }
  for (std::size_t index = 0; index < pixels; ++index) {
    output->pixels()[index] = {rgb[index * 3], rgb[index * 3 + 1], rgb[index * 3 + 2], 255};
  }
  cmsDeleteTransform(transform);
  cmsCloseProfile(source);
  cmsCloseProfile(destination);
  return {std::move(*output), {}};
}

template Error convert_to_srgb<std::uint8_t>(image::ImageBuffer<std::uint8_t>&,
                                             std::span<const std::uint8_t>);
template Error convert_to_srgb<std::uint16_t>(image::ImageBuffer<std::uint16_t>&,
                                              std::span<const std::uint8_t>);

}  // namespace chromasunder::color
