// doomgeneric_emscripten.c
// Emscripten backend for DoomGeneric without SDL. Implements the platform
// functions DoomGeneric expects (see doomgeneric.h):
//   - frames are handed to JS as a pointer into WASM memory; JS blits them
//     onto a <canvas> via window.DoomBridge._blitFrame(ptr, w, h)
//   - keys are pushed from JS with DG_PushKey(pressed, doomKey)
//   - main() owns the game loop through emscripten_set_main_loop, because
//     DoomGeneric's D_DoomLoop only runs a single tick and returns.
//
// build.sh copies this file into the doomgeneric/ source tree before compiling.

#include <emscripten.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

#include "doomgeneric.h"
#include "doomkeys.h"

#define KEYQUEUE_SIZE 64

static uint8_t s_keyQueue[KEYQUEUE_SIZE];
static uint8_t s_keyIsPressed[KEYQUEUE_SIZE];
static int     s_keyQueueRead = 0;
static int     s_keyQueueWrite = 0;

// Called from JS: Module.ccall('DG_PushKey', null, ['number','number'], [pressed, key])
EMSCRIPTEN_KEEPALIVE
void DG_PushKey(int pressed, int doomKey) {
    int next = (s_keyQueueWrite + 1) % KEYQUEUE_SIZE;
    if (next == s_keyQueueRead) {
        return; // queue full: drop rather than overwrite unread keys
    }
    s_keyQueue[s_keyQueueWrite] = (uint8_t) doomKey;
    s_keyIsPressed[s_keyQueueWrite] = (uint8_t) (pressed != 0);
    s_keyQueueWrite = next;
}

void DG_Init(void) {
    EM_ASM({
        console.log("DoomGeneric: DG_Init, resolution " + $0 + "x" + $1);
    }, DOOMGENERIC_RESX, DOOMGENERIC_RESY);
}

void DG_DrawFrame(void) {
    // DG_ScreenBuffer is a uint32_t* buffer of RESX*RESY pixels packed as
    // 0x00RRGGBB (see i_video.c). JS converts it to RGBA and paints it.
    EM_ASM({
        if (window.DoomBridge && window.DoomBridge._blitFrame) {
            window.DoomBridge._blitFrame($0, $1, $2);
        }
    }, DG_ScreenBuffer, DOOMGENERIC_RESX, DOOMGENERIC_RESY);
}

void DG_SleepMs(uint32_t ms) {
    // No-op on purpose. The browser drives doomgeneric_Tick via
    // requestAnimationFrame, and TryRunTics() returns as soon as a tic has
    // elapsed, so sleeping here would only stall the frame. Avoiding
    // emscripten_sleep() also means the build does not need ASYNCIFY.
    (void) ms;
}

uint32_t DG_GetTicksMs(void) {
    return (uint32_t) emscripten_get_now();
}

int DG_GetKey(int* pressed, unsigned char* doomKey) {
    if (s_keyQueueRead == s_keyQueueWrite) {
        return 0;
    }
    *pressed = s_keyIsPressed[s_keyQueueRead];
    *doomKey = s_keyQueue[s_keyQueueRead];
    s_keyQueueRead = (s_keyQueueRead + 1) % KEYQUEUE_SIZE;
    return 1;
}

void DG_SetWindowTitle(const char* title) {
    EM_ASM({
        if (window.DoomBridge && window.DoomBridge.onTitle) {
            window.DoomBridge.onTitle(UTF8ToString($0));
        }
    }, title);
}

int main(int argc, char **argv) {
    doomgeneric_Create(argc, argv);
    // fps=0 -> requestAnimationFrame; simulate_infinite_loop=1 -> never returns
    emscripten_set_main_loop(doomgeneric_Tick, 0, 1);
    return 0;
}
