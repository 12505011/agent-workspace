import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import os
from unittest import mock

ROOT = Path(__file__).resolve().parent

class Tools(unittest.TestCase):
    def test_cpu_log_stays_open_after_loaded_library_snapshot(self):
        spec = importlib.util.spec_from_file_location("collect", ROOT / "collect.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        class TwoSamples:
            count = 0
            def wait(self, seconds):
                self.count += 1
                return self.count > 2
        def docker_command(argv, *args):
            if argv[:2] == ["docker", "top"]:
                return dict(code=0, output="PID COMMAND\n%d loader_exe\n" % os.getpid())
            return dict(code=0, output="/debug/install/lib/libperception_q_lidar_obj_det.so\n")
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(module, "command", side_effect=docker_command):
                module.monitor_system(TwoSamples(), Path(directory), "fixture")
            rows = (Path(directory) / "system.jsonl").read_text().splitlines()
            self.assertEqual(len(rows), 2)
            self.assertIn("processes", json.loads(rows[1]))

    def test_cpu_percent_uses_single_core_convention(self):
        module_path = ROOT / "collect.py"
        self.assertTrue(module_path.exists(), "collector not implemented")
        spec = importlib.util.spec_from_file_location("collect", module_path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertAlmostEqual(module.process_cpu_pct(100, 300, 2, 100), 100)
        self.assertEqual(module.process_cpu_pct(300, 100, 2, 100), 0)

    def test_report_excludes_warmup_failed_and_pending_gpu(self):
        module_path = ROOT / "analyze.py"
        self.assertTrue(module_path.exists(), "benchmark analyzer not implemented")
        spec = importlib.util.spec_from_file_location("analyze", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.log"
            path.write_text(
                "[BEV_PERF] model=onemodel scope=core frame=1 complete=1 phase=frame stage=total wall_ms=999 thread_cpu_ms=2\n"
                "[BEV_PERF] model=onemodel scope=core frame=2 complete=0 phase=frame stage=total wall_ms=999 thread_cpu_ms=2\n"
                "[BEV_PERF] model=onemodel scope=core frame=3 complete=1 phase=frame stage=total wall_ms=100 thread_cpu_ms=3\n"
                "[BEV_PERF] model=onemodel scope=core frame=3 complete=1 phase=stage stage=od.head wall_ms=1 thread_cpu_ms=0.1 stream_ms=NA gpu_valid=0\n"
                "[BEV_PERF] model=onemodel scope=core frame=4 complete=1 phase=frame stage=total wall_ms=120 thread_cpu_ms=5\n"
                "[BEV_PERF] model=onemodel scope=core frame=4 complete=1 phase=stage stage=od.head wall_ms=2 thread_cpu_ms=0.1 stream_ms=4 gpu_valid=1\n"
            )
            result = module.summarize(Path(folder), warmup=1)
            self.assertEqual(result["metrics"]["onemodel/core/total"]["wall_ms"]["p50"], 110)
            self.assertEqual(result["metrics"]["onemodel/core/od.head"]["stream_ms"]["n"], 1)
            self.assertEqual(result["metrics"]["onemodel/core/od.head"]["wall_ms"]["n"], 2)

if __name__ == "__main__": unittest.main()
