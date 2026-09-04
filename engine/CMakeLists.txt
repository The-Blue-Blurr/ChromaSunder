cmake_minimum_required(VERSION 3.21)

project(
  ChromaSunderEngine
  VERSION 2.0.0
  DESCRIPTION "Portable native engine for Chroma Sunder"
  LANGUAGES CXX
)

option(CHROMASUNDER_NATIVE_ASSET "Build for Flutter native-assets packaging" OFF)
option(CHROMASUNDER_BUILD_BENCHMARKS "Build the standalone native benchmark harness" ON)
option(CHROMASUNDER_ENABLE_SANITIZERS "Enable AddressSanitizer and UndefinedBehaviorSanitizer" OFF)
option(CHROMASUNDER_ENABLE_TSAN "Enable ThreadSanitizer" OFF)
if(CHROMASUNDER_ENABLE_SANITIZERS AND CHROMASUNDER_ENABLE_TSAN)
  message(FATAL_ERROR "Address/Undefined sanitizers and ThreadSanitizer are separate configurations")
endif()
set(_chromasunder_codec_default ON)
if(CHROMASUNDER_NATIVE_ASSET)
  set(_chromasunder_codec_default OFF)
endif()
option(CHROMASUNDER_ENABLE_CODECS "Build PNG, JPEG, and ICC image I/O" ${_chromasunder_codec_default})

include(CTest)
include(CMakePackageConfigHelpers)
include(GNUInstallDirs)
find_package(Threads REQUIRED)

add_library(
  chromasunder_core STATIC
  src/path.cpp
  src/render_backend.cpp
  src/render_budget.cpp
  src/thread_pool.cpp
)
target_compile_features(chromasunder_core PUBLIC cxx_std_20)
set_target_properties(
  chromasunder_core
  PROPERTIES CXX_EXTENSIONS OFF POSITION_INDEPENDENT_CODE ON
)
target_include_directories(
  chromasunder_core
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)
target_link_libraries(chromasunder_core PUBLIC Threads::Threads)

if(CHROMASUNDER_ENABLE_CODECS)
  find_package(PNG REQUIRED)
  find_package(JPEG REQUIRED)
  find_path(LCMS2_INCLUDE_DIR NAMES lcms2.h REQUIRED)
  find_library(LCMS2_LIBRARY NAMES lcms2 liblcms2 REQUIRED)
  add_library(LCMS2::LCMS2 UNKNOWN IMPORTED)
  set_target_properties(
    LCMS2::LCMS2
    PROPERTIES IMPORTED_LOCATION "${LCMS2_LIBRARY}" INTERFACE_INCLUDE_DIRECTORIES "${LCMS2_INCLUDE_DIR}"
  )
  target_sources(
    chromasunder_core
    PRIVATE
      src/color_management.cpp
      src/image_io.cpp
      src/jpeg_codec.cpp
      src/orientation.cpp
      src/png_codec.cpp
  )
  target_link_libraries(chromasunder_core PRIVATE PNG::PNG JPEG::JPEG LCMS2::LCMS2)
  target_compile_definitions(chromasunder_core PUBLIC CHROMASUNDER_ENABLE_CODECS=1)
endif()

add_library(chromasunder_engine SHARED src/smoke.cpp)
add_library(ChromaSunder::Engine ALIAS chromasunder_engine)

target_compile_features(chromasunder_engine PUBLIC cxx_std_20)
set_target_properties(
  chromasunder_engine
  PROPERTIES
    EXPORT_NAME Engine
    CXX_EXTENSIONS OFF
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN YES
)
if(CHROMASUNDER_NATIVE_ASSET)
  set_target_properties(chromasunder_engine PROPERTIES NO_SONAME YES)
else()
  set_target_properties(
    chromasunder_engine
    PROPERTIES VERSION "${PROJECT_VERSION}" SOVERSION "${PROJECT_VERSION_MAJOR}"
  )
endif()

target_include_directories(
  chromasunder_engine
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)
target_compile_definitions(chromasunder_engine PRIVATE CHROMASUNDER_ENGINE_BUILD)
target_link_libraries(chromasunder_engine PRIVATE chromasunder_core)

if(MSVC)
  target_compile_options(chromasunder_core PRIVATE /W4 /permissive-)
  target_compile_options(chromasunder_engine PRIVATE /W4 /permissive-)
else()
  target_compile_options(chromasunder_core PRIVATE -Wall -Wextra -Wpedantic)
  target_compile_options(chromasunder_engine PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(CHROMASUNDER_ENABLE_SANITIZERS AND NOT MSVC)
  foreach(target chromasunder_core chromasunder_engine)
    target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${target} PRIVATE -fsanitize=address,undefined)
  endforeach()
endif()

if(BUILD_TESTING)
  add_executable(chromasunder_engine_smoke_test tests/smoke_test.cpp)
  target_compile_features(chromasunder_engine_smoke_test PRIVATE cxx_std_20)
  set_target_properties(chromasunder_engine_smoke_test PROPERTIES CXX_EXTENSIONS OFF)
  target_link_libraries(chromasunder_engine_smoke_test PRIVATE ChromaSunder::Engine)
  if(MSVC)
    target_compile_options(chromasunder_engine_smoke_test PRIVATE /W4 /permissive-)
  else()
    target_compile_options(chromasunder_engine_smoke_test PRIVATE -Wall -Wextra -Wpedantic)
  endif()
  add_test(NAME engine_smoke COMMAND chromasunder_engine_smoke_test)
  if(CHROMASUNDER_ENABLE_SANITIZERS AND NOT MSVC)
    target_compile_options(
      chromasunder_engine_smoke_test PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer
    )
    target_link_options(chromasunder_engine_smoke_test PRIVATE -fsanitize=address,undefined)
  endif()

  add_executable(chromasunder_engine_core_test tests/core_test.cpp)
  target_compile_features(chromasunder_engine_core_test PRIVATE cxx_std_20)
  set_target_properties(chromasunder_engine_core_test PROPERTIES CXX_EXTENSIONS OFF)
  target_link_libraries(chromasunder_engine_core_test PRIVATE chromasunder_core)
  if(MSVC)
    target_compile_options(chromasunder_engine_core_test PRIVATE /W4 /permissive-)
  else()
    target_compile_options(chromasunder_engine_core_test PRIVATE -Wall -Wextra -Wpedantic)
  endif()
  if(CHROMASUNDER_ENABLE_SANITIZERS AND NOT MSVC)
    target_compile_options(
      chromasunder_engine_core_test PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer
    )
    target_link_options(chromasunder_engine_core_test PRIVATE -fsanitize=address,undefined)
  endif()
  add_test(NAME engine_core COMMAND chromasunder_engine_core_test)

  add_executable(chromasunder_engine_parity_test tests/parity_test.cpp)
  target_compile_features(chromasunder_engine_parity_test PRIVATE cxx_std_20)
  set_target_properties(chromasunder_engine_parity_test PROPERTIES CXX_EXTENSIONS OFF)
  target_link_libraries(chromasunder_engine_parity_test PRIVATE chromasunder_core)
  target_compile_definitions(
    chromasunder_engine_parity_test
    PRIVATE CHROMASUNDER_TESTDATA_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../testdata"
  )
  if(MSVC)
    target_compile_options(chromasunder_engine_parity_test PRIVATE /W4 /permissive-)
  else()
    target_compile_options(chromasunder_engine_parity_test PRIVATE -Wall -Wextra -Wpedantic)
  endif()
  if(CHROMASUNDER_ENABLE_SANITIZERS AND NOT MSVC)
    target_compile_options(
      chromasunder_engine_parity_test PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer
    )
    target_link_options(chromasunder_engine_parity_test PRIVATE -fsanitize=address,undefined)
  endif()
  add_test(NAME engine_v1_parity COMMAND chromasunder_engine_parity_test)

  if(CHROMASUNDER_ENABLE_CODECS)
    add_executable(chromasunder_engine_codec_test tests/codec_test.cpp)
    target_compile_features(chromasunder_engine_codec_test PRIVATE cxx_std_20)
    set_target_properties(chromasunder_engine_codec_test PROPERTIES CXX_EXTENSIONS OFF)
    target_link_libraries(
      chromasunder_engine_codec_test PRIVATE chromasunder_core PNG::PNG LCMS2::LCMS2
    )
    if(MSVC)
      target_compile_options(chromasunder_engine_codec_test PRIVATE /W4 /permissive-)
    else()
      target_compile_options(chromasunder_engine_codec_test PRIVATE -Wall -Wextra -Wpedantic)
    endif()
    if(CHROMASUNDER_ENABLE_SANITIZERS AND NOT MSVC)
      target_compile_options(
        chromasunder_engine_codec_test PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer
      )
      target_link_options(chromasunder_engine_codec_test PRIVATE -fsanitize=address,undefined)
    endif()
    add_test(NAME engine_codec COMMAND chromasunder_engine_codec_test)
  endif()
endif()

if(CHROMASUNDER_BUILD_BENCHMARKS)
  add_executable(chromasunder_engine_benchmark benchmarks/render_benchmark.cpp)
  target_compile_features(chromasunder_engine_benchmark PRIVATE cxx_std_20)
  set_target_properties(chromasunder_engine_benchmark PROPERTIES CXX_EXTENSIONS OFF)
  target_link_libraries(chromasunder_engine_benchmark PRIVATE chromasunder_core)
  if(MSVC)
    target_compile_options(chromasunder_engine_benchmark PRIVATE /W4 /permissive-)
  else()
    target_compile_options(chromasunder_engine_benchmark PRIVATE -Wall -Wextra -Wpedantic)
  endif()
endif()

if(CHROMASUNDER_ENABLE_TSAN AND NOT MSVC)
  set(_chromasunder_tsan_targets chromasunder_core chromasunder_engine)
  if(BUILD_TESTING)
    list(
      APPEND _chromasunder_tsan_targets
      chromasunder_engine_smoke_test
      chromasunder_engine_core_test
      chromasunder_engine_parity_test
    )
    if(CHROMASUNDER_ENABLE_CODECS)
      list(APPEND _chromasunder_tsan_targets chromasunder_engine_codec_test)
    endif()
  endif()
  if(CHROMASUNDER_BUILD_BENCHMARKS)
    list(APPEND _chromasunder_tsan_targets chromasunder_engine_benchmark)
  endif()
  foreach(target IN LISTS _chromasunder_tsan_targets)
    target_compile_options(${target} PRIVATE -fsanitize=thread -fno-omit-frame-pointer)
    target_link_options(${target} PRIVATE -fsanitize=thread)
  endforeach()
endif()

install(
  TARGETS chromasunder_engine
  EXPORT ChromaSunderEngineTargets
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
  LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
)
install(DIRECTORY include/ DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")
install(
  EXPORT ChromaSunderEngineTargets
  FILE ChromaSunderEngineTargets.cmake
  NAMESPACE ChromaSunder::
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/ChromaSunderEngine"
)
configure_package_config_file(
  cmake/ChromaSunderEngineConfig.cmake.in
  "${CMAKE_CURRENT_BINARY_DIR}/ChromaSunderEngineConfig.cmake"
  INSTALL_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/ChromaSunderEngine"
)
write_basic_package_version_file(
  "${CMAKE_CURRENT_BINARY_DIR}/ChromaSunderEngineConfigVersion.cmake"
  VERSION "${PROJECT_VERSION}"
  COMPATIBILITY SameMajorVersion
)
install(
  FILES
    "${CMAKE_CURRENT_BINARY_DIR}/ChromaSunderEngineConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/ChromaSunderEngineConfigVersion.cmake"
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/ChromaSunderEngine"
)
