// parakeet-server: keeps a Parakeet model loaded and turns audio into text over a pipe.
//
// whisper.cpp ships Parakeet only as a command-line tool, which loads the model for every
// file (seconds). The voice agent needs it loaded once, so this reads requests on stdin:
//
//   request:  uint32 n (little-endian), then n int16 samples, 16 kHz mono
//   reply:    one line on stdout: "<milliseconds>\t<text>\n"
//
// It prints "READY\t<system info>\n" once the model is loaded, and exits at end of input.
// Built inside whisper.cpp's tree by .github/workflows/release.yml (see CMakeLists.txt).

#include "parakeet.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

static bool read_exact(void * buf, size_t n) {
    return fread(buf, 1, n, stdin) == n;
}

static void quiet(enum ggml_log_level level, const char * text, void *) {
    if (level >= GGML_LOG_LEVEL_WARN) {
        fputs(text, stderr);
    }
}

int main(int argc, char ** argv) {
    std::string model;
    int  n_threads = std::min(4, (int) std::thread::hardware_concurrency());
    bool use_gpu   = true;
    int  device    = 0;
    bool verbose   = false;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if      ((a == "-m" || a == "--model")   && i + 1 < argc) { model     = argv[++i]; }
        else if ((a == "-t" || a == "--threads") && i + 1 < argc) { n_threads = std::stoi(argv[++i]); }
        else if ((a == "-dev" || a == "--device") && i + 1 < argc) { device   = std::stoi(argv[++i]); }
        else if (a == "-ng" || a == "--no-gpu")  { use_gpu = false; }
        else if (a == "-v"  || a == "--verbose") { verbose = true; }
        else {
            fprintf(stderr, "usage: %s -m model.bin [-t threads] [-ng] [-dev N] [-v]\n", argv[0]);
            return 2;
        }
    }
    if (model.empty()) {
        fprintf(stderr, "error: -m model.bin is required\n");
        return 2;
    }
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);   // the samples are bytes, not text
    _setmode(_fileno(stdout), _O_BINARY);  // and replies end in a plain \n
#endif
    if (!verbose) {
        parakeet_log_set(quiet, nullptr);
    }

    parakeet_context_params cparams = parakeet_context_default_params();
    cparams.use_gpu    = use_gpu;
    cparams.gpu_device = device;
    parakeet_context * ctx = parakeet_init_from_file_with_params(model.c_str(), cparams);
    if (!ctx) {
        fprintf(stderr, "error: failed to load the model from '%s'\n", model.c_str());
        return 1;
    }
    printf("READY\t%s\n", parakeet_print_system_info());
    fflush(stdout);

    std::vector<int16_t> pcm;
    std::vector<float>   samples;
    uint32_t n = 0;
    while (read_exact(&n, sizeof(n))) {
        if (n > 16000u * 120u) {  // over two minutes: not a voice command, and not ours to buffer
            fprintf(stderr, "error: request of %u samples refused\n", n);
            return 3;
        }
        pcm.resize(n);
        if (n && !read_exact(pcm.data(), n * sizeof(int16_t))) {
            break;
        }
        samples.resize(n);
        for (uint32_t i = 0; i < n; i++) {
            samples[i] = pcm[i] / 32768.0f;
        }

        const auto t0 = std::chrono::steady_clock::now();
        std::string text;
        if (n >= 1600) {  // under 0.1 s there is nothing to hear
            parakeet_full_params p = parakeet_full_default_params(PARAKEET_SAMPLING_GREEDY);
            p.n_threads = n_threads;
            if (parakeet_full(ctx, p, samples.data(), (int) samples.size()) == 0) {
                for (int i = 0; i < parakeet_full_n_segments(ctx); i++) {
                    if (!text.empty()) {
                        text += ' ';
                    }
                    text += parakeet_full_get_segment_text(ctx, i);
                }
            } else {
                fprintf(stderr, "error: transcription failed\n");
            }
        }
        for (char & c : text) {
            if (c == '\n' || c == '\r' || c == '\t') {
                c = ' ';
            }
        }
        const long ms = (long) std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - t0).count();
        printf("%ld\t%s\n", ms, text.c_str());
        fflush(stdout);
    }
    parakeet_free(ctx);
    return 0;
}
