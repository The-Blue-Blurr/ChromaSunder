#ifndef CHROMASUNDER_EXPORT_H
#define CHROMASUNDER_EXPORT_H

#if defined(_WIN32) || defined(__CYGWIN__)
#  if defined(CHROMASUNDER_ENGINE_BUILD)
#    define CS_API __declspec(dllexport)
#  else
#    define CS_API __declspec(dllimport)
#  endif
#elif defined(__GNUC__) || defined(__clang__)
#  define CS_API __attribute__((visibility("default")))
#else
#  define CS_API
#endif

#endif
