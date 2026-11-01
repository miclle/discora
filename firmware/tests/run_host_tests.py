#!/usr/bin/env python3
"""Compile/run the platform-independent wire protocol tests; no device access."""

import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def main():
    firmware = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="discora-protocol-") as temp:
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
                str(firmware / "tests/cdda_recovery_test.c"), "-o", str(recovery),
            ], check=True,
        )
        subprocess.run([str(recovery)], check=True)



if __name__ == "__main__":
    main()
