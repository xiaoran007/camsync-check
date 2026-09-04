#include <Arduino.h>
#include "boards/uno_r4_wifi/target.h"

void setup() {
    Serial.begin(115200);
    // Standalone USB power must work without waiting for a serial connection.
    target::begin();
}

void loop() {
    if (Serial.available() == 0) {
        return;
    }
    switch (Serial.read()) {
        case 's': target::set_mode(target::Mode::sweep); break;
        case 'c': target::set_mode(target::Mode::corners); break;
        case 'd': target::set_mode(target::Mode::dark); break;
        case '?': target::print_status(Serial); break;
        case '\r': case '\n': break;
        default: Serial.println("Commands: s=sweep c=corners d=dark ?=status");
    }
}
