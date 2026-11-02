"""Build the standalone compatibility application in a new external workspace.

This produces a bare-metal boot image. It is not a PYNQ SD-card image.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--xsa', required=True, type=Path)
    parser.add_argument('--vitis', required=True, type=Path,
                        help='2025.2 Vitis installation directory, containing bin/vitis.bat')
    args = parser.parse_args()
    work, xsa, vitis = (p.resolve() for p in (args.workspace, args.xsa, args.vitis))
    if work.exists():
        parser.error('Workspace must be new; existing work is never overwritten.')
    if work == ROOT or ROOT in work.parents:
        parser.error('Use an external workspace outside the submission directory.')
    executable = vitis / 'bin/vitis.bat'
    if not executable.is_file() or not xsa.is_file():
        parser.error('Vitis executable or source XSA is missing.')
    with ZipFile(xsa) as archive:
        names = archive.namelist()
        hwhs = [n for n in names if n.endswith('.hwh')]
        if len(hwhs) != 1 or len([n for n in names if n.endswith('.bit')]) != 1:
            parser.error('XSA must contain one HWH and one bitstream.')
        version = ET.fromstring(archive.read(hwhs[0])).get('VIVADOVERSION', '')
        if not version.startswith('2025.2'):
            parser.error('This migration build requires an actual Vivado 2025.2 XSA.')
    hidden = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    version_result = subprocess.run([str(executable), '-v'], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, errors='replace',
                                    creationflags=hidden)
    # The Windows 2025.2 launcher returns 1 for a successful `-v` query.
    # Validate its actual product/version banner, and still reject error text.
    if (version_result.returncode not in (0, 1)
            or not re.search(r'^\*+ Vitis v2025\.2 \(64-bit\)',
                             version_result.stdout, re.MULTILINE)
            or re.search(r'\[ERROR\]|Traceback|not recognized', version_result.stdout)):
        parser.error('The selected Vitis command did not report version 2025.2.')
    work.mkdir(parents=True)
    (work / 'tool_version.log').write_text(version_result.stdout, encoding='utf-8')
    shutil.copytree(ROOT / 'src/vitis/app_src', work / 'app_src')
    scripts = ROOT / 'src/vitis/scripts'
    env = dict(os.environ, FPGA_VITIS_WORK=str(work), FPGA_VITIS_INSTALL=str(vitis),
               FPGA_HW_XSA=str(xsa))
    launch_options = {'creationflags': hidden}
    def vitis_stage(script):
        return [str(executable), '-s', str(script)]
    if os.name == 'nt':
        # The SDK server decodes cmd diagnostics as UTF-8. A no-console child
        # otherwise emits Chinese Windows messages in CP936 and crashes the
        # client before platform creation. Change only this hidden child console.
        wrapper = work / 'run_vitis_utf8.cmd'
        wrapper.write_text('@echo off\nchcp 65001 >nul\n'
                           'call "%FPGA_VITIS_INSTALL%\\bin\\vitis.bat" -s "%~1"\n'
                           'exit /b %errorlevel%\n', encoding='ascii')
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        launch_options = {'creationflags': subprocess.CREATE_NEW_CONSOLE,
                          'startupinfo': startup}
        def vitis_stage(script):
            return [os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c',
                    str(wrapper), str(script)]
    stages = [
        ('platform', vitis_stage(scripts / 'create_platform.py'),
         'PLATFORM_BUILD_COMPLETED'),
        ('app', vitis_stage(scripts / 'build_app.py'),
         'APPLICATION_BUILD_COMPLETED'),
        ('verify', [sys.executable, '-I', '-X', 'utf8', '-B', str(scripts / 'verify_build.py')], '"PASS"'),
        ('package', [sys.executable, '-I', '-X', 'utf8', '-B', str(scripts / 'package_boot.py')],
         'BOOT_PACKAGE_CREATED'),
    ]
    result = {'state': 'running', 'source_xsa_sha256': hashlib.sha256(xsa.read_bytes()).hexdigest(),
              'hardware_version': version, 'hardware_tested': False, 'stages': []}
    status = work / 'build_status.json'
    try:
        for name, command, marker in stages:
            started = time.time()
            result['current_stage'] = name
            status.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            log = work / ('build_' + name + '.log')
            with log.open('w', encoding='utf-8') as stream:
                run = subprocess.run(command, cwd=work, env=env, stdout=stream,
                                     stderr=subprocess.STDOUT, **launch_options)
            content = log.read_text(encoding='utf-8', errors='replace')
            if os.name == 'nt' and name in ('platform', 'app'):
                # Check the exact port recorded by this stage, never all Java
                # processes. Release the SDK's orphan before reusing workspace.
                ports = re.findall(r"Vitis Server started on port '(\d+)'", content)
                for port in set(ports):
                    cleanup = subprocess.run([
                        str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
                        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                        str(ROOT / 'build/stop_owned_vitis_server.ps1'),
                        '-ServerPort', port, '-VitisInstall', str(vitis)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        creationflags=hidden, text=True, errors='replace')
                    (work / ('cleanup_' + name + '.log')).write_text(cleanup.stdout, encoding='utf-8')
                    if cleanup.returncode:
                        raise RuntimeError('Unable to release the owned Vitis server; inspect cleanup log')
            success = run.returncode == 0 and marker in content
            if name in ('platform', 'app') and re.search(
                    r'Traceback \(most recent call last\)|\[ERROR\]|build failed\.|FAILED:', content):
                success = False
            result['stages'].append({'name': name, 'exit_code': run.returncode,
                                     'passed': success, 'elapsed_seconds': round(time.time() - started, 3)})
            if not success:
                raise RuntimeError('Stage {} failed; inspect {}'.format(name, log))
            print(name + ': PASS', flush=True)
        result['state'] = 'passed'
    except BaseException as exc:
        result['state'] = 'failed'
        result['error'] = str(exc)
        raise
    finally:
        status.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
