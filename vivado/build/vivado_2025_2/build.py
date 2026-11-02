"""Build the AC820 PL with Vivado 2025.2 and four actual 2025.2 HLS exports.

Restore native source snapshots outside this submission tree first. All native
tool output is confined to a new external workspace; original input trees are
read only. No board, SD card, installer or global environment is modified.
"""
import argparse
import ctypes
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prepare_inputs import digest, inspect_ip, prepare_new, within

SUBMISSION = HERE.parents[1]


def now():
    return datetime.datetime.now().astimezone().isoformat()


def alive(pid):
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied is not proof of exit.
        code = ctypes.c_ulong()
        try:
            return bool(kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def refuse_live_workspace(work):
    status = work / 'build_status.json'
    if status.is_file():
        record = json.loads(status.read_text(encoding='utf-8-sig'))
        # A terminated Python launcher can record interrupted/failed while its
        # child still generates the design, before native run markers exist.
        for key in ('helper_pid', 'launcher_pid', 'child_pid'):
            pid = record.get(key)
            if pid and int(pid) != os.getpid() and alive(pid):
                raise RuntimeError('Workspace still has an active recorded process, PID ' + str(pid))
    for marker in (work / 'r/p/leaf.runs').glob('*/.vivado.begin.rst'):
        if marker.with_name('.vivado.end.rst').exists() or marker.with_name('.vivado.error.rst').exists():
            continue
        for item in ET.parse(marker).getroot().iter():
            for key, value in item.attrib.items():
                if key.lower() == 'pid' and value.isdigit() and alive(int(value)):
                    raise RuntimeError('Native run PID is still alive: ' + value)


def verify_resume_sources(prepared, native, ip_root):
    manifest = json.loads((prepared / 'prepare_manifest.json').read_text())
    if digest(native / 'trash.xpr') != manifest['source_xpr_sha256']:
        raise ValueError('Native project changed; use a new workspace')
    sources = {'inputs/bd/design_1.bd': native / 'trash.srcs/sources_1/bd/design_1/design_1.bd',
               'inputs/rtl/rgb888_to_rgb565.v': native / 'trash.srcs/sources_1/new/RGB888toRGB565.v',
               'inputs/constraints/trash.xdc': native / 'trash.srcs/constrs_1/new/Trash.xdc'}
    for key, path in sources.items():
        if digest(path) != manifest['files'][key]:
            raise ValueError('Native source changed; use a new workspace: ' + str(path))
    ips, _ = inspect_ip(ip_root)
    for core, item in ips.items():
        for name in ['component.xml'] + item['files']:
            expected = manifest['files']['ip_repo/' + core + '/' + name]
            if digest(item['component'].parent / name) != expected:
                raise ValueError('HLS export changed; use a new workspace: ' + core + '/' + name)
    return manifest


def preserve_attempt(work):
    attempts = work / 'attempts' / datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    attempts.mkdir(parents=True)
    for folder in (work / 'r/p/leaf.runs').glob('*'):
        if not folder.is_dir() or (folder / '.vivado.end.rst').exists():
            continue
        for source in folder.iterdir():
            if source.is_file() and source.suffix.lower() in ('.log', '.rpt', '.tcl', '.rst'):
                target = attempts / folder.name / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    return attempts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-project', required=True, type=Path)
    p.add_argument('--hls-ip-root', required=True, type=Path,
                   help='Exactly four component.xml exports; duplicate VLNVs are rejected')
    p.add_argument('--workspace', required=True, type=Path)
    p.add_argument('--vivado', type=Path, help='2025.2 vivado executable or Windows vivado.bat')
    p.add_argument('--python', default=sys.executable, type=Path)
    p.add_argument('--timing-xdc', type=Path, help='Only add externally reviewed timing constraints')
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--resume', action='store_true', help='Keep source identity; reject live native run PIDs')
    args = p.parse_args()
    native, ip_root, work = [v.resolve() for v in (args.native_project, args.hls_ip_root, args.workspace)]
    for source in (native, ip_root, SUBMISSION):
        if within(work, source) or within(source, work):
            p.error('Native workspace must be outside source/submission trees and must not contain them')
    prepared, result = work / 'prepared', work / 'r'
    if args.resume:
        if not prepared.is_dir():
            p.error('--resume requires this entrypoint\'s existing prepared directory')
        refuse_live_workspace(work)
        manifest = verify_resume_sources(prepared, native, ip_root)
        preserve_attempt(work)
    else:
        if work.exists() and any(work.iterdir()):
            p.error('Use a new empty external workspace, or --resume for an unchanged stopped build')
        work.mkdir(parents=True, exist_ok=True)
        manifest = prepare_new(native, ip_root, prepared, args.timing_xdc)
    if args.prepare_only:
        print(json.dumps({'status': 'PREPARED_NOT_COMPILED', 'prepared': str(prepared)}))
        return 0
    vivado = args.vivado or (Path(shutil.which('vivado')) if shutil.which('vivado') else None)
    if vivado is None or not vivado.is_file():
        p.error('Pass --vivado for the installed Vivado 2025.2 executable')
    mode = 'resume' if (result / 'p/leaf.xpr').is_file() else 'migrate'
    script = HERE / ('resume.tcl' if mode == 'resume' else 'migrate.tcl')
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log, console = work / ('vivado_' + stamp + '.log'), work / ('console_' + stamp + '.log')
    env = os.environ.copy()
    env['XILINX_LOCAL_USER_DATA'] = 'no'
    env['FPGA_PYTHON'] = str(args.python.resolve())
    if os.name == 'nt':
        powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        command = [str(powershell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(HERE / 'invoke_vivado.ps1'),
                   '-Vivado', str(vivado.resolve()), '-Script', str(script), '-Log', str(log), '-Prepared', str(prepared),
                   '-Result', str(result), '-NativeProject', str(native), '-Mode', mode]
    else:
        native_args = [str(result), str(native)] if mode == 'resume' else [str(prepared), str(result), str(native), 'all']
        command = [str(vivado), '-mode', 'batch', '-nojournal', '-log', str(log), '-source', str(script), '-tclargs'] + native_args
    record = {'state': 'running', 'start_time': now(), 'launcher_pid': os.getpid(), 'mode': mode,
              'workspace': str(work), 'vivado_log': str(log), 'console_log': str(console),
              'hls_policy': manifest['logic_policy'], 'board_tested': False,
              'validation_limit': 'PL build only. Retain separate HLS cosim, timing-coverage and physical-board evidence.'}
    status_file = work / 'build_status.json'
    try:
        with console.open('wb') as output:
            process = subprocess.Popen(command, cwd=work, env=env, stdout=output, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            record['child_pid'] = process.pid
            status_file.write_text(json.dumps(record, indent=2) + '\n')
            code = process.wait()
        record['native_exit_code'] = code
        text = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
        success = code == 0 and not re.search(r'^ERROR:', text, re.M) and 'VIVADO_2025_2_BUILD_COMPLETED' in text and (result / 'leaf.xsa').is_file()
        record['state'] = 'completed' if success else 'failed'
        return 0 if success else 1
    finally:
        if record['state'] == 'running':
            record['state'] = 'interrupted_or_launcher_error'
        record['end_time'] = now()
        status_file.write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps(record))


if __name__ == '__main__':
    raise SystemExit(main())
