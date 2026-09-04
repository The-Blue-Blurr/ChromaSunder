cmake_minimum_required(VERSION 3.21)

project(
  ChromaSunderEngine
  VERSION 2.0.0
  DESCRIPTION "Portable native engine for Chroma Sunder"
  LANGUAGES CXX
)

option(CHROMASUNDER_NATIVE_ASSET "Build for Flutter native-assets packaging" OFF)

include(CTest)
include(CMakePackageConfigHelpers)
include(GNUInstallDirs)

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

if(MSVC)
  target_compile_options(chromasunder_engine PRIVATE /W4 /permissive-)
else()
  target_compile_options(chromasunder_engine PRIVATE -Wall -Wextra -Wpedantic)
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
