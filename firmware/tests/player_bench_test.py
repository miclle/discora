"""No serial dependency or device access."""
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location("player_bench", Path(__file__).resolve().parents[1] / "tools/player_bench.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class GuardTests(unittest.TestCase):
    def test_identity(self):
        target = SimpleNamespace(device="/dev/target", serial_number="abc", vid=0x1a86, pid=0x55d3)
        other = SimpleNamespace(device="/dev/other", serial_number="xyz", vid=0x303a, pid=0x1001)
        self.assertIs(bench.identify([other, target], "/dev/target", "abc", 0x1a86, 0x55d3), target)
        for ports, path, serial in [([other], "/dev/other", "abc"), ([target], "/dev/other", "abc"),
                                    ([target, target], "/dev/target", "abc"), ([target], "/dev/target", "wrong")]:
            with self.assertRaises(RuntimeError):
                bench.identify(ports, path, serial, 0x1a86, 0x55d3)

    def test_status(self):
        self.assertEqual(bench.fields("\x1b[0;32mI (100) cd_player: state=stopped sink=software-clock-no-I2S reads=8\x1b[0m"),
                         {"state": "stopped", "sink": "software-clock-no-I2S", "reads": "8"})
        self.assertEqual(bench.fields("unrelated boot output"), {})
        self.assertEqual(bench.fields("source_sha256=abc consumed_sha256=abc"),
                         {"source_sha256": "abc", "consumed_sha256": "abc"})


class TOCTests(unittest.TestCase):
    def test_session_toc(self):
        lines = ["usb_probe: TOC validated first=1 last=2 tracks=2 audio=2 data=0 lead_out_lba=35",
                 "usb_probe: TOC track=1 type=audio start_lba=0 end_lba=17",
                 "usb_probe: TOC track=2 type=audio start_lba=17 end_lba=35"]
        self.assertEqual(bench.observed_toc(lines)[1], {"number": 2, "start": 17, "end": 35})
        for invalid in [lines[:-1], lines[:1], [], [lines[0],lines[1],lines[2].replace("type=audio","type=data")],
                        [lines[0],lines[1],lines[2].replace("start_lba=17","start_lba=18")]]:
            with self.assertRaises(RuntimeError):
                bench.observed_toc(invalid)


class ScriptedSerial:
    def __init__(self, reply):
        self.reply, self.pending, self.commands = reply, b"", []

    @property
    def in_waiting(self):
        return len(self.pending)

    def read(self, size):
        data, self.pending = self.pending[:size], self.pending[size:]
        return data

    def write(self, data):
        self.commands.append(data)
        self.pending += self.reply

    def flush(self):
        pass


class SessionTests(unittest.TestCase):
    def make(self, reply):
        stream = ScriptedSerial(reply)
        report = {"actions": []}
        return bench.Bench(stream, io.BytesIO(), report, 5), stream, report

    def test_ack_and_resources(self):
        session, stream, report = self.make(
            b"I (90) cd_player: state=stopped sink=I2S-unverified generation=1\n"
            b"I (100) cd_player: command=track 99 accepted=0\n"
            b"I (110) cd_player: resources heap_free=1000 heap_min=900 output_stack_min=500\n"
            b"I (120) cd_player: state=playing sink=software-clock-no-I2S generation=2\n")
        state = session.command("track 99", accepted=False)
        self.assertEqual(state["heap_min"], "900")
        self.assertEqual(stream.commands, [b"track 99\n"])
        self.assertEqual(len(report["actions"]), 1)

    def test_reject_wrong_sink(self):
        session, _, _ = self.make(b"cd_player: state=stopped sink=I2S-unverified\n")
        with self.assertRaisesRegex(RuntimeError, "Only software-clock"):
            session.command("status")
        self.assertFalse(session.recognized)

    def test_transport_fault(self):
        session, _, _ = self.make(b"usb_probe: transport error\n")
        with self.assertRaisesRegex(RuntimeError, "transport error"):
            session.command("status")

    def test_missing_ack_is_bounded(self):
        session, _, _ = self.make(b"unrelated boot log\n")
        with self.assertRaisesRegex(RuntimeError, "Missing command"):
            session.command("status")


class EOFTrace(bench.Bench):
    """Scripted observations for report rules, not a simulated drive."""
    def __init__(self, consumed_hash):
        super().__init__(None, io.BytesIO(), {}, 5)
        self.consumed_hash = consumed_hash
        self.emitted = False

    def command(self, command, accepted=True):
        return {"state": "stopped", "eof": "1", "delivered": "39984", "queued": "0", "reads": "3", "generation": "2"}

    def wait_state(self, expected, seconds=40):
        return {"state": expected}

    def pump(self, seconds):
        if not self.emitted:
            self.lines += ["cd_player: verify EOF generation=2 produced=39984 consumed=39984 expected=39984 tail=1176 match=1",
                           "cd_player: verify source_sha256=" + "ab" * 32 + " consumed_sha256=" + self.consumed_hash]
            self.emitted = True


class EOFTests(unittest.TestCase):
    def test_complete_tail_report(self):
        session = EOFTrace("ab" * 32)
        session.eof(39984)
        self.assertEqual(session.report["eof"]["tail"], "1176")
        self.assertEqual(session.report["final"]["reads"], "3")

    def test_hash_mismatch_rejected(self):
        session = EOFTrace("cd" * 32)
        with self.assertRaises(RuntimeError):
            session.eof(39984)

    def test_length_mismatch_rejected(self):
        session = EOFTrace("ab" * 32)
        with self.assertRaises(RuntimeError):
            session.eof(42336)


class I2SEOFTests(unittest.TestCase):
    def fixture(self):
        names = ["last_write", "before_verify", "after_verify", "drain_start", "before_close", "closed"]
        times = [100, 120, 140, 150, 50150, 50170]
        lines = ["cd_player: eof_trace generation=2 " + " ".join(
            f"{name}_{k}={v}" for k, v in [("us", times[i]), ("dma", 100+i), ("ovf", 0 if i<4 else 2)])
            for i, name in enumerate(names)]
        baseline = {"event_overflows": "0", "pcm_submitted": "0", "opens": "0"}
        final = {"generation": "2", "event_overflows": "2", "pcm_submitted": "39984", "opens": "1", "closes": "1",
                 "handle": "0", "tx": "closed", "write_errors": "0", "bad_dma_sizes": "0", "underruns": "0", "report_dropped": "0"}
        return lines, baseline, final

    def test_drain_overflow_is_preserved(self):
        lines, before, final = self.fixture()
        result = bench.i2s_eof_trace(lines, before, final, 39984)
        self.assertEqual(result["closed_ovf"], "2")

    def test_missing_or_steady_overflow_rejected(self):
        lines, before, final = self.fixture()
        for invalid in [lines[:-1], [lines[0].replace("last_write_ovf=0", "last_write_ovf=1")] + lines[1:],
                        [x.replace("generation=2", "generation=1") for x in lines]]:
            with self.assertRaises(RuntimeError):
                bench.i2s_eof_trace(invalid, before, final, 39984)
        final["pcm_submitted"] = "39980"
        with self.assertRaises(RuntimeError):
            bench.i2s_eof_trace(lines, before, final, 39984)

    def test_i2s_requires_explicit_selection_and_counters(self):
        reply = (b"cd_player: i2s tx=closed handle=0 pcm_submitted=0\n"
                 b"cd_player: resources report_dropped=0\n"
                 b"cd_player: state=stopped sink=I2S-unverified generation=2\n")
        session = bench.Bench(ScriptedSerial(reply), io.BytesIO(), {"actions": []}, 5, "i2s-unloaded")
        self.assertEqual(session.command("status")["handle"], "0")
        session.stream.reply = b"cd_player: state=stopped sink=I2S-unverified\n"
        with self.assertRaisesRegex(RuntimeError, "Missing I2S counters"):
            session.command("status")


if __name__ == "__main__":
    unittest.main()
