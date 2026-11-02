"""Run a saved original-format input and record real board measurements."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
from trash_pynq.kernels import Kernels
from trash_pynq.model import (LABELS, NO_LEAF_THRESHOLD, MobileNetRunner,
                              classify, load_weights,
                              preprocess_bgr, validate_weights)
from trash_pynq.overlay import inspect_overlay, load_overlay


def read_input(path, input_format):
    path = Path(path)
    expected_bytes = 150528 if input_format == 'bgr-bin' else 301056
    if path.stat().st_size != expected_bytes:
        raise ValueError('{} requires exactly {} bytes'.format(input_format, expected_bytes))
    if input_format == 'bgr-bin':
        values = np.fromfile(str(path), dtype=np.uint8)
        if values.size != 224*224*3:
            raise ValueError('bgr-bin must contain exactly one 224x224 BGR888 frame (150528 bytes)')
        return preprocess_bgr(values.reshape(224,224,3))
    values = np.fromfile(str(path), dtype='<i2')
    if values.size != 3*224*224:
        raise ValueError('q10-bin must be one RGB CHW int16 frame (301056 bytes)')
    return values.reshape(3,224,224)


def read_golden(path):
    path = Path(path)
    if path.stat().st_size != 12:
        raise ValueError('Golden output must be exactly 12 bytes')
    values = np.fromfile(str(path), dtype='<i2')
    if values.size != 6:
        raise ValueError('Golden output must contain exactly six original int16 logits')
    return values


def reset_on_fault(overlay):
    """Reset PL before allowing an exiting process to relinquish active CMA."""
    try:
        overlay.download()
    except BaseException as exc:
        print('PL reset failed: {}. DMA buffers remain allocated. Power off the board before terminating this process.'.format(exc), file=sys.stderr, flush=True)
        # An exiting process releases CMA even if Python retains references.
        # Stay alive while a failed AXI master might still own those pages.
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                print('Power off the board first; then terminate this process from the host.', file=sys.stderr, flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board', required=True, choices=['ac820'])
    source=p.add_mutually_exclusive_group()
    source.add_argument('--variant', choices=['3v3','1v8'])
    source.add_argument('--overlay-dir', type=Path,
                        help='Use a newly exported bit/HWH/manifest directory')
    p.add_argument('--io-voltage', required=True, choices=['3.3','1.8'])
    p.add_argument('--weights', type=Path, default=ROOT/'data/trash_weight')
    p.add_argument('--input', required=True, type=Path)
    p.add_argument('--input-format', required=True, choices=['bgr-bin','q10-bin'])
    p.add_argument('--golden', type=Path)
    p.add_argument('--repeat', type=int, default=5)
    p.add_argument('--timeout', type=float, default=5.0)
    p.add_argument('--output', type=Path, default=ROOT/'report/board_run.json')
    args=p.parse_args()
    if args.repeat < 1 or args.repeat > 10000:
        p.error('--repeat must be between 1 and 10000')
    if args.variant is not None and {'3v3':'3.3','1v8':'1.8'}[args.variant] != args.io_voltage:
        p.error('--variant and --io-voltage disagree')
    directory=(args.overlay_dir if args.overlay_dir is not None else
               ROOT/'board/overlays'/({'3.3':'3v3','1.8':'1v8'}[args.io_voltage]))
    manifest=inspect_overlay(directory)
    image=read_input(args.input,args.input_format)
    golden=read_golden(args.golden) if args.golden else None
    validate_weights(args.weights)  # invalid assets fail before modifying PL
    from pynq import allocate
    from pynq import __version__ as pynq_version
    weights={}
    overlay=runner=kernels=None
    try:
        overlay=load_overlay(directory,args.board,args.io_voltage)
        # PYNQ 2.7 XRT allocation needs an already downloaded overlay. Re-read
        # and revalidate files here in case they changed since the preflight.
        weights=load_weights(args.weights,allocate)
        kernels=Kernels(overlay,args.timeout)
        runner=MobileNetRunner(kernels,allocate,weights)
        runner.run(image)  # warm-up excluded from statistics
        kernels.trace.clear()
        times=[]
        predictions=[]
        for _ in range(args.repeat):
            start=time.monotonic()
            scores=runner.run(image)
            times.append(time.monotonic()-start)
            predictions.append(scores.tolist())
        expected_ok=(all(np.array_equal(np.asarray(v,dtype=np.int16),golden)
                         for v in predictions) if golden is not None else None)
        differences=([int(np.max(np.abs(np.asarray(v,dtype=np.int32)-golden.astype(np.int32))))
                      for v in predictions] if golden is not None else None)
        report={
            'board':'ac820', 'part':manifest['part'], 'overlay_directory':str(directory),
            'io_voltage':args.io_voltage,
            'pynq_version':pynq_version, 'host':platform.platform(),
            'bit_sha256':manifest['files']['leaf.bit'],
            'hls_policy':manifest.get('hls_policy'),
            'input_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),
            'weight_sha256':{name:hashlib.sha256((args.weights/name).read_bytes()).hexdigest() for name in weights},
            'labels':LABELS, 'scores_int16':predictions,
            'prediction_indices':[int(np.argmax(v)) for v in predictions],
            'prediction_labels':[classify(v)[1] for v in predictions],
            'no_leaf_threshold':NO_LEAF_THRESHOLD,
            'repeat':args.repeat, 'warmup':1,
            'scope':'host-controlled PL inference; includes input copy, MMIO and cache sync; excludes capture/preprocess/display',
            'seconds':times, 'median_seconds':float(np.median(times)),
            'p95_seconds':float(np.percentile(times,95)),
            'median_inferences_per_second':1/float(np.median(times)),
            'golden_exact_match':expected_ok, 'golden_max_abs_diff':differences,
            'kernel_call_trace':kernels.trace,
            'cpu_baseline':'not_measured', 'accuracy_dataset':'not_measured',
        }
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print(json.dumps({k:report[k] for k in ['median_seconds','golden_exact_match',
                                            'prediction_indices','prediction_labels',
                                            'no_leaf_threshold']},indent=2))
        return 0 if expected_ok is not False else 3
    finally:
        if kernels is not None and (kernels.faulted or (runner is not None and runner._faulted)):
            reset_on_fault(overlay)
            if runner is not None:
                runner.close(assume_hardware_stopped=True)
        elif runner is not None:
            runner.close()
        for buffer in weights.values():
            buffer.freebuffer()


if __name__=='__main__':
    raise SystemExit(main())
