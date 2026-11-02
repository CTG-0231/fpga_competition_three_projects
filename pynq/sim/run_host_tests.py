"""Run local tests without PYNQ hardware; store results outside the submission."""
import argparse
import contextlib
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output == ROOT.parent or ROOT.parent in output.parents:
        parser.error('output-dir must be outside the submission tree')
    output.mkdir(parents=True, exist_ok=False)
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT/'src'), str(ROOT/'sim')]
    suite = unittest.defaultTestLoader.discover(str(ROOT/'sim'), pattern='test_*.py')
    start = time.monotonic()
    with (output/'host_tests.log').open('w', encoding='utf-8') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    report = dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                  skipped=[dict(test=str(test), reason=reason) for test, reason in result.skipped],
                  passed=result.wasSuccessful(), seconds=round(time.monotonic()-start, 3),
                  board_accessed=False, hls_arithmetic_emulated=False)
    (output/'host_tests.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
