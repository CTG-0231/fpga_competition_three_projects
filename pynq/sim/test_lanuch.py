"""Lifecycle tests use tagged fake stages; no PYNQ or board access is required."""
import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "board/lanuch.py"
SPEC = importlib.util.spec_from_file_location("lanuch_test_subject", str(SCRIPT))
lanuch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lanuch)

SOURCES = {
    "setup": """
import asyncio
ROOT = _LAUNCH_ROOT
ol = video = camera = touch = runner = kernels = None
camera_bus = touch_bus = task = None
weights = {}
running = False
events = []
cleanup_count = 0
fail_cleanup = False
cleanup_gate = None
""",
    "overlay": "ol = object(); events.append('overlay')",
    "peripherals": "video = object(); touch = object() if ENABLE_TOUCH else None; events.append('peripherals')",
    "model": "runner = object(); events.append('model')",
    "preview": """
pending_action = None
BROWSER_FPS = 2
preview_metrics = {'lcd_fps': 7.5}
def request_action(action):
    global pending_action, running
    if action == 'stop':
        running = False
    else:
        pending_action = action
async def preview_loop():
    global running
    try:
        while running:
            await asyncio.sleep(0.001)
    finally:
        running = False
running = True
task = asyncio.create_task(preview_loop())
""",
    "cleanup": """
running = False
if task is not None:
    try:
        await task
    except BaseException:
        pass
if cleanup_gate is not None:
    await cleanup_gate.wait()
if fail_cleanup:
    raise RuntimeError('DMA halt failed')
cleanup_count += 1
ol = video = camera = touch = runner = kernels = None
camera_bus = touch_bus = task = None
weights = {}
events.append('cleanup')
""",
}


class LauncherTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "src/trash_pynq").mkdir(parents=True)
        (self.root / "board").mkdir()
        self.write_notebook()
        self.lock = Mock()
        self.preflight = Mock(return_value={"part": "fake"})
        self.fix = Mock()
        self.patches = [patch.object(lanuch, "_preflight", self.preflight),
                        patch.object(lanuch, "_apply_touch_fix", self.fix),
                        patch.object(lanuch, "_acquire_lock", return_value=self.lock),
                        patch.object(lanuch, "_user_namespace", return_value={})]
        for item in self.patches:
            item.start()
        self.assertIsNone(lanuch.get_app())

    def write_notebook(self, updates=None):
        sources = dict(SOURCES)
        sources.update(updates or {})
        cells = [dict(cell_type="code", metadata={"tags": ["ricevision:" + stage]},
                      source=source.splitlines(keepends=True)) for stage, source in sources.items()]
        (self.root / lanuch._NOTEBOOK).write_text(json.dumps(dict(cells=cells)), encoding="utf-8")

    async def asyncTearDown(self):
        app = lanuch.get_app()
        if app is not None:
            app._ns["fail_cleanup"] = False
            gate = app._ns.get("cleanup_gate")
            if gate is not None:
                gate.set()
            await app.stop()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    async def test_start_duplicate_request_and_idempotent_stop(self):
        app = lanuch.start(root=self.root, browser_fps=0)
        self.assertIs(app, lanuch.start(root=self.root))
        self.preflight.assert_called_once()
        self.fix.assert_called_once_with(self.root)
        self.assertTrue(app.status()["running"])
        self.assertEqual(app.status()["browser_fps"], 0)
        self.assertEqual(app._ns["events"], ["overlay", "peripherals", "model"])
        app.request("detect")
        self.assertEqual(app._ns["pending_action"], "detect")
        await asyncio.gather(app.stop(), app.stop(), lanuch.stop())
        await app.stop()
        self.assertEqual(app._ns["cleanup_count"], 1)
        self.lock.close.assert_called_once()
        self.assertIsNone(lanuch.get_app())
        self.assertTrue(app.status()["stopped"])

    async def test_optional_model_touch_and_web_stop(self):
        app = lanuch.start(root=self.root, enable_model=False, enable_touch=False)
        self.fix.assert_not_called()
        self.assertNotIn("model", app._ns["events"])
        self.assertFalse(app.status()["model"])
        self.assertFalse(app.status()["touch"])
        # Notebook button callbacks resolve this replaced global function.
        app._ns["request_action"]("stop")
        await app.stop()
        self.lock.close.assert_called_once()

    async def test_initialization_exception_cleans_partial_resources(self):
        self.write_notebook({"peripherals": "video = object(); raise RuntimeError('camera failed')"})
        with self.assertRaisesRegex(RuntimeError, "camera failed"):
            lanuch.start(root=self.root)
        app = lanuch.get_app()
        self.assertIsNotNone(app)
        await lanuch.stop()
        self.assertEqual(app._ns["cleanup_count"], 1)
        self.lock.close.assert_called_once()
        self.assertIn("camera failed", app.status()["error"])

    async def test_preview_failure_automatically_cleans(self):
        self.write_notebook({"preview": SOURCES["preview"].replace(
            "while running:\n            await asyncio.sleep(0.001)",
            "await asyncio.sleep(0.001)\n        raise RuntimeError('capture timeout')")})
        app = lanuch.start(root=self.root)
        with self.assertRaisesRegex(RuntimeError, "capture timeout"):
            await app._ns["task"]
        await asyncio.sleep(0)
        await app.stop()
        self.assertIn("capture timeout", app.status()["error"])
        self.lock.close.assert_called_once()

    async def test_cleanup_failure_retains_owner_and_lock_then_retries(self):
        app = lanuch.start(root=self.root)
        app._ns["fail_cleanup"] = True
        with self.assertRaisesRegex(RuntimeError, "DMA halt failed"):
            await app.stop()
        self.assertIs(lanuch.get_app(), app)
        self.assertIsNotNone(app._ns["video"])
        self.lock.close.assert_not_called()
        self.assertIn("DMA halt failed", app.status()["cleanup_error"])
        app._ns["fail_cleanup"] = False
        await app.stop()
        self.lock.close.assert_called_once()
        self.assertIsNone(lanuch.get_app())

    async def test_cancelled_waiter_cannot_cancel_cleanup(self):
        app = lanuch.start(root=self.root)
        gate = app._ns["cleanup_gate"] = asyncio.Event()
        waiter = asyncio.create_task(app.stop())
        await asyncio.sleep(0)
        waiter.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiter
        self.assertFalse(app._cleanup_task.cancelled())
        self.lock.close.assert_not_called()
        gate.set()
        await app.stop()
        self.lock.close.assert_called_once()

    async def test_legacy_notebook_is_rejected_before_hardware(self):
        with patch.object(lanuch, "_user_namespace", return_value={"video": object()}):
            with self.assertRaisesRegex(RuntimeError, "cleanup cell"):
                lanuch.start(root=self.root)
        self.preflight.assert_not_called()
        self.assertIsNone(lanuch.get_app())

    async def test_missing_or_duplicate_tag_is_rejected(self):
        path = self.root / lanuch._NOTEBOOK
        notebook = json.loads(path.read_text(encoding="utf-8"))
        notebook["cells"].append(notebook["cells"][0])
        path.write_text(json.dumps(notebook), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "exactly one ricevision:setup"):
            lanuch.start(root=self.root)
        self.preflight.assert_not_called()
        self.assertIsNone(lanuch.get_app())


if __name__ == "__main__":
    unittest.main()
