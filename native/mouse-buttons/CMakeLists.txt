cmake_minimum_required(VERSION 3.16)
project(mouse-buttons C)
# A console program (its stdout is the agent's pipe); the agent starts it without a window.
add_executable(mouse-buttons mouse-buttons.c)
target_link_libraries(mouse-buttons PRIVATE user32)
if (MSVC)
    target_compile_options(mouse-buttons PRIVATE /W4 /O2)
endif()
