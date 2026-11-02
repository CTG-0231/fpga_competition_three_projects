"""Generate a source-controlled PYNQ bring-up/demo notebook without outputs."""
import json
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
cells=[]


def add(kind, source):
    cell={'cell_type':kind,'metadata':{},'source':dedent(source).strip()+'\n'}
    if kind=='code':
        cell.update(execution_count=None,outputs=[])
    cells.append(cell)


add('markdown', '''
# AC820 · RiceVision

依次执行：只读盘点 → 确认实物电压 → Overlay → 摄像头/LCD → 权重 → 界面。
本 Notebook 尚未进行 PYNQ 板级验证。按队伍要求复用已实测的原始 HLS/IP/bitstream，
不修改计算核心。摄像头与 LCD 可以先独立联调。请先阅读 `README.md` 和
`report/hardware_audit.md`。设备树缺少 I²C 时先完成 Linux 集成。
''')
add('code', '''
if globals().get('ol') is not None:
    raise RuntimeError('Run the cleanup cell before reinitializing the application')
from pathlib import Path
import sys, json, time, asyncio, io
import numpy as np
for candidate in (Path.cwd(), *Path.cwd().parents):
    if (candidate/'src/trash_pynq').is_dir():
        ROOT=candidate
        break
else:
    raise RuntimeError('Run this notebook inside the unpacked pynq_port folder')
sys.path.insert(0,str(ROOT/'src'))
from trash_pynq.overlay import inspect_overlay, load_overlay
from trash_pynq.model import LABELS, load_weights, preprocess_bgr, MobileNetRunner
from trash_pynq.kernels import Kernels
from trash_pynq.peripherals import LinuxI2C, OV5640, VideoDMA, GT911, make_ps_gpio_factory, raw_mmio
from trash_pynq.ui import LeafUI
from pynq import allocate

BOARD='ac820'
IO_VOLTAGE=None  # Set '3.3' or '1.8' from the ACTUAL board bank voltage, not its filename.
OVERLAY_DIR=None  # e.g. 'board/overlays/rebuilt' after validating a 2025.2 export
ENABLE_LCD=True
ENABLE_TOUCH=True
AUTOFOCUS=True
WEIGHTS=ROOT/'data/trash_weight'
ol=video=camera=touch=runner=kernels=None
weights={}
camera_bus=touch_bus=None
running=False
task=None
''')
add('code', '''
# Read-only: this does not load PL or modify the board.
import subprocess
subprocess.run([sys.executable,str(ROOT/'build/doctor.py')],check=False)
''')
add('code', '''
if IO_VOLTAGE not in ('3.3','1.8'):
    raise ValueError('First set IO_VOLTAGE to match the actual AC820 I/O bank')
variant={'3.3':'3v3','1.8':'1v8'}[IO_VOLTAGE]
overlay_dir=Path(OVERLAY_DIR) if OVERLAY_DIR is not None else ROOT/'board/overlays'/variant
if not overlay_dir.is_absolute():
    overlay_dir=ROOT/overlay_dir
manifest=inspect_overlay(overlay_dir)
ol=load_overlay(overlay_dir,BOARD,IO_VOLTAGE)
print('Loaded',manifest['part'],manifest['source_xsa'])
print('IPs:',sorted(ol.ip_dict))
''')
add('code', '''
# I2C adapters are matched by PS controller address, never guessed by bus number.
camera_bus=LinuxI2C.for_ps_controller(1)
camera=OV5640(camera_bus)
camera.initialize(autofocus=AUTOFOCUS)
video=VideoDMA(raw_mmio(ol,'axi_vdma_0'),ol.ip_dict['axi_vdma_0']['parameters'])
video.start_capture()
raw=video.read_frame()
print('Captured:',raw.shape,raw.dtype,'range',int(raw.min()),int(raw.max()))
if ENABLE_LCD:
    video.start_display(ol.v_tc_0.mmio)
if ENABLE_TOUCH:
    try:
        touch_bus=LinuxI2C.for_ps_controller(0)
        touch=GT911(touch_bus,make_ps_gpio_factory(overlay_dir/'leaf.hwh'))
        touch.initialize()
    except (OSError, RuntimeError) as exc:
        # Optional touch input must not prevent camera/LCD debugging.
        if touch is not None:
            touch.close()
        if touch_bus is not None:
            touch_bus.close()
        touch=touch_bus=None
        print('Touch unavailable; use Jupyter buttons:',repr(exc))
''')
add('markdown', '''
## 推理初始化

保持原始 HLS/IP/bitstream，加载从 runs/rice/trash_weight 复制的真实权重。
预处理默认保持原摄像头 G×200/256；训练测试图的 RGB 文件应关闭这项传感器补偿。
''')
add('code', '''
weights=load_weights(WEIGHTS,allocate)
kernels=Kernels(ol,timeout=5.0)
runner=MobileNetRunner(kernels,allocate,weights)
print('Loaded',len(weights),'weight arrays')
''')
add('markdown', '''
## LCD 和浏览器同步演示

摄像头/屏幕可在未初始化推理时运行。浏览器与触摸屏共用 Detect、Light、Save 操作；
只有初始化成功的推理器才能识别。每次 Save 保存当前原始 BGR 帧和对应 Q10 输入，
便于复现。Stop 停止预览，再执行最后的清理单元。
''')
add('code', '''
import ipywidgets as widgets
from IPython.display import display
from PIL import Image
from trash_pynq.preview import PreviewPresenter

if task is not None and not task.done():
    raise RuntimeError('Stop the current preview before starting another')

ui=LeafUI()
preview=widgets.Image(format='jpeg',width=800,height=480)
# LCD has priority. Browser snapshots are independently limited to 2 FPS.
BROWSER_FPS=2.0
LCD_TARGET_FPS=15.0
presenter=PreviewPresenter(ui, video if ENABLE_LCD else None)
preview_metrics={}
message=widgets.Label(value='Ready')
actions=[widgets.Button(description=s) for s in ('Detect','Light','Save','Stop')]
pending_action=None
light=False
saved_count=0
last_label=None
last_ms=None

def request_action(action):
    global pending_action,running
    if action=='stop':
        running=False
    else:
        pending_action=action

for button,action in zip(actions,('detect','light','save','stop')):
    button.on_click(lambda _,action=action:request_action(action))

async def preview_loop():
    global pending_action,running,light,saved_count,last_label,last_ms
    status='Ready'
    next_browser=0.0
    last_message=0.0
    try:
        while running:
            cycle_started=time.monotonic()
            raw=video.read_frame()
            capture_done=time.monotonic()
            if touch is not None:
                points=touch.poll()
                if touch.just_pressed and len(points)==1:
                    pending_action=ui.hit_test(*points[0])
            action,pending_action=pending_action,None
            if action=='light':
                light=not light
                camera.set_light(light)
                status='Light on' if light else 'Light off'
            elif action=='save':
                target=ROOT/'data/captures'
                target.mkdir(parents=True,exist_ok=True)
                stem=str(time.time_ns())
                raw.tofile(str(target/(stem+'_bgr.bin')))
                preprocess_bgr(raw).astype('<i2').tofile(str(target/(stem+'_q10.bin')))
                (target/(stem+'.json')).write_text(json.dumps({'shape':[224,224,3],
                    'format':'BGR888','green_gain':[200,256],'last_label':last_label,
                    'last_label_is_from_this_frame':False},indent=2))
                saved_count+=1
                status='Frame saved'
            elif action=='detect':
                if runner is None:
                    status='Model unavailable'
                else:
                    kernels.trace.clear()
                    started=time.monotonic()
                    logits=runner.run(preprocess_bgr(raw))
                    last_ms=(time.monotonic()-started)*1000
                    last_label=LABELS[int(np.argmax(logits))]
                    status='Identified'
                    print({'label':last_label,'logits':logits.tolist(),'milliseconds':last_ms})
            frame=presenter.present(raw,label=last_label,latency_ms=last_ms,light=light,
                                    status=status,saved_count=saved_count)
            lcd_done=time.monotonic()
            now=lcd_done
            if BROWSER_FPS>0 and now>=next_browser:
                content=io.BytesIO()
                # RGB conversion in native Pillow is cheaper on the ARM CPU.
                Image.frombytes('RGB',(800,480),frame.tobytes(),'raw','BGR').save(
                    content,format='JPEG',quality=75)
                preview.value=content.getvalue()
                next_browser=time.monotonic()+1.0/BROWSER_FPS
            preview_metrics.update(capture_ms=(capture_done-cycle_started)*1000,
                ui_lcd_ms=(lcd_done-capture_done)*1000,lcd_fps=presenter.fps)
            if now-last_message>=1.0:
                message.value='{} | LCD {:.1f} FPS | capture {:.0f} ms'.format(
                    status,presenter.fps,preview_metrics['capture_ms'])
                last_message=now
            remaining=1.0/LCD_TARGET_FPS-(time.monotonic()-cycle_started)
            await asyncio.sleep(max(0.001,remaining))
    except BaseException as exc:
        message.value='Stopped: '+str(exc)
        print('Preview stopped. Keep this kernel alive; run cleanup/reset before releasing DMA buffers.',exc)
        raise
    finally:
        running=False

display(widgets.VBox([preview,widgets.HBox(actions),message]))
running=True
task=asyncio.create_task(preview_loop())
''')
add('code', '''
# Stop and release only after active DMA engines have halted.
running=False
if task is not None:
    try:
        await task
    except BaseException as exc:
        print('Preview task ended:',repr(exc))
if video is not None:
    video.close()  # on halt failure this raises and preserves its buffers
if camera is not None and camera.initialized:
    camera.set_light(False)
if touch is not None:
    touch.close()
for bus in (camera_bus,touch_bus):
    if bus is not None:
        bus.close()
if runner is not None:
    if runner._faulted or kernels.faulted:
        ol.download()  # if this fails, do not free/restart the Python kernel; reboot board
        runner.close(assume_hardware_stopped=True)
    else:
        runner.close()
for buffer in weights.values():
    buffer.freebuffer()
weights={}
ol=video=camera=touch=runner=kernels=None
camera_bus=touch_bus=None
task=None
print('Stopped and released')
''')

if __name__=='__main__':
    output=ROOT/'board/01_bringup_and_demo.ipynb'
    output.write_text(json.dumps({'cells':cells,'metadata':{
        'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
        'language_info':{'name':'python','version':'3.8'}},
        'nbformat':4,'nbformat_minor':4},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(output)
