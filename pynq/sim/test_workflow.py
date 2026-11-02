import ast
import importlib.util
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('infer_file',str(ROOT/'board/infer_file.py'))
infer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(infer)


class WorkflowTests(unittest.TestCase):
    @staticmethod
    def _cli_arguments(weights, output):
        return ['infer_file.py','--board','ac820','--variant','3v3',
                '--io-voltage','3.3','--weights',str(weights),
                '--input',str(ROOT/'data/samples/original_infer_q10.bin'),
                '--input-format','q10-bin','--repeat','1','--output',str(output)]

    def test_int16_files_reject_odd_trailing_bytes(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT/'sim')) as tmp:
            path=Path(tmp)/'bad.bin'
            path.write_bytes(bytes(301057))
            with self.assertRaises(ValueError):
                infer.read_input(path,'q10-bin')
            path.write_bytes(bytes(13))
            with self.assertRaises(ValueError):
                infer.read_golden(path)

    def test_notebook_code_syntax_and_no_fabricated_outputs(self):
        notebook=json.loads((ROOT/'board/01_bringup_and_demo.ipynb').read_text(encoding='utf-8'))
        for index,cell in enumerate(notebook['cells']):
            if cell['cell_type']=='code':
                self.assertEqual(cell['outputs'],[])
                source=cell['source']
                if isinstance(source,list):
                    source=''.join(source)
                ast.parse(source,feature_version=(3,8))
                compile(source,'notebook_cell_'+str(index),'exec',flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)

    def test_all_python_sources_target_python_38(self):
        for path in (ROOT/'src/trash_pynq').glob('*.py'):
            ast.parse(path.read_text(encoding='utf-8'),feature_version=(3,8))

    def test_notebook_reentry_preserves_existing_handles(self):
        notebook=json.loads((ROOT/'board/01_bringup_and_demo.ipynb').read_text(encoding='utf-8'))
        first=next(cell['source'] for cell in notebook['cells'] if cell['cell_type']=='code')
        if isinstance(first,list):
            first=''.join(first)
        handles={name:object() for name in ('ol','video','camera','touch','runner','kernels',
                                          'camera_bus','touch_bus','task')}
        handles['weights']={'keep':object()}
        handles['running']=True
        namespace=dict(handles)
        with self.assertRaisesRegex(RuntimeError,'cleanup cell'):
            exec(compile(first,'notebook_first_cell','exec'),namespace)
        for name,original in handles.items():
            self.assertIs(namespace[name],original,name+' was reset before rejecting reentry')

    def test_notebook_generator_has_no_live_application_guard(self):
        generated=runpy.run_path(str(ROOT/'build/make_notebook.py'),
                                init_globals={'ol':object()},run_name='generator_import')
        self.assertTrue(generated['cells'])

    def test_cli_downloads_overlay_before_xrt_allocation(self):
        events=[]

        class Buffer(np.ndarray):
            def flush(self):
                pass

            def freebuffer(self):
                events.append('free')

        def allocate(shape,dtype):
            if 'download' not in events:
                raise RuntimeError('Overlay is not downloaded')
            events.append('allocate')
            return np.empty(shape,dtype=dtype).view(Buffer)

        def download(*args):
            events.append('download')
            return object()

        class Kernels:
            faulted=False

            def __init__(self,*args):
                self.trace=[]

        class Runner:
            _faulted=False

            def __init__(self,kernels,allocator,weights):
                self.weights=weights

            def run(self,image):
                return np.arange(6,dtype=np.int16)

            def close(self):
                events.append('close')

        fake_pynq=types.SimpleNamespace(allocate=allocate,__version__='2.7.0')
        with tempfile.TemporaryDirectory(dir=str(ROOT/'sim')) as tmp:
            arguments=self._cli_arguments(ROOT/'data/trash_weight',Path(tmp)/'run.json')
            with patch.dict(sys.modules,{'pynq':fake_pynq}), \
                    patch.object(sys,'argv',arguments), \
                    patch.object(infer,'load_overlay',side_effect=download), \
                    patch.object(infer,'Kernels',Kernels), \
                    patch.object(infer,'MobileNetRunner',Runner), \
                    patch.object(infer.time,'monotonic',side_effect=[10.0,10.01]), \
                    patch('builtins.print'):
                self.assertEqual(infer.main(),0)
        self.assertEqual(events[0],'download')
        self.assertEqual(events.count('allocate'),106)
        self.assertEqual(events.count('free'),106)

    def test_cli_rejects_missing_or_invalid_weights_before_pl_download(self):
        allocate=Mock(side_effect=AssertionError('preflight must not allocate'))
        fake_pynq=types.SimpleNamespace(allocate=allocate,__version__='2.7.0')
        with tempfile.TemporaryDirectory(dir=str(ROOT/'sim')) as tmp:
            directory=Path(tmp)/'weights'
            directory.mkdir()
            arguments=self._cli_arguments(directory,Path(tmp)/'run.json')
            with patch.dict(sys.modules,{'pynq':fake_pynq}), \
                    patch.object(sys,'argv',arguments), \
                    patch.object(infer,'load_overlay') as download:
                with self.assertRaisesRegex(ValueError,'missing'):
                    infer.main()
                download.assert_not_called()
                allocate.assert_not_called()
                shutil.copytree(ROOT/'data/trash_weight',directory,dirs_exist_ok=True)
                for value,diagnostic in ((np.nan,'NaN'),(32.0,'range')):
                    with self.subTest(value=value):
                        np.full(32,value,dtype='<f4').tofile(str(directory/'head.bc1.bin'))
                        with self.assertRaisesRegex(ValueError,diagnostic):
                            infer.main()
                        download.assert_not_called()
                        allocate.assert_not_called()

    def test_cli_revalidates_files_changed_after_preflight(self):
        allocate=Mock(side_effect=AssertionError('changed weights must not allocate'))
        fake_pynq=types.SimpleNamespace(allocate=allocate,__version__='2.7.0')
        with tempfile.TemporaryDirectory(dir=str(ROOT/'sim')) as tmp:
            directory=Path(tmp)/'weights'
            shutil.copytree(ROOT/'data/trash_weight',directory)

            def download(*args):
                np.full(32,np.nan,dtype='<f4').tofile(str(directory/'head.bc1.bin'))
                return object()

            arguments=self._cli_arguments(directory,Path(tmp)/'run.json')
            with patch.dict(sys.modules,{'pynq':fake_pynq}), \
                    patch.object(sys,'argv',arguments), \
                    patch.object(infer,'load_overlay',side_effect=download) as downloaded:
                with self.assertRaisesRegex(ValueError,'NaN'):
                    infer.main()
                downloaded.assert_called_once()
                allocate.assert_not_called()


if __name__=='__main__':
    unittest.main()
