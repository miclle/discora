#!/usr/bin/env python3
"""Bounded software-clock or explicitly selected unloaded-I2S player checks. Never flashes or saves PCM; opening COM may reset some boards."""
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


def observed_toc(lines):
    header, tracks = None, []
    for line in lines:
        if "usb_probe: TOC validated " in line:
            header, tracks = fields(line), []
        elif header is not None and "usb_probe: TOC track=" in line:
            t = fields(line)
            require(t.get("type") == "audio", "Whole-disc scenario currently requires all-audio media")
            tracks.append({"number": int(t["track"]), "start": int(t["start_lba"]), "end": int(t["end_lba"])})
    require(header is not None and len(tracks) == int(header["tracks"]) and 1 <= len(tracks) <= 99,
            "Need a complete TOC captured in this session; no stale manifest is used")
    require(tracks[0]["number"] == int(header["first"]) and tracks[-1]["number"] == int(header["last"])
            and tracks[-1]["end"] == int(header["lead_out_lba"]), "TOC header mismatch")
    for i, track in enumerate(tracks):
        require(8 <= track["end"] - track["start"] <= 75 * 480, track)
        if i:
            require(track["number"] == tracks[i-1]["number"] + 1 and track["start"] == tracks[i-1]["end"], "TOC discontinuity")
    require(sum(t["end"] - t["start"] for t in tracks) <= 75 * 4500, "Disc exceeds bounded workload")
    return tracks


def i2s_eof_trace(lines, baseline, final, expected_bytes):
    points = {}
    for line in lines:
        if "cd_player: eof_trace " in line:
            part = fields(line)
            require(part["generation"] == final["generation"], "Stale EOF trace")
            points.update(part)
    names = ["last_write", "before_verify", "after_verify", "drain_start", "before_close", "closed"]
    for name in names:
        require(all(name + "_" + key in points for key in ["us", "dma", "ovf"]), "Missing EOF stage: " + name)
    for key in ["us", "dma", "ovf"]:
        values = [int(points[name + "_" + key]) for name in names]
        require(values == sorted(values), "Non-monotonic bounded trace: " + key)
    require(int(points["last_write_ovf"]) == int(baseline["event_overflows"]), "Overflow during PCM supply")
    require(int(points["closed_ovf"]) == int(final["event_overflows"]), "Overflow changed after closure")
    require(50000 <= int(points["before_close_us"]) - int(points["drain_start_us"]) < 100000,
            "EOF drain outside observed scheduling bound")
    require(final["handle"] == "0" and final["tx"] == "closed" and final["opens"] == final["closes"], final)
    require(int(final["pcm_submitted"]) - int(baseline["pcm_submitted"]) == expected_bytes, "PCM submission mismatch")
    require(int(final["opens"]) - int(baseline["opens"]) == 1, "Expected one channel per track")
    require(all(final[k] == "0" for k in ["write_errors", "bad_dma_sizes", "underruns", "report_dropped"]), final)
    return points


class Bench:
    def __init__(self, stream, log, report, timeout, sink="software-clock"):
        self.stream, self.log, self.report = stream, log, report
        self.start = time.monotonic()
        self.deadline = self.start + timeout
        self.pending = b""
        self.lines = []
        self.recognized = False
        self.report_path = None
        self.i2s = sink == "i2s-unloaded"

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
                require(not any(x in line for x in ["Guru Meditation", "Brownout detector", "device closed", "transport error", "output error=", "output close failed="]), line)

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
                require(state.get("sink") == ("I2S-unverified" if self.i2s else "software-clock-no-I2S"),
                        "Only " + ("explicit unloaded-I2S" if self.i2s else "software-clock") + " sink allowed")
                self.recognized = True
                resources = [fields(x) for x in fresh if "cd_player: resources " in x]
                if resources:
                    state.update(resources[-1])
                if self.i2s:
                    stats = [fields(x) for x in fresh if "cd_player: i2s " in x]
                    require(stats, "Missing I2S counters")
                    state.update(stats[-1])
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

    def eof(self, expected_bytes, baseline=None):
        if self.i2s and baseline is None:
            baseline = self.command("status")
        mark = len(self.lines)
        self.command("play")
        self.wait_state("playing")
        end = time.monotonic() + min(540, expected_bytes / 176400 + 45)
        next_progress = time.monotonic() + 30
        while time.monotonic() < end:
            self.pump(2)
            state = self.command("status")
            require(state["state"] not in ["fault", "underrun"], state)
            if time.monotonic() >= next_progress:
                print("track", state["track"], "bytes", state["delivered"], "/", expected_bytes, flush=True)
                next_progress = time.monotonic() + 30
            if state["state"] == "stopped" and state["eof"] == "1" and (not self.i2s or state["handle"] == "0"):
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
        keys = ["reads", "delivered", "queued", "state", "generation", "eof"]
        if self.i2s:
            keys += ["dma_blocks", "event_overflows", "pcm_submitted", "handle"]
        self.report["final"] = self.stable(keys, 2)
        if self.i2s:
            self.report["i2s_eof"] = i2s_eof_trace(self.lines[mark:], baseline, self.report["final"], expected_bytes)

    def disc(self):
        # TOC logging can finish shortly after media is published to the player.
        self.pump(.5)
        tracks = observed_toc(self.lines)
        self.report["toc"] = tracks
        self.report["tracks"] = []
        for track in tracks:
            baseline = self.command("status") if self.i2s else None
            self.command("track " + str(track["number"]))
            self.eof((track["end"] - track["start"]) * 2352, baseline)
            require(int(self.report["final"]["track"]) == track["number"], self.report["final"])
            self.report["tracks"].append({"track": track, "eof": self.report["eof"],
                                          "hashes": self.report["hashes"], "final": self.report["final"]})
            if self.i2s:
                self.report["tracks"][-1]["i2s_eof"] = self.report["i2s_eof"]
            if self.report_path is not None:
                temp = self.report_path.with_suffix(".tmp")
                temp.write_text(json.dumps(self.report, indent=2) + "\n")
                temp.replace(self.report_path)
            print("track complete", track["number"], "hash match", self.report["eof"]["match"], flush=True)

    def sequence(self, start_track):
        self.pump(.5)
        toc = observed_toc(self.lines)
        require(any(t["number"] == start_track for t in toc), "Start track absent")
        tracks = [t for t in toc if t["number"] >= start_track]
        self.report["toc"] = toc
        self.command("track " + str(start_track))
        self.command("stop")
        baseline = self.stable(["state", "reads", "queued"], 1)
        mark = len(self.lines)
        armed = self.command("play-disc")
        require(armed.get("continuous") == "1", "Sequence not armed")
        end = time.monotonic() + sum((t["end"]-t["start"])/75 for t in tracks) + 90
        progress = time.monotonic() + 30
        while time.monotonic() < end:
            self.pump(2)
            state = self.command("status")
            require(state["state"] not in ["fault", "underrun"], state)
            if time.monotonic() >= progress:
                print("sequence track", state["track"], "bytes", state["delivered"], flush=True)
                progress = time.monotonic() + 30
            if state["state"] == "stopped" and state.get("continuous") == "0" and state["eof"] == "1":
                require(int(state["track"]) == tracks[-1]["number"], "Premature sequence stop")
                if not self.i2s or state["handle"] == "0": break
        else:
            raise RuntimeError("Sequence deadline exceeded")
        fresh = self.lines[mark:]
        advances = [fields(x) for x in fresh if "cd_player: sequence advance " in x]
        require([(int(x["from"]),int(x["to"])) for x in advances] ==
                [(a["number"],b["number"]) for a,b in zip(tracks,tracks[1:])], "Unexpected automatic track order")
        require(sum("cd_player: sequence complete " in x for x in fresh) == 1, "Missing sequence completion")
        summaries = [fields(x) for x in fresh if "cd_player: verify EOF " in x]
        hashes = [fields(x) for x in fresh if "cd_player: verify source_sha256=" in x]
        require(len(summaries) == len(hashes) == len(tracks), "Incomplete sequence EOF reports")
        # Deferred status snapshots retain the old track's closed-output counters.
        closed, stats, resources = {}, {}, {}
        for line in fresh:
            if "cd_player: i2s " in line: stats = fields(line)
            elif "cd_player: resources " in line: resources = fields(line)
            elif "cd_player: state=" in line:
                snap = fields(line)
                if snap["state"] == "stopped" and snap.get("eof") == "1":
                    snap.update(stats); snap.update(resources)
                    if not self.i2s or snap.get("handle") == "0": closed[snap["generation"]] = snap
        self.report["tracks"] = []
        for track, eof, digest in zip(tracks, summaries, hashes):
            expected = (track["end"]-track["start"])*2352
            require(eof["match"] == "1" and all(int(eof[k]) == expected for k in ["expected", "produced", "consumed"])
                    and int(eof["tail"]) == (expected % 1764 or 1764), eof)
            require(len(digest["source_sha256"]) == 64 and digest["source_sha256"] == digest["consumed_sha256"], digest)
            require(eof["generation"] in closed, "Missing closed-track snapshot")
            final = closed[eof["generation"]]
            require(int(final["track"]) == track["number"] and final["underruns"] == "0", final)
            entry = {"track": track, "eof": eof, "hashes": digest, "final": final}
            if self.i2s:
                trace = [x for x in fresh if "cd_player: eof_trace " in x and fields(x)["generation"] == eof["generation"]]
                entry["i2s_eof"] = i2s_eof_trace(trace, baseline, final, expected)
            self.report["tracks"].append(entry)
            baseline = final
        self.report["advances"] = advances
        keys = ["reads", "delivered", "queued", "state", "continuous", "generation", "eof"]
        if self.i2s: keys += ["handle", "dma_blocks", "pcm_submitted", "event_overflows"]
        self.report["final"] = self.stable(keys, 2)

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
    parser.add_argument("action", choices=["inspect", "eof", "disc", "sequence", "stress", "faults"])
    parser.add_argument("--sink", choices=["software-clock", "i2s-unloaded"], default="software-clock")
    parser.add_argument("--port", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--vid", type=lambda x: int(x, 16), required=True)
    parser.add_argument("--pid", type=lambda x: int(x, 16), required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-bytes", type=int)
    parser.add_argument("--start-track", type=int, choices=range(1,100), default=1)
    parser.add_argument("--rounds", type=int, choices=range(1, 21), default=10)
    args = parser.parse_args()
    require(args.sink != "i2s-unloaded" or args.action in ["inspect", "eof", "disc", "sequence"], "Unloaded I2S permits eof/disc/sequence only")
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
              "scenario": args.action, "sink": args.sink, "identity": {"port": args.port, "serial": args.serial, "vid": args.vid, "pid": args.pid},
              "actions": [], "rounds": [], "passed": False, "started_scenario": False, "flashed": False, "reset_requested": False}
    stream = serial.Serial(port=None, baudrate=115200, timeout=.01, write_timeout=1)
    stream.dtr = stream.rts = False
    stream.port = args.port
    bench = None
    try:
        stream.open()
        with (args.output / "serial.log").open("wb") as log:
            bench = Bench(stream, log, report, 5400 if args.action in ["disc", "sequence"] else 600, args.sink)
            bench.report_path = args.output / "report.json"
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
            if args.action == "disc":
                bench.disc()
            elif args.action == "sequence":
                bench.sequence(args.start_track)
            elif args.action == "eof":
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
        # Best effort only, to the already positively identified player.
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
