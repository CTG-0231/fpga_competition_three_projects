#!/usr/bin/env python3
"""One-command AC820 LCD/camera application, reusing the verified notebook.

Jupyter: ``from lanuch import start; app = start()`` and ``await app.stop()``.
SSH: ``sudo /usr/local/share/pynq-venv/bin/python3 board/lanuch.py`` (Ctrl+C stops).
The filename intentionally follows the requested spelling, ``lanuch.py``.
"""
import argparse
import ast
import asyncio
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import signal
import sys
import types


_STAGES = ("setup", "overlay", "peripherals", "model", "preview", "cleanup")
_NOTEBOOK = Path("board/01_bringup_and_demo_optimized.ipynb")
_LOCK_PATH = "/run/lock/ac820-ricevision.lock"
# %run and import can create different module instances in the same kernel.
# Keep the hardware owner shared between those instances.
_STATE = sys.modules.setdefault("_ac820_lanuch_state", types.ModuleType("_ac820_lanuch_state"))
if not hasattr(_STATE, "app"):
    _STATE.app = None


def _find_root(root=None):
    result = Path(root).expanduser().resolve() if root is not None else Path(__file__).resolve().parents[1]
    if not (result / "src/trash_pynq").is_dir():
        raise RuntimeError("Project root must contain src/trash_pynq: " + str(result))
    return result


def _load_stages(root):
    notebook = json.loads((root / _NOTEBOOK).read_text(encoding="utf-8"))
    stages = {}
    for stage in _STAGES:
        matches = [cell for cell in notebook["cells"]
                   if cell.get("cell_type") == "code" and
                   "ricevision:" + stage in cell.get("metadata", {}).get("tags", [])]
        if len(matches) != 1:
            raise RuntimeError("Need exactly one ricevision:{} cell; found {}".format(stage, len(matches)))
        source = matches[0]["source"]
        source = source if isinstance(source, str) else "".join(source)
        # Check every stage before touching hardware, including async cleanup.
        stages[stage] = compile(source, str(root / _NOTEBOOK) + "#" + stage, "exec",
                                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT if stage == "cleanup" else 0)
    return stages


def _user_namespace():
    try:
        from IPython import get_ipython
        shell = get_ipython()
        return shell.user_ns if shell is not None else {}
    except ImportError:
        return {}


def _check_legacy_notebook():
    namespace = _user_namespace()
    if any(namespace.get(name) is not None for name in ("video", "ol")):
        raise RuntimeError("This kernel still owns an old notebook application. Run its cleanup cell "
                           "and wait for 'Stopped and released' before using lanuch.py.")


def _preflight(root, io_voltage, enable_model):
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise RuntimeError("Run on the PYNQ board as root, using its PYNQ Python environment.")
    source = str(root / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from trash_pynq.overlay import inspect_overlay
    from trash_pynq.model import validate_weights
    variant = {"3.3": "3v3", "1.8": "1v8"}[io_voltage]
    manifest = inspect_overlay(root / "board/overlays" / variant)
    if manifest.get("io_voltage") != io_voltage:
        raise ValueError("Overlay voltage does not match the requested I/O bank voltage")
    if enable_model:
        validate_weights(root / "data/trash_weight")
    return manifest


def _apply_touch_fix(root, check_only=False):
    project_script = root / "board/linux/touch_fix/ac820-touch-pinctrl.py"
    candidates = (project_script, Path("/usr/local/sbin/ac820-touch-pinctrl.py"))
    script = next((path for path in candidates if path.is_file()), None)
    if script is None:
        raise RuntimeError("Touch pinctrl helper is missing: " + str(project_script))
    spec = importlib.util.spec_from_file_location("_ac820_touch_pinctrl", str(script))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    local_dtbo = project_script.parent / "gt911_pads_fix.dtbo"
    if local_dtbo.is_file():
        helper.DTBO = local_dtbo
    helper.apply_fix(check_only=check_only)


def _acquire_lock():
    import fcntl
    lock = open(_LOCK_PATH, "a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError("Another launcher owns AC820 hardware. Stop that application first; "
                           "do not delete the lock file or run competing notebooks.") from None
    except BaseException:
        lock.close()
        raise
    lock.seek(0)
    lock.truncate()
    lock.write(str(os.getpid()) + "\n")
    lock.flush()
    return lock


def _validate_options(io_voltage, browser_fps):
    if io_voltage not in ("3.3", "1.8"):
        raise ValueError("io_voltage must match the physical bank: '3.3' or '1.8'")
    if not math.isfinite(browser_fps) or browser_fps < 0:
        raise ValueError("browser_fps must be finite and nonnegative (0 disables web images)")


class Handle:
    """Own one preview task and its DMA allocations until cleanup succeeds."""
    def __init__(self, root, stages, lock):
        self.root, self._stages, self._lock = root, stages, lock
        self._ns = dict(__name__="_ac820_notebook_runtime", __file__=str(root / _NOTEBOOK),
                        _LAUNCH_ROOT=root, ol=None, video=None, camera=None, touch=None,
                        runner=None, kernels=None, weights={}, camera_bus=None,
                        touch_bus=None, task=None, running=False)
        self._cleanup_task = None
        self._cleanup_error = None
        self._last_error = None
        self._stopped = False
        self._original_request = None

    def status(self):
        """Return a JSON-compatible snapshot; reading status never touches PL."""
        task = self._ns.get("task")
        stopping = self._cleanup_task is not None and not self._cleanup_task.done()
        return dict(pid=os.getpid(), root=str(self.root),
                    running=bool(self._ns.get("running") and task is not None and not task.done()),
                    stopping=stopping, stopped=self._stopped,
                    io_voltage=self._ns.get("IO_VOLTAGE"),
                    browser_fps=self._ns.get("BROWSER_FPS", 0),
                    model=self._ns.get("runner") is not None,
                    touch=self._ns.get("touch") is not None,
                    light=bool(self._ns.get("light", False)),
                    saved_count=self._ns.get("saved_count", 0),
                    last_label=self._ns.get("last_label"),
                    last_ms=self._ns.get("last_ms"),
                    metrics=dict(self._ns.get("preview_metrics", {})),
                    error=str(self._last_error) if self._last_error else None,
                    cleanup_error=str(self._cleanup_error) if self._cleanup_error else None)

    def request(self, action):
        """Request detect/light/save, or stop and release all owned resources."""
        if action not in ("detect", "light", "save", "stop"):
            raise ValueError("action must be detect, light, save, or stop")
        if action == "stop":
            self._begin_stop()
            return
        if self._stopped or self._cleanup_task is not None or not self._ns.get("running"):
            raise RuntimeError("Application is stopping or stopped")
        self._original_request(action)

    def _preview_done(self, task):
        try:
            error = task.exception()
        except asyncio.CancelledError as exc:
            error = exc
        if error is not None:
            self._last_error = error
        if not self._stopped and self._cleanup_task is None:
            self._begin_stop()

    def _begin_stop(self):
        self._ns["running"] = False
        if self._stopped:
            return self._cleanup_task
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup())
            self._cleanup_task.add_done_callback(self._cleanup_done)
        return self._cleanup_task

    def _cleanup_done(self, task):
        # Retrieve failures even when Stop was clicked without an awaiter.
        try:
            error = task.exception()
        except asyncio.CancelledError as exc:
            error = exc
        if error is not None:
            print("Cleanup failed; keep this kernel/process alive. DMA buffers and the hardware "
                  "lock are retained. Retry await app.stop() after fixing the fault, or reboot "
                  "the board. Error: " + repr(error), file=sys.stderr)

    async def _cleanup(self):
        try:
            result = eval(self._stages["cleanup"], self._ns)
            if inspect.isawaitable(result):
                await result
            self._lock.close()  # only release ownership after DMA cleanup succeeded
        except BaseException as exc:
            self._cleanup_error = exc
            self._last_error = exc
            raise
        else:
            self._cleanup_error = None
            self._stopped = True
            self._lock = None
            if _STATE.app is self:
                _STATE.app = None

    async def stop(self):
        """Stop idempotently; cancellation of a caller cannot cancel DMA cleanup."""
        if self._stopped:
            return
        await asyncio.shield(self._begin_stop())


def get_app():
    """Return this process's owner, including one retaining resources after a fault."""
    return _STATE.app


async def stop():
    """Stop the current application, if any."""
    app = get_app()
    if app is not None:
        await app.stop()


def start(io_voltage="3.3", enable_model=True, enable_touch=True, autofocus=True,
          browser_fps=2.0, root=None):
    """Initialize and start preview inside a running asyncio loop (e.g. Jupyter).

    Calling start again returns the existing Handle. Use await app.stop() before
    changing options. On startup failure, cleanup runs asynchronously; await
    stop() before retrying. A failed cleanup keeps the owner and lock alive.
    """
    asyncio.get_running_loop()
    if get_app() is not None:
        return get_app()
    _validate_options(io_voltage, browser_fps)
    root = _find_root(root)
    stages = _load_stages(root)
    _check_legacy_notebook()
    _preflight(root, io_voltage, enable_model)
    app = Handle(root, stages, _acquire_lock())
    _STATE.app = app
    try:
        exec(stages["setup"], app._ns)
        app._ns.update(IO_VOLTAGE=io_voltage, ENABLE_TOUCH=enable_touch,
                       AUTOFOCUS=autofocus, ENABLE_LCD=True)
        if enable_touch:
            _apply_touch_fix(root)
        for stage in ("overlay", "peripherals"):
            exec(stages[stage], app._ns)
        if enable_model:
            exec(stages["model"], app._ns)
        exec(stages["preview"], app._ns)
        app._ns["BROWSER_FPS"] = float(browser_fps)
        app._original_request = app._ns["request_action"]
        app._ns["request_action"] = app.request
        app._ns["task"].add_done_callback(app._preview_done)
    except BaseException as exc:
        app._last_error = exc
        app._begin_stop()
        raise
    return app


def _in_notebook():
    try:
        from IPython import get_ipython
        shell = get_ipython()
        return shell is not None and shell.__class__.__name__ == "ZMQInteractiveShell"
    except ImportError:
        return False


async def _run_cli(args):
    loop = asyncio.get_running_loop()
    retry = asyncio.Event()
    app = None

    def request_stop():
        retry.set()
        owner = app or get_app()
        if owner is not None:
            owner.request("stop")

    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, request_stop)
    exit_code = 0
    timer = None
    try:
        app = start(**_start_options(args))
        if args.duration is not None:
            timer = loop.call_later(args.duration, request_stop)
        await asyncio.shield(app._ns["task"])
    except BaseException as exc:
        exit_code = 1
        print("Application stopped: " + repr(exc), file=sys.stderr)
    finally:
        if timer is not None:
            timer.cancel()
        app = app or get_app()
        while app is not None and not app._stopped:
            retry.clear()
            try:
                await app.stop()
            except BaseException:
                # Exiting would release CMA memory that a faulted DMA may own.
                # A subsequent SIGINT/SIGTERM retries cleanup; reboot is safe.
                exit_code = 1
                print("Process retained after cleanup failure. Fix the fault and press Ctrl+C "
                      "to retry cleanup, or reboot the board.", file=sys.stderr)
                await retry.wait()
    return exit_code


def _start_options(args):
    return dict(io_voltage=args.io_voltage, enable_model=not args.no_model,
                enable_touch=not args.no_touch, autofocus=not args.no_autofocus,
                browser_fps=args.browser_fps)


def main(argv=None):
    notebook = _in_notebook()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--io-voltage", choices=("3.3", "1.8"), default="3.3")
    parser.add_argument("--no-model", action="store_true")
    parser.add_argument("--no-touch", action="store_true")
    parser.add_argument("--no-autofocus", action="store_true")
    parser.add_argument("--browser-fps", type=float, default=2.0 if notebook else 0.0)
    parser.add_argument("--check", action="store_true", help="read-only checks, without downloading PL")
    parser.add_argument("--duration", type=float, help="stop after this many seconds (CLI test)")
    args = parser.parse_args(argv)
    _validate_options(args.io_voltage, args.browser_fps)
    if args.duration is not None and (not math.isfinite(args.duration) or args.duration <= 0):
        parser.error("--duration must be finite and positive")
    print("Jupyter: http://<board-ip>:9090/notebooks/fpga_competition/pynq/board/00_one_click_start.ipynb")
    if args.check:
        root = _find_root()
        _load_stages(root)
        manifest = _preflight(root, args.io_voltage, not args.no_model)
        if not args.no_touch:
            _apply_touch_fix(root, check_only=True)
        print(json.dumps(dict(check="passed", part=manifest["part"], io_voltage=args.io_voltage,
                              model=not args.no_model, touch=not args.no_touch)))
        return None if notebook else 0
    if notebook:
        app = start(**_start_options(args))
        if args.duration is not None:
            asyncio.get_running_loop().call_later(args.duration, app.request, "stop")
        print("Application started. Use app.status(), app.request('detect'), or await app.stop().")
        return app
    return asyncio.run(_run_cli(args))


if __name__ == "__main__":
    if _in_notebook():
        app = main()
    else:
        sys.exit(main())
