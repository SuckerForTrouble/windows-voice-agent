// mouse-buttons: the mouse's side buttons as push-to-talk keys.
//
// Windows' hotkeys (RegisterHotKey) know nothing about mouse buttons, so this watches
// them with a low-level mouse hook. It is a separate little C program because such a
// hook sees every mouse event, movements included (1000 a second on a gaming mouse):
// in Python each one would wait for the interpreter and could make the mouse stutter.
// Here only the side buttons do any work; everything else passes straight through.
//
//   mouse-buttons 1 2      watch button 1 (back) and/or 2 (forward)
//   stdout                 "down 1" / "up 1" per press, one line each
//   the watched buttons are swallowed, so a browser doesn't also go back / forward
//   it exits when its stdin closes (the agent quit or crashed)
//   mouse-buttons --check  installs the hook, prints "ok", exits (the build's self-test)

#include <windows.h>
#include <stdio.h>
#include <string.h>

static int watch[3];
static DWORD main_thread;

static LRESULT CALLBACK on_mouse(int code, WPARAM wp, LPARAM lp) {
    if (code == HC_ACTION && (wp == WM_XBUTTONDOWN || wp == WM_XBUTTONUP)) {
        const MSLLHOOKSTRUCT * m = (const MSLLHOOKSTRUCT *) lp;
        const int b = HIWORD(m->mouseData);
        if (b >= 1 && b <= 2 && watch[b] && !(m->flags & LLMHF_INJECTED)) {
            printf("%s %d\n", wp == WM_XBUTTONDOWN ? "down" : "up", b);
            fflush(stdout);
            return 1;  // swallowed
        }
    }
    return CallNextHookEx(NULL, code, wp, lp);
}

static DWORD WINAPI wait_for_parent(LPVOID unused) {
    (void) unused;
    char buf[64];
    while (fgets(buf, sizeof(buf), stdin)) {
    }
    PostThreadMessage(main_thread, WM_QUIT, 0, 0);  // stdin closed: the agent is gone
    return 0;
}

int main(int argc, char ** argv) {
    int check = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--check") == 0) {
            check = 1;
        } else if (strcmp(argv[i], "1") == 0 || strcmp(argv[i], "2") == 0) {
            watch[argv[i][0] - '0'] = 1;
        } else {
            fprintf(stderr, "usage: %s [1] [2] | --check\n", argv[0]);
            return 2;
        }
    }
    HHOOK hook = SetWindowsHookExW(WH_MOUSE_LL, on_mouse, GetModuleHandleW(NULL), 0);
    if (!hook) {
        fprintf(stderr, "error: SetWindowsHookEx failed (%lu)\n", GetLastError());
        return 1;
    }
    if (check) {
        printf("ok\n");
        UnhookWindowsHookEx(hook);
        return 0;
    }
    main_thread = GetCurrentThreadId();
    CreateThread(NULL, 0, wait_for_parent, NULL, 0, NULL);
    printf("ready\n");
    fflush(stdout);
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {  // a low-level hook needs this thread pumping messages
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    UnhookWindowsHookEx(hook);
    return 0;
}
