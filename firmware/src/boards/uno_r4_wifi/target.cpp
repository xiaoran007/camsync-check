#include "target.h"

#include <Arduino_LED_Matrix.h>
#include <FspTimer.h>

namespace target {
namespace {
// Reuse the core's source/sink mapping and direct GPIO implementation.
// ArduinoCore-renesas 1.6.0, Arduino_LED_Matrix.h, on()/off().
// Never call matrix.begin(): the official scanner must stay disabled.
ArduinoLEDMatrix matrix;
FspTimer timer;
volatile Mode active_mode = Mode::sweep;
volatile uint32_t ticks = 0;
uint8_t next_led = 0;
uint8_t corner_index = 0;
uint8_t corner_cycles = 0;
constexpr uint8_t corners[] = {0, 11, 95, 84};
bool ready = false;
uint32_t clock_hz = 0;

void tick(timer_callback_args_t *) {
    const Mode mode = active_mode;
    if (mode == Mode::sweep) {
        matrix.on(next_led);
    } else if (mode == Mode::corners && next_led == 0) {
        matrix.on(corners[corner_index]);
    } else {
        matrix.off(0);
    }
    ++ticks;
    if (++next_led == led_count) {
        next_led = 0;
        if (++corner_cycles == 21) {
            corner_cycles = 0;
            corner_index = (corner_index + 1) % 4;
        }
    }
}
} // namespace

bool begin() {
    matrix.off(0);
    uint8_t type = GPT_TIMER;
    const int8_t channel = FspTimer::get_available_timer(type);
    if (channel < 0 || type != GPT_TIMER) {
        return false;
    }
    clock_hz = R_FSP_SystemClockHzGet(FSP_PRIV_CLOCK_PCLKD);
    // Integer period counts avoid floating-point truncation of the slot.
    const uint64_t scaled = static_cast<uint64_t>(clock_hz) * slot_us;
    if (scaled % 1000000 != 0 || scaled / 1000000 > 65535) {
        return false;
    }
    const uint32_t counts = scaled / 1000000;
    if (!timer.begin(TIMER_MODE_PERIODIC, GPT_TIMER, channel, counts, 0U,
                     TIMER_SOURCE_DIV_1, tick)) {
        return false;
    }
    if (!timer.setup_overflow_irq(irq_priority) || !timer.open() || !timer.start()) {
        timer.end();
        matrix.off(0);
        return false;
    }
    ready = true;
    return true;
}

void set_mode(Mode mode) {
    if (!ready) {
        return;
    }
    // Keep this critical section short; no I/O or allocation here.
    const uint32_t primask = __get_PRIMASK();
    __disable_irq();
    active_mode = mode;
    next_led = 0;
    corner_index = 0;
    corner_cycles = 0;
    matrix.off(0);
    __set_PRIMASK(primask);
}

void print_status(Print &out) {
    out.print("{\"board\":\"uno_r4_wifi\",\"protocol\":\"sweep96-v0\",\"slot_us\":250,");
    out.print("\"period_us\":24000,\"clock_source\":\"PCLKD\",\"clock_hz\":");
    out.print(clock_hz);
    out.print(",\"divider\":1,\"irq_priority\":2,\"ready\":");
    out.print(ready ? "true" : "false");
    out.print(",\"timer_channel\":");
    if (ready) out.print(timer.get_channel()); else out.print("null");
    out.print(",\"period_counts\":");
    if (ready) out.print(timer.get_period_raw()); else out.print("null");
    out.print(",\"mode\":\"");
    switch (active_mode) {
        case Mode::sweep: out.print("sweep"); break;
        case Mode::corners: out.print("corners"); break;
        case Mode::dark: out.print("dark"); break;
    }
    out.print("\",\"isr_count\":");
    out.print(ticks);
    out.println(",\"clock_calibrated\":false,\"overrun_detection\":false}");
}
} // namespace target
