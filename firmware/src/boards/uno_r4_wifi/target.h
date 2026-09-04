#pragma once

#include <Arduino.h>
#include <optical_protocol.h>

namespace target {
constexpr uint32_t slot_us = optical_protocol::slot_us;
constexpr uint8_t led_count = 96;
constexpr uint8_t irq_priority = 2;

enum class Mode : uint8_t { sweep, corners, dark };

bool begin();
void set_mode(Mode mode);
void print_status(Print &output);
} // namespace target
