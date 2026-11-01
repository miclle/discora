#!/usr/bin/env python3
"""Bounded software-clock player checks. Never flashes or saves PCM; opening COM may reset some boards."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def fields(line):
    line = ANSI.sub("", line)
    return dict(re.findall(r"\b([a-z_][a-z0-9_]*)=([^\s]+)", line))


def identify(ports, port, serial_number, vid, pid):
    matches = [p for p in ports if (p.vid, p.pid, p.serial_number) == (vid, pid, serial_number)]
    if len(matches) != 1 or matches[0].device != port:
        raise RuntimeError("Serial identity/path mismatch; refusing to open a device")
    return matches[0]


def require(condition, detail):
    if not condition:
        raise RuntimeError(str(detail))


class Bench:
    def __init__(self, stream, log, report, timeout):
        self.stream, self.log, self.report = stream, log, report
        self.start = time.monotonic()
        self.deadline = self.start + timeout
        self.pending = b""
        self.lines = []
        self.recognized = False

    def pump(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            require(time.monotonic() < self.deadline, "Overall bench deadline exceeded")
            data = self.stream.read(self.stream.in_waiting or 1)
            if not data:
                continue
            self.log.write(data)
            self.log.flush()
            self.pending += data
            while b"\n" in self.pending:
                line, self.pending = self.pending.split(b"\n", 1)
                line = ANSI.sub("", line.decode(errors="replace")).strip()
                self.lines.append(line)
                require(not any(x in line for x in ["Guru Meditation", "Brownout detector", "device closed", "transport error"]), line)

    def command(self, command, accepted=True):
        mark = len(self.lines)
        start = time.monotonic()
        self.stream.write((command + "\n").encode("ascii"))
        ack = None
        while time.monotonic() - start < 2:
            self.pump(.02)
            fresh = self.lines[mark:]
            expected = "cd_player: state=" if command == "status" else "cd_player: command=" + command + " accepted="
            replies = [x for x in fresh if expected in x]
            if replies and ack is None:
                ack = time.monotonic() - start
                if command != "status":
                    require(fields(replies[-1]).get("accepted") == str(int(accepted)), replies[-1])
            # An asynchronous state line before the acknowledgement belongs to older work.
            if command != "status" and replies:
                fresh = fresh[fresh.index(replies[-1]):]
            states = [fields(x) for x in fresh if "cd_player: state=" in x]
            if ack is not None and states:
                state = states[-1]
                require(state.get("sink") == "software-clock-no-I2S", "Only software-clock sink allowed")
                self.recognized = True
                resources = [fields(x) for x in fresh if "cd_player: resources " in x]
                if resources:
                    state.update(resources[-1])
                self.report["actions"].append({"command": command, "ack_seconds": round(ack, 4), "state": state})
                return state
        raise RuntimeError("Missing command acknowledgement/status: " + command)

    def wait_state(self, expected, seconds=40):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            state = self.command("status")
            if state["state"] == expected:
                return state
            require(state["state"] not in ["fault", "underrun"] or state["state"] == expected, state)
            self.pump(.25)
        raise RuntimeError("State timeout: " + expected)

    def stable(self, keys, seconds=.5):
        first = self.command("status")
        self.pump(seconds)
        last = self.command("status")
        require(all(first[k] == last[k] for k in keys), (first, last))
        return last

    def stress(self, rounds):
        self.command("play")
        self.wait_state("playing")
        baseline = self.command("status")
        self.report["baseline"] = baseline
        for index in range(rounds):
            self.command("pause")
            paused = self.stable(["delivered", "generation", "state"])
            require(paused["state"] == "paused", paused)
            self.command("play")
            self.wait_state("playing")
            following = self.command("next")
            require(int(following["track"]) > int(baseline["track"])
                    and following["generation"] != paused["generation"], following)
            self.wait_state("playing")
            previous = self.command("prev")
            require(previous["track"] == baseline["track"]
                    and previous["generation"] != following["generation"], previous)
            self.wait_state("playing")
            before = self.command("status")
            after = self.command("track 99", accepted=False)
            require(before["generation"] == after["generation"], after)
            self.command("stop")
            stopped = self.stable(["reads", "delivered", "queued", "state"])
            require(stopped["state"] == "stopped" and stopped["queued"] == "0", stopped)
            # Allow an actual request to enter USB, then invalidate its generation.
            self.command("play")
            self.pump(.01)
            self.command("stop")
            self.command("play")
            self.wait_state("playing")
            current = self.command("status")
            require(current["underruns"] == baseline["underruns"], current)
            self.report["rounds"].append(current)
            print("control round", index + 1, "stale", current["stale"], flush=True)
        self.command("stop")
        self.report["final"] = self.stable(["reads", "delivered", "queued", "state"], 1)

    def eof(self, expected_bytes):
        mark = len(self.lines)
        self.command("play")
        self.wait_state("playing")
        end = time.monotonic() + min(540, expected_bytes / 176400 + 45)
        while time.monotonic() < end:
            self.pump(2)
            state = self.command("status")
            require(state["state"] not in ["fault", "underrun"], state)
            if state["state"] == "stopped" and state["eof"] == "1":
                break
        else:
            raise RuntimeError("No EOF within track deadline")
        require(int(state["delivered"]) == expected_bytes and state["queued"] == "0", state)
        summaries = [fields(x) for x in self.lines[mark:] if "cd_player: verify EOF " in x]
        require(len(summaries) == 1, summaries)
        summary = summaries[0]
        require(summary["match"] == "1" and summary["generation"] == state["generation"]
                and int(summary["expected"]) == expected_bytes and int(summary["produced"]) == expected_bytes
                and int(summary["consumed"]) == expected_bytes
                and int(summary["tail"]) == (expected_bytes % 1764 or 1764), summary)
        hashes = [fields(x) for x in self.lines[mark:] if "cd_player: verify source_sha256=" in x]
        require(len(hashes) == 1 and len(hashes[0]["source_sha256"]) == 64
                and hashes[0]["source_sha256"] == hashes[0]["consumed_sha256"], hashes)
        self.report["eof"] = summary
        self.report["hashes"] = hashes[0]
        self.report["final"] = self.stable(["reads", "delivered", "queued", "state", "generation", "eof"], 2)

    def faults(self):
        self.command("play")
        self.wait_state("playing")
        before = self.command("status")
        self.command("test delay")
        stalled = self.wait_state("underrun", 5)
        require(int(stalled["underruns"]) == int(before["underruns"]) + 1, stalled)
        self.report["underrun"] = self.stable(["delivered", "reads", "state"], 1.5)
        self.command("play")
        self.report["resumed"] = self.wait_state("playing")
        self.command("test fail")
        fault = self.wait_state("fault", 5)
        require(fault["queued"] == "0", fault)
        self.report["fault"] = self.stable(["delivered", "reads", "state"], 1)
        self.command("play", accepted=False)
        self.command("stop")
        self.command("play")
        self.report["restarted"] = self.wait_state("playing")
        # Check while playing, so refusal proves spent budgets rather than stopped state.
        self.command("test delay", accepted=False)
        self.command("test fail", accepted=False)
        self.command("stop")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inspect", "eof", "stress", "faults"])
    parser.add_argument("--port", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--vid", type=lambda x: int(x, 16), required=True)
    parser.add_argument("--pid", type=lambda x: int(x, 16), required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-bytes", type=int)
    parser.add_argument("--rounds", type=int, choices=range(1, 21), default=10)
    args = parser.parse_args()
    import serial
    from serial.tools import list_ports
    target = identify(list_ports.comports(), args.port, args.serial, args.vid, args.pid)
    if args.action == "inspect":
        print(json.dumps({"port": target.device, "serial": target.serial_number, "vid": target.vid, "pid": target.pid}))
        return
    require(args.output is not None, "--output required for experiments")
    if args.action == "eof":
        require(args.expected_bytes is not None and 0 < args.expected_bytes <= 176400 * 480
                and args.expected_bytes % 2352 == 0, "EOF requires --expected-bytes from the selected track TOC, at most 480 seconds")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"started_utc": datetime.now(timezone.utc).isoformat(),
              "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "scenario": args.action, "identity": {"port": args.port, "serial": args.serial, "vid": args.vid, "pid": args.pid},
              "actions": [], "rounds": [], "passed": False, "started_scenario": False, "flashed": False, "reset_requested": False}
    stream = serial.Serial(port=None, baudrate=115200, timeout=.01, write_timeout=1)
    stream.dtr = stream.rts = False
    stream.port = args.port
    bench = None
    try:
        stream.open()
        with (args.output / "serial.log").open("wb") as log:
            bench = Bench(stream, log, report, 600)
            bench.pump(.1)
            ready_deadline = time.monotonic() + 45
            while True:
                state = bench.command("status")
                require(state["state"] == "stopped", "Need stopped player firmware")
                if state["media"] == "1":
                    break
                require(time.monotonic() < ready_deadline, "No ready medium within 45 seconds")
                bench.pump(.5)
            report["boot_observed"] = any("ESP-ROM:" in x for x in bench.lines)
            report["started_scenario"] = True
            if args.action == "eof":
                bench.eof(args.expected_bytes)
            elif args.action == "stress":
                bench.stress(args.rounds)
            else:
                bench.faults()
            report["passed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        # Best effort only, to the already positively identified software player.
        if stream.is_open and bench is not None and bench.recognized and report["started_scenario"]:
            try:
                stream.write(b"stop\n")
            except serial.SerialException as exc:
                report["stop_error"] = str(exc)
        stream.close()
        if bench is not None:
            report["boot_observed"] = any("ESP-ROM:" in x for x in bench.lines)
            report["firmware_versions_seen"] = [x.split("App version:", 1)[1].strip()
                                                 for x in bench.lines if "App version:" in x]
        log_path = args.output / "serial.log"
        if log_path.exists():
            report["serial_log_sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
        report["elapsed_seconds"] = round(time.monotonic() - bench.start, 3) if bench else 0
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
