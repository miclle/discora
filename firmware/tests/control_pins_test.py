"""Compile the production pin guards; no device or ESP-IDF required."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def main():
    main_dir = Path(__file__).resolve().parents[1] / "main"
    base = {
        "DISCORA_EJECT_BUTTON": 1, "DISCORA_EJECT_GPIO": 41,
        "DISCORA_PLAY_PAUSE_BUTTON": 1, "DISCORA_PLAY_PAUSE_GPIO": 1,
        "DISCORA_TRACK_BUTTONS": 1, "DISCORA_PREV_GPIO": 2, "DISCORA_NEXT_GPIO": 42,
        "DISCORA_OLED": 1, "DISCORA_CD_PLAYER_I2S": 1,
        "DISCORA_I2S_BCLK": 15, "DISCORA_I2S_LRCK": 16, "DISCORA_I2S_DATA": 7,
    }
    legacy = {**base, "DISCORA_EJECT_GPIO": 5, "DISCORA_PLAY_PAUSE_GPIO": 4,
              "DISCORA_PREV_GPIO": 8, "DISCORA_NEXT_GPIO": 9}
    cases = [("adjacent J2 pins", base, None), ("legacy pins", legacy, None),
             ("disabled controls", {}, None)]
    keys = ("EJECT", "PLAY_PAUSE", "PREV", "NEXT")
    for index, key in enumerate(keys):
        for pins, error in [((15, 16, 7), f"{key} GPIO conflicts with I2S"),
                            ((10, 11), f"{key} GPIO conflicts with OLED"),
                            ((0, 3, 19, 20, 35, 36, 37, 43, 44, 45, 46, 48), f"Invalid {key} control GPIO")]:
            for pin in pins:
                cases.append((f"{key} GPIO{pin}", {**base, f"DISCORA_{key}_GPIO": pin}, error))
        for other in keys[:index]:
            cases.append((f"{key} shares {other}",
                          {**base, f"DISCORA_{key}_GPIO": base[f"DISCORA_{other}_GPIO"]},
                          f"{key} GPIO conflicts with {other}"))
    with tempfile.TemporaryDirectory(prefix="discora-control-pins-") as tmp:
        root = Path(tmp)
        source = root / "pins.c"
        source.write_text('#include "control_pins.h"\nint main(void) { return 0; }\n')
        for label, config, error in cases:
            (root / "sdkconfig.h").write_text("".join(
                f"#define CONFIG_{key} {value}\n" for key, value in config.items()))
            result = subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Werror", "-fsyntax-only", "-I", str(root),
                "-I", str(main_dir), str(source)], capture_output=True, text=True)
            if error:
                assert result.returncode != 0 and error in result.stderr, (label, result.stderr)
            else:
                assert result.returncode == 0, (label, result.stderr)
    print(f"PASS: {len(cases)} control pin configurations (compile-time checks only)")


if __name__ == "__main__":
    main()
