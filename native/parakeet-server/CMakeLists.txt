# Copied into whisper.cpp's examples/ by the release workflow and added after parakeet-cli.
set(TARGET parakeet-server)
add_executable(${TARGET} parakeet-server.cpp)

include(DefaultTargetOptions)

target_link_libraries(${TARGET} PRIVATE parakeet ${CMAKE_THREAD_LIBS_INIT})

install(TARGETS ${TARGET} RUNTIME)
