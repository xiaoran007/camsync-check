"""Generate the firmware lookup table from the Python package's target profile."""

import json
from pathlib import Path

Import("env")

profile = json.loads((Path(env.subst("$PROJECT_DIR")).parent /
                      "src/camsync_check/profiles/uno_r4_wifi.json").read_text())
order = profile["scan_order"]
if sorted(order) != list(range(96)) or profile["slot_us"] != 250:
    raise ValueError("Expected a 96-LED permutation at 250 us")
directory = Path(env.subst("$BUILD_DIR")) / "generated"
directory.mkdir(parents=True, exist_ok=True)
header = directory / "optical_protocol.h"
content = ("// Generated from the target profile; do not edit.\n#pragma once\n#include <stdint.h>\n"
           "namespace optical_protocol {\n"
           f"constexpr uint32_t slot_us = {profile['slot_us']};\n"
           f"constexpr const char *id = {json.dumps(profile['protocol'])};\n"
           "constexpr uint8_t scan_order[96] = {" + ", ".join(map(str, order)) + "};\n}\n")
if not header.exists() or header.read_text() != content:
    header.write_text(content)
env.Append(CPPPATH=[str(directory)])
