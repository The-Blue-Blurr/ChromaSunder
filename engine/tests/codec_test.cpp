#include "chromasunder/codec/image_codec.hpp"
#include "chromasunder/codec/image_io.hpp"
#include "chromasunder/codec/orientation.hpp"
#include "chromasunder/color/color_management.hpp"
#include "chromasunder/image/image_buffer.hpp"

#include <lcms2.h>
#include <png.h>

#include <algorithm>
#include <array>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <span>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

namespace {

using chromasunder::ErrorCode;
using chromasunder::codec::DecodedImage;
using chromasunder::codec::ImageFileFormat;
using chromasunder::codec::JpegCodec;
using chromasunder::codec::PngCodec;
using chromasunder::image::AnyImage;
using chromasunder::image::ImageBuffer;
using chromasunder::image::RgbaPixel;

int failures = 0;
int png_tests = 0;
int jpeg_tests = 0;
int exif_tests = 0;
int icc_tests = 0;

void expect(bool condition, std::string_view message) {
  if (!condition) {
    std::cerr << "FAIL: " << message << '\n';
    ++failures;
  }
}

template <typename T>
ImageBuffer<T> make_image(std::size_t width, std::size_t height,
                          std::vector<RgbaPixel<T>> pixels) {
  auto [image, error] = ImageBuffer<T>::create(width, height);
  expect(!error, "test image allocation succeeds");
  std::copy(pixels.begin(), pixels.end(), image->pixels().begin());
  return std::move(*image);
}

std::vector<std::uint8_t> read_file(const std::filesystem::path& path) {
  std::ifstream stream(path, std::ios::binary);
  return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}

void write_png_fixture(const std::filesystem::path& path, int color_type, int bit_depth,
                       std::size_t width, std::size_t height, void* pixels,
                       std::size_t row_bytes,
                       std::span<const std::uint8_t> profile = {}) {
  FILE* file = std::fopen(path.c_str(), "wb");
  expect(file != nullptr, "fixture PNG opens");
  png_structp png = png_create_write_struct(PNG_LIBPNG_VER_STRING, nullptr, nullptr, nullptr);
  png_infop info = png_create_info_struct(png);
  if (setjmp(png_jmpbuf(png))) {
    expect(false, "fixture PNG writes");
    png_destroy_write_struct(&png, &info);
    std::fclose(file);
    return;
  }
  png_init_io(png, file);
  png_set_IHDR(png, info, static_cast<png_uint_32>(width), static_cast<png_uint_32>(height),
               bit_depth, color_type, PNG_INTERLACE_NONE, PNG_COMPRESSION_TYPE_DEFAULT,
               PNG_FILTER_TYPE_DEFAULT);
  if (!profile.empty()) {
    png_set_iCCP(png, info, "source", PNG_COMPRESSION_TYPE_BASE, profile.data(),
                 static_cast<png_uint_32>(profile.size()));
  }
  std::vector<png_bytep> rows(height);
  for (std::size_t y = 0; y < height; ++y)
    rows[y] = static_cast<png_bytep>(pixels) + y * row_bytes;
  png_set_rows(png, info, rows.data());
  const auto transform = bit_depth == 16 && std::endian::native == std::endian::little
                             ? PNG_TRANSFORM_SWAP_ENDIAN
                             : PNG_TRANSFORM_IDENTITY;
  png_write_png(png, info, transform, nullptr);
  png_destroy_write_struct(&png, &info);
  std::fclose(file);
}

std::vector<std::uint8_t> exif_segment(std::uint16_t orientation) {
  std::vector<std::uint8_t> payload{
      'E', 'x', 'i', 'f', 0, 0, 'I', 'I', 42, 0, 8, 0, 0, 0,
      1, 0, 0x12, 0x01, 3, 0, 1, 0, 0, 0,
      static_cast<std::uint8_t>(orientation), 0, 0, 0, 0, 0, 0, 0};
  const auto length = static_cast<std::uint16_t>(payload.size() + 2);
  std::vector<std::uint8_t> segment{0xFF, 0xE1, static_cast<std::uint8_t>(length >> 8U),
                                    static_cast<std::uint8_t>(length)};
  segment.insert(segment.end(), payload.begin(), payload.end());
  return segment;
}

std::vector<std::uint8_t> with_orientation(const std::vector<std::uint8_t>& jpeg,
                                           std::uint16_t orientation) {
  auto marker = exif_segment(orientation);
  std::vector<std::uint8_t> result;
  result.reserve(jpeg.size() + marker.size());
  result.insert(result.end(), jpeg.begin(), jpeg.begin() + 2);
  result.insert(result.end(), marker.begin(), marker.end());
  result.insert(result.end(), jpeg.begin() + 2, jpeg.end());
  return result;
}

std::vector<std::uint8_t> with_incomplete_icc(const std::vector<std::uint8_t>& jpeg) {
  constexpr std::array<std::uint8_t, 18> marker{
      0xFF, 0xE2, 0, 16, 'I', 'C', 'C', '_', 'P', 'R', 'O', 'F', 'I', 'L', 'E', 0, 1, 2};
  std::vector<std::uint8_t> result;
  result.insert(result.end(), jpeg.begin(), jpeg.begin() + 2);
  result.insert(result.end(), marker.begin(), marker.end());
  result.insert(result.end(), jpeg.begin() + 2, jpeg.end());
  return result;
}

std::vector<std::uint8_t> linear_rgb_profile() {
  cmsCIExyY white{};
  cmsWhitePointFromTemp(&white, 6504);
  cmsCIExyYTRIPLE primaries{{0.64, 0.33, 1}, {0.30, 0.60, 1}, {0.15, 0.06, 1}};
  cmsToneCurve* curves[3]{cmsBuildGamma(nullptr, 1.0), cmsBuildGamma(nullptr, 1.0),
                          cmsBuildGamma(nullptr, 1.0)};
  cmsHPROFILE profile = cmsCreateRGBProfile(&white, &primaries, curves);
  for (auto* curve : curves) cmsFreeToneCurve(curve);
  cmsUInt32Number size = 0;
  cmsSaveProfileToMem(profile, nullptr, &size);
  std::vector<std::uint8_t> bytes(size);
  cmsSaveProfileToMem(profile, bytes.data(), &size);
  cmsCloseProfile(profile);
  return bytes;
}

std::vector<std::uint8_t> linear_gray_profile() {
  cmsCIExyY white{};
  cmsWhitePointFromTemp(&white, 6504);
  cmsToneCurve* curve = cmsBuildGamma(nullptr, 1.0);
  cmsHPROFILE profile = cmsCreateGrayProfile(&white, curve);
  cmsFreeToneCurve(curve);
  cmsUInt32Number size = 0;
  cmsSaveProfileToMem(profile, nullptr, &size);
  std::vector<std::uint8_t> bytes(size);
  cmsSaveProfileToMem(profile, bytes.data(), &size);
  cmsCloseProfile(profile);
  return bytes;
}

void test_png(const std::filesystem::path& directory) {
  const std::array<std::uint8_t, 6> rgb8{1, 2, 3, 250, 128, 64};
  const std::array<std::uint8_t, 2> gray8{0, 128};
  const std::array<std::uint16_t, 6> rgb16{1, 256, 65535, 32767, 32768, 65534};
  const std::array<std::uint16_t, 2> gray16{255, 32768};
  write_png_fixture(directory / "rgb8.png", PNG_COLOR_TYPE_RGB, 8, 2, 1,
                    const_cast<std::uint8_t*>(rgb8.data()), 6);
  write_png_fixture(directory / "gray8.png", PNG_COLOR_TYPE_GRAY, 8, 2, 1,
                    const_cast<std::uint8_t*>(gray8.data()), 2);
  write_png_fixture(directory / "rgb16.png", PNG_COLOR_TYPE_RGB, 16, 2, 1,
                    const_cast<std::uint16_t*>(rgb16.data()), 12);
  write_png_fixture(directory / "gray16.png", PNG_COLOR_TYPE_GRAY, 16, 2, 1,
                    const_cast<std::uint16_t*>(gray16.data()), 4);
  for (const auto& name : {"rgb8.png", "gray8.png", "rgb16.png", "gray16.png"}) {
    auto decoded = chromasunder::codec::decode_image_file(directory / name);
    expect(!decoded.error && decoded.image.has_value(), "PNG color type decodes");
    ++png_tests;
  }
  auto decoded_rgb16 = chromasunder::codec::decode_image_file(directory / "rgb16.png");
  const auto& rgb16_image = std::get<ImageBuffer<std::uint16_t>>(decoded_rgb16.image->pixels);
  expect(rgb16_image.pixels()[0] == RgbaPixel<std::uint16_t>{1, 256, 65535, 65535} &&
             rgb16_image.pixels()[1] == RgbaPixel<std::uint16_t>{32767, 32768, 65534, 65535},
         "PNG16 channel values and host byte order are exact");
  ++png_tests;

  auto rgba8 = make_image<std::uint8_t>(2, 1, {{1, 2, 3, 4}, {250, 128, 64, 32}});
  auto rgba16 = make_image<std::uint16_t>(
      2, 1, {{1, 256, 257, 65535}, {32767, 32768, 65534, 12345}});
  {
    std::ofstream existing(directory / "rgba8.png", std::ios::binary);
    existing << "existing destination";
  }
  expect(!chromasunder::codec::encode_image_atomic(AnyImage{rgba8}, directory / "rgba8.png",
                                                   ImageFileFormat::png),
         "PNG8 atomic encode succeeds");
  expect(!chromasunder::codec::encode_image_atomic(AnyImage{rgba16}, directory / "rgba16.png",
                                                   ImageFileFormat::png),
         "PNG16 atomic encode succeeds");
  auto round8 = chromasunder::codec::decode_image_file(directory / "rgba8.png");
  auto round16 = chromasunder::codec::decode_image_file(directory / "rgba16.png");
  expect(std::equal(std::get<ImageBuffer<std::uint8_t>>(round8.image->pixels).pixels().begin(),
                    std::get<ImageBuffer<std::uint8_t>>(round8.image->pixels).pixels().end(),
                    rgba8.pixels().begin()),
         "tagged sRGB PNG8 round trip is exact");
  expect(std::equal(std::get<ImageBuffer<std::uint16_t>>(round16.image->pixels).pixels().begin(),
                    std::get<ImageBuffer<std::uint16_t>>(round16.image->pixels).pixels().end(),
                    rgba16.pixels().begin()),
         "tagged sRGB PNG16 round trip preserves non-U8 precision exactly");
  png_tests += 4;

  auto truncated = read_file(directory / "rgba8.png");
  truncated.resize(16);
  expect(PngCodec{}.decode(truncated).error.code == ErrorCode::decode_failed,
         "truncated PNG fails cleanly");
  ++png_tests;

  auto auxiliary = make_image<std::uint8_t>(2, 1, {{127, 127, 127, 255}, {128, 128, 128, 255}});
  expect(!chromasunder::codec::encode_image_atomic(AnyImage{auxiliary}, directory / "aux.png",
                                                   ImageFileFormat::png),
         "auxiliary fixture writes");
  auto binary = chromasunder::codec::load_auxiliary_image(directory / "aux.png", 2, 1);
  expect(!binary.error && !binary.image->at(0, 0) && binary.image->at(1, 0),
         "auxiliary U8 threshold is exactly >=128");
  expect(chromasunder::codec::load_auxiliary_image(directory / "aux.png", 1, 2).error.code ==
             ErrorCode::dimension_mismatch,
         "auxiliary canonical dimensions are exact");
  png_tests += 3;
}

void test_jpeg_and_exif(const std::filesystem::path& directory) {
  auto source = make_image<std::uint8_t>(
      3, 2, {{255, 0, 0, 255}, {0, 255, 0, 255}, {0, 0, 255, 255},
             {255, 255, 0, 255}, {0, 255, 255, 255}, {255, 0, 255, 255}});
  const auto source_before = std::vector(source.pixels().begin(), source.pixels().end());
  expect(!chromasunder::codec::encode_image_atomic(AnyImage{source}, directory / "quality1.jpg",
                                                   ImageFileFormat::jpeg, {1}),
         "JPEG quality 1 encodes");
  expect(!chromasunder::codec::encode_image_atomic(AnyImage{source}, directory / "quality100.jpg",
                                                   ImageFileFormat::jpeg, {100}),
         "JPEG quality 100 encodes");
  expect(JpegCodec{}.encode(AnyImage{source}, directory / "invalid.jpg", {0}).code ==
             ErrorCode::invalid_settings,
         "JPEG quality 0 is rejected");
  auto baseline = chromasunder::codec::decode_image_file(directory / "quality100.jpg");
  expect(!baseline.error &&
             std::get<ImageBuffer<std::uint8_t>>(baseline.image->pixels).width() == 3 &&
             baseline.image->working_profile.source_was_tagged,
         "JPEG decodes to RGBA8");
  jpeg_tests += 4;

  const auto jpeg_bytes = read_file(directory / "quality100.jpg");
  const auto& baseline_image = std::get<ImageBuffer<std::uint8_t>>(baseline.image->pixels);
  const std::array<std::array<std::size_t, 6>, 8> expected_indices{{
      {0, 1, 2, 3, 4, 5}, {2, 1, 0, 5, 4, 3}, {5, 4, 3, 2, 1, 0},
      {3, 4, 5, 0, 1, 2}, {0, 3, 1, 4, 2, 5}, {3, 0, 4, 1, 5, 2},
      {5, 2, 4, 1, 3, 0}, {2, 5, 1, 4, 0, 3}}};
  for (std::uint16_t orientation = 1; orientation <= 8; ++orientation) {
    auto decoded = JpegCodec{}.decode(with_orientation(jpeg_bytes, orientation));
    const auto& actual = std::get<ImageBuffer<std::uint8_t>>(decoded.image->pixels);
    std::vector<RgbaPixel<std::uint8_t>> expected;
    for (const auto index : expected_indices[orientation - 1])
      expected.push_back(baseline_image.pixels()[index]);
    expect(!decoded.error && decoded.image->applied_orientation == orientation &&
               actual.width() == (orientation >= 5 ? 2U : 3U) &&
               actual.height() == (orientation >= 5 ? 3U : 2U) &&
               std::equal(actual.pixels().begin(), actual.pixels().end(), expected.begin()),
           "JPEG EXIF orientation produces canonical upright pixels");
    ++exif_tests;
  }

  auto alpha8 = make_image<std::uint8_t>(2, 1, {{200, 100, 50, 0}, {200, 100, 50, 128}});
  const auto scratch8 = chromasunder::codec::jpeg_rgb8_scratch(AnyImage{alpha8});
  expect(scratch8[0] == 0 && scratch8[1] == 0 && scratch8[2] == 0 && scratch8[3] == 100 &&
             scratch8[4] == 50 && scratch8[5] == 25,
         "JPEG export flattens U8 alpha onto black with rounding");
  auto alpha16 = make_image<std::uint16_t>(1, 1, {{65535, 32768, 1, 32768}});
  const auto alpha16_before = std::vector(alpha16.pixels().begin(), alpha16.pixels().end());
  const auto scratch16 = chromasunder::codec::jpeg_rgb8_scratch(AnyImage{alpha16});
  expect(scratch16[0] == 128 && scratch16[1] == 64 && scratch16[2] == 0,
         "U16 JPEG scratch uses high precision before deliberate U8 quantization");
  expect(std::equal(alpha16.pixels().begin(), alpha16.pixels().end(), alpha16_before.begin()) &&
             std::equal(source.pixels().begin(), source.pixels().end(), source_before.begin()),
         "JPEG conversion does not mutate U8 or U16 native renders");
  jpeg_tests += 3;

  const std::array<std::uint8_t, 26> big_endian_exif{
      'M', 'M', 0, 42, 0, 0, 0, 8, 0, 1, 0x01, 0x12, 0, 3, 0, 0, 0, 1,
      0, 8, 0, 0, 0, 0, 0, 0};
  expect(chromasunder::codec::parse_exif_orientation(big_endian_exif) == 8,
         "big-endian EXIF orientation parses safely");
  ++exif_tests;

  expect(JpegCodec{}.decode(std::span<const std::uint8_t>(jpeg_bytes).first(20)).error.code ==
             ErrorCode::decode_failed,
         "truncated JPEG fails cleanly");
  expect(JpegCodec{}.decode(with_incomplete_icc(jpeg_bytes)).error.code ==
             ErrorCode::color_transform_failed,
         "incomplete JPEG ICC marker sequence fails cleanly");
  jpeg_tests += 2;
}

void test_icc(const std::filesystem::path& directory) {
  const auto profile = linear_rgb_profile();
  auto image8 = make_image<std::uint8_t>(1, 1, {{128, 64, 32, 77}});
  auto image16 = make_image<std::uint16_t>(1, 1, {{32768, 16384, 8192, 43210}});
  const auto original8 = image8.pixels()[0];
  const auto original16 = image16.pixels()[0];
  expect(!chromasunder::color::convert_to_srgb(image8, profile) &&
             image8.pixels()[0].a == original8.a && image8.pixels()[0].r != original8.r,
         "ICC conversion transforms U8 RGB and copies alpha");
  expect(!chromasunder::color::convert_to_srgb(image16, profile) &&
             image16.pixels()[0].a == original16.a && image16.pixels()[0].r != original16.r,
         "ICC conversion transforms U16 RGB at U16 precision and copies alpha");
  expect(!chromasunder::color::convert_to_srgb(image8, {}),
         "untagged input is explicitly treated as sRGB without mutation");
  const std::array<std::uint8_t, 3> rgb8{128, 64, 32};
  const std::array<std::uint16_t, 3> rgb16{32768, 16384, 8192};
  write_png_fixture(directory / "profile8.png", PNG_COLOR_TYPE_RGB, 8, 1, 1,
                    const_cast<std::uint8_t*>(rgb8.data()), 3, profile);
  write_png_fixture(directory / "profile16.png", PNG_COLOR_TYPE_RGB, 16, 1, 1,
                    const_cast<std::uint16_t*>(rgb16.data()), 6, profile);
  auto decoded8 = chromasunder::codec::decode_image_file(directory / "profile8.png");
  auto decoded16 = chromasunder::codec::decode_image_file(directory / "profile16.png");
  expect(!decoded8.error && decoded8.image->working_profile.source_was_tagged &&
             std::get<ImageBuffer<std::uint8_t>>(decoded8.image->pixels).pixels()[0].r != rgb8[0],
         "profiled PNG8 import converts into sRGB");
  expect(!decoded16.error && decoded16.image->working_profile.source_was_tagged &&
             std::get<ImageBuffer<std::uint16_t>>(decoded16.image->pixels).pixels()[0].r !=
                 rgb16[0],
         "profiled PNG16 import converts into sRGB without reducing depth");
  const auto gray_profile = linear_gray_profile();
  const std::array<std::uint8_t, 1> gray8{128};
  const std::array<std::uint16_t, 1> gray16{32768};
  write_png_fixture(directory / "gray-profile8.png", PNG_COLOR_TYPE_GRAY, 8, 1, 1,
                    const_cast<std::uint8_t*>(gray8.data()), 1, gray_profile);
  write_png_fixture(directory / "gray-profile16.png", PNG_COLOR_TYPE_GRAY, 16, 1, 1,
                    const_cast<std::uint16_t*>(gray16.data()), 2, gray_profile);
  auto decoded_gray8 = chromasunder::codec::decode_image_file(directory / "gray-profile8.png");
  auto decoded_gray16 = chromasunder::codec::decode_image_file(directory / "gray-profile16.png");
  expect(!decoded_gray8.error &&
             std::holds_alternative<ImageBuffer<std::uint8_t>>(decoded_gray8.image->pixels),
         "grayscale-profiled PNG8 converts to canonical sRGB RGBA8");
  expect(!decoded_gray16.error &&
             std::holds_alternative<ImageBuffer<std::uint16_t>>(decoded_gray16.image->pixels),
         "grayscale-profiled PNG16 converts to canonical sRGB RGBA16");
  icc_tests += 7;
}

}  // namespace

int main() {
  const auto directory = std::filesystem::temp_directory_path() / "chromasunder-codec-tests";
  std::error_code error;
  std::filesystem::create_directories(directory, error);
  expect(!error, "codec test directory exists");
  test_png(directory);
  test_jpeg_and_exif(directory);
  test_icc(directory);
  std::filesystem::remove_all(directory, error);
  std::cout << "png_tests=" << png_tests << " jpeg_tests=" << jpeg_tests
            << " exif_tests=" << exif_tests << " icc_tests=" << icc_tests << '\n';
  if (failures != 0) {
    std::cerr << failures << " codec assertion(s) failed\n";
    return 1;
  }
  return 0;
}
