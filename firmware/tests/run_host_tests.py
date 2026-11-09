#!/usr/bin/env python3
"""Compile/run the platform-independent wire protocol tests; no device access."""

import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import sys


def main():
    firmware = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(firmware / "tests/control_pins_test.py")], check=True)
    with tempfile.TemporaryDirectory(prefix="discora-protocol-") as temp:
        for name, sources, flags in [
            ("usb_ab", ["tests/usb_ab_test.c"], []),
            ("usb_trace", ["tests/usb_trace_test.c"], []),
            ("usb_trace_port", ["main/usb_trace_port.c", "tests/usb_trace_port_test.c"],
             ["-DCONFIG_DISCORA_USB_DIAGNOSTICS=1"]),
        ]:
            diagnostic = Path(temp) / name
            subprocess.run(
                shlex.split(os.environ.get("CC", "cc")) + flags + [
                    "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-I", str(firmware / "tests/stubs"), "-I", str(firmware / "main"),
                ] + [str(firmware / source) for source in sources] + ["-o", str(diagnostic)],
                check=True,
            )
            subprocess.run([str(diagnostic)], check=True)

        binary = Path(temp) / "probe_protocol_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc"))
            + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-I", str(firmware / "main"),
                str(firmware / "main/probe_protocol.c"),
                str(firmware / "tests/probe_protocol_test.c"), "-o", str(binary),
            ],
            check=True,
        )
        subprocess.run([str(binary)], check=True)
        button = Path(temp) / "eject_button_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-I", str(firmware / "main"), str(firmware / "main/button_core.c"),
                str(firmware / "tests/eject_button_test.c"), "-o", str(button),
            ], check=True,
        )
        subprocess.run([str(button)], check=True)
        tracks = Path(temp) / "track_buttons_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-I", str(firmware / "main"), str(firmware / "main/button_core.c"),
                str(firmware / "main/track_buttons_core.c"), str(firmware / "main/pcm_buffer.c"),
                str(firmware / "main/audio_core.c"), str(firmware / "main/cd_player_core.c"),
                str(firmware / "tests/track_buttons_test.c"), "-o", str(tracks),
            ], check=True,
        )
        subprocess.run([str(tracks)], check=True)
        oled = Path(temp) / "oled_panel_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-I", str(firmware / "main"), str(firmware / "main/pcm_buffer.c"),
                str(firmware / "main/audio_core.c"), str(firmware / "main/cd_player_core.c"),
                str(firmware / "main/oled_panel.c"), str(firmware / "tests/oled_panel_test.c"),
                "-o", str(oled),
            ], check=True,
        )
        subprocess.run([str(oled)], check=True)
        stream = Path(temp) / "stream_core_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-I", str(firmware / "main"), str(firmware / "main/pcm_buffer.c"),
                str(firmware / "main/cdda_cursor.c"), str(firmware / "tests/stream_core_test.c"),
                "-o", str(stream),
            ], check=True,
        )
        subprocess.run([str(stream)], check=True)
        audio = Path(temp) / "audio_core_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-I", str(firmware / "main"), str(firmware / "main/pcm_buffer.c"),
                str(firmware / "main/audio_core.c"), str(firmware / "main/test_tone.c"),
                str(firmware / "tests/audio_core_test.c"), "-o", str(audio),
            ], check=True,
        )
        subprocess.run([str(audio)], check=True)
        recovery = Path(temp) / "cdda_recovery_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-I", str(firmware / "main"), str(firmware / "main/cdda_recovery.c"),
                str(firmware / "main/pcm_buffer.c"), str(firmware / "main/audio_core.c"),
                str(firmware / "main/cd_player_core.c"),
                str(firmware / "tests/cdda_recovery_test.c"), "-o", str(recovery),
            ], check=True,
        )
        subprocess.run([str(recovery)], check=True)
        player = Path(temp) / "cd_player_core_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-I", str(firmware / "main"), str(firmware / "main/pcm_buffer.c"),
                str(firmware / "main/audio_core.c"), str(firmware / "main/cd_player_core.c"),
                str(firmware / "tests/cd_player_core_test.c"), "-o", str(player),
            ], check=True,
        )
        subprocess.run([str(player)], check=True)

        rebuffer = Path(temp) / "cd_player_rebuffer_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-I", str(firmware / "main"), str(firmware / "main/pcm_buffer.c"),
                str(firmware / "main/audio_core.c"), str(firmware / "main/cd_player_core.c"),
                str(firmware / "tests/cd_player_rebuffer_test.c"), "-o", str(rebuffer),
            ], check=True,
        )
        subprocess.run([str(rebuffer)], check=True)

        # Both wire formats retain PCM16 DMA sizing, preload and lifecycle checks.
        for name, flags in [
            ("default", []),
            ("64fs", ["-DCONFIG_DISCORA_AUDIO_DIAGNOSTIC=1", "-DCONFIG_DISCORA_DIAG_I2S_64FS=1"]),
            ("non_diag", ["-DCONFIG_DISCORA_DIAG_I2S_64FS=1"]),
        ]:
            adapter = Path(temp) / ("audio_i2s_test_" + name)
            subprocess.run(
                shlex.split(os.environ.get("CC", "cc")) + flags + [
                    "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-I", str(firmware / "tests/stubs"), "-I", str(firmware / "main"),
                    str(firmware / "main/audio_i2s.c"), str(firmware / "tests/audio_i2s_test.c"),
                    "-o", str(adapter),
                ], check=True,
            )
            subprocess.run([str(adapter)], check=True)

        clocks = Path(temp) / "audio_clock_probe_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-DCONFIG_DISCORA_AUDIO_DIAGNOSTIC=1", "-DCONFIG_DISCORA_DIAG_CLOCK_PROBE=1",
                "-I", str(firmware / "tests/stubs"), "-I", str(firmware / "main"),
                str(firmware / "main/audio_clock_probe.c"), str(firmware / "tests/audio_clock_probe_test.c"),
                "-o", str(clocks),
            ], check=True,
        )
        for args in ([], ["setup-error"], ["start-error"]):
            subprocess.run([str(clocks)] + args, check=True)

        waiting = Path(temp) / "transfer_wait_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-I", str(firmware / "main"), str(firmware / "main/transfer_wait.c"),
                str(firmware / "main/pcm_buffer.c"), str(firmware / "main/audio_core.c"),
                str(firmware / "main/cd_player_core.c"), str(firmware / "tests/transfer_wait_test.c"),
                "-o", str(waiting),
            ], check=True,
        )
        subprocess.run([str(waiting)], check=True)

        sequences = Path(temp) / "cd_player_sequence_test"
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-g",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-I", str(firmware / "main"), str(firmware / "main/pcm_buffer.c"),
                str(firmware / "main/audio_core.c"), str(firmware / "main/cd_player_core.c"),
                str(firmware / "tests/cd_player_sequence_test.c"), "-o", str(sequences),
            ], check=True,
        )
        subprocess.run([str(sequences)], check=True)




if __name__ == "__main__":
    main()
