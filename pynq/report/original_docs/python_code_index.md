# Python 完整源码索引

本索引列出工程内全部 Python 源文件、模块级函数与类方法，包含 `_` 开头的内部项。面向调用的参数说明与示例请先看 [API_REFERENCE_CN.md](API_REFERENCE_CN.md)；内部项可能依赖对象状态，完整实现保留在对应源码中。

生成范围排除 Vivado 生成的 `build/work`、缓存和备份目录；Notebook 定义的控制函数另列。

共 30 个 Python 文件，257 个模块级函数与类方法（包含内部实现及测试函数）。
## board/infer_file.py

[查看完整源码](board/infer_file.py)

```python
  19  read_input(path, input_format)
  35  read_golden(path)
  45  reset_on_fault(overlay)
  60  main()
```

## board/linux/touch_fix/ac820-touch-pinctrl.py

[查看完整源码](board/linux/touch_fix/ac820-touch-pinctrl.py)

```python
  31  read_mio()
  44  format_mio(values)
  49  overlay_status()
  55  require_gpio_idle()
  68  bound_drivers()
  82  rebind_all(detached)
  98  apply_fix(check_only=False)
 152  interrupted(signum, _frame)
 156  main()
```

## build/doctor.py

[查看完整源码](build/doctor.py)

```python
  14  main()
```

## build/export_overlay.py

[查看完整源码](build/export_overlay.py)

```python
  12  sha256(data)
  16  bit_part(data)
  37  export(xsa, output, io_voltage=None)
```

## build/inspect_boot_image.py

[查看完整源码](build/inspect_boot_image.py)

```python
  14  main()
```

## build/inspect_fdt.py

[查看完整源码](build/inspect_fdt.py)

```python
  21  parse_fdt(blob)
  76  string(value)
  80  cells(value)
  84  describe(value)
  98  summarize_tree(tree)
 144  decompress_candidate(payload, offset, algorithm)
 158  inspect_kernel(payload, fit_compression)
 199  inspect(path)
 252  main()
```

## build/make_notebook.py

[查看完整源码](build/make_notebook.py)

```python
  10  add(kind, source)
```

## build/package_release.py

[查看完整源码](build/package_release.py)

```python
  11  selected_files()
```

## build/prepare_vivado.py

[查看完整源码](build/prepare_vivado.py)

```python
  22  digest(path)
  26  within(path, parent)
  34  inspect_ip(root)
  70  prepare(project_root, ip_root, output, timing_xdc=None, target_version='2025.2')
```

## build/reference/check_components.py

[查看完整源码](build/reference/check_components.py)

```python
  23  check(compiler, include)
```

## build/repack_fit.py

[查看完整源码](build/repack_fit.py)

```python
  22  sha256(data)
  26  require_cstring(value, description)
  32  validate_fit(tree)
  74  selected_images(tree)
  94  write_its(tree, work_dir)
 137  verify_properties(original, compiled, expected_changes)
 158  repack(source_fit, merged_dtb, dtc, output_dir, work_dir=None)
 250  main()
```

## build/test_host.py

[查看完整源码](build/test_host.py)

此文件没有模块级函数或类方法；请查看其常量、配置或命令行执行体。

## build/validate_boot_dtb.py

[查看完整源码](build/validate_boot_dtb.py)

```python
  19  require(condition, message)
  24  reservations(blob, tree)
  36  validate(base, migrated)
  80  main()
```

## data/peripherals/extract_from_vitis.py

[查看完整源码](data/peripherals/extract_from_vitis.py)

```python
  12  initializer(source, symbol)
  21  extract(source_dir, destination)
```

## lanuch.py

[查看完整源码](lanuch.py)

```python
  32  _find_root(root=None)
  39  _load_stages(root)
  56  _user_namespace()
  65  _check_legacy_notebook()
  72  _preflight(root, io_voltage, enable_model)
  89  _apply_touch_fix(root, check_only=False)
 104  _acquire_lock()
 123  _validate_options(io_voltage, browser_fps)
 130  class Handle
 132  Handle.__init__(self, root, stages, lock)
 144  Handle.status(self)
 163  Handle.request(self, action)
 174  Handle._preview_done(self, task)
 184  Handle._begin_stop(self)
 193  Handle._cleanup_done(self, task)
 204  async Handle._cleanup(self)
 221  async Handle.stop(self)
 228  get_app()
 233  async stop()
 240  start(io_voltage='3.3', enable_model=True, enable_touch=True, autofocus=True, browser_fps=2.0, root=None)
 280  _in_notebook()
 289  async _run_cli(args)
 330  _start_options(args)
 336  main(argv=None)
```

## sim/test_kernels.py

[查看完整源码](sim/test_kernels.py)

```python
   6  class Buffer
   7  Buffer.__new__(cls, size, address=16777216)
  13  Buffer.flush(self)
  16  Buffer.invalidate(self)
  20  class IP
  21  IP.__init__(self, done=True)
  26  IP.write(self, offset, value)
  31  IP.read(self, offset)
  35  class Overlay
  36  Overlay.__init__(self)
  41  class KernelTests
  42  KernelTests.test_pw_and_dw_match_bsp_register_writes(self)
  66  KernelTests.test_conv_fc_shortcut_and_cache_sync(self)
  77  KernelTests.test_reject_virtual_unaligned_outside_window_and_small(self)
  85  KernelTests.test_timeout_faults_and_pins_buffers(self)
```

## sim/test_model.py

[查看完整源码](sim/test_model.py)

```python
  25  _cleanup_completed_process_directory(temporary)
  38  class DeviceBuffer
  39  DeviceBuffer.__new__(cls, shape, dtype, address)
  47  DeviceBuffer.__array_finalize__(self, parent)
  55  DeviceBuffer.device_address(self)
  58  DeviceBuffer.flush(self)
  61  DeviceBuffer.freebuffer(self)
  65  class Allocator
  66  Allocator.__init__(self)
  69  Allocator.__call__(self, shape, dtype)
  75  class CheckedKernels
  77  CheckedKernels.__init__(self, fail_at=None)
  82  CheckedKernels._call(self, mode, *buffers)
  92  CheckedKernels.conv(self, inp, weight, bias, out)
 101  CheckedKernels.pw(self, inp, weight, bias, out, ch_in, ch_out, act, size)
 110  CheckedKernels.dw(self, inp, weight, bias, out, channel, size, stride)
 119  CheckedKernels.shortcut(self, inp1, inp2, out, length)
 126  CheckedKernels.fc(self, inp, weight, bias, out)
 135  synthetic_weights(allocator)
 145  class ModelTests
 146  ModelTests.test_preprocess_boundaries_channels_and_negative_truncation(self)
 160  ModelTests.test_preprocess_against_original_c_expressions_all_256_values(self)
 200  ModelTests.test_preprocess_rejects_ambiguous_input(self)
 208  ModelTests.test_configs_and_labels_match_original_sources(self)
 220  ModelTests.test_missing_weights_are_all_reported_before_allocation(self)
 230  ModelTests.test_weight_float32_conversion_and_validation(self)
 263  ModelTests.test_complete_schedule_shapes_reuse_and_cpu_owned_scores(self)
 292  ModelTests.test_dma_timeout_retains_buffers_until_explicit_reset_acknowledgment(self)
```

## sim/test_overlay.py

[查看完整源码](sim/test_overlay.py)

```python
  11  class OverlayTests
  12  OverlayTests.test_both_xsa_pairs_and_register_contract(self)
  18  OverlayTests.test_board_and_variant_checked_before_pynq_import(self)
  24  OverlayTests.test_corrupted_hwh_rejected(self)
```

## sim/test_peripherals.py

[查看完整源码](sim/test_peripherals.py)

```python
  26  class Buffer
  27  Buffer.__new__(cls, shape, address)
  33  Buffer.flush(self)
  36  Buffer.invalidate(self)
  39  Buffer.freebuffer(self)
  43  class MMIO
  44  MMIO.__init__(self)
  49  MMIO.read(self, address)
  52  MMIO.write(self, address, value)
  70  class Bus
  73  Bus.__init__(self)
  79  Bus.read_reg(self, address, register, length=1)
  82  Bus.write_reg(self, address, register, payload)
  94  class Pin
  95  Pin.__init__(self, number, direction, log)
  99  Pin.write(self, value)
 102  Pin.release(self)
 106  class PeripheralTests
 107  PeripheralTests.tearDown(self)
 111  PeripheralTests.test_original_data_extracts_byte_for_byte(self)
 129  PeripheralTests.test_camera_af_transfer_id_and_light(self)
 143  PeripheralTests.test_camera_wrong_id_and_unknown_clock_fail(self)
 155  PeripheralTests.test_discovery_matches_ps_address_and_frequency(self)
 166  PeripheralTests.test_linux_i2c_combined_transaction_structure(self)
 188  PeripheralTests.test_touch_reset_address_press_release_and_flip(self)
 204  PeripheralTests.test_gpio_factory_maps_only_mio0_and_emio0(self)
 226  PeripheralTests.test_touch_bad_count_acknowledged_and_state_cleared(self)
 237  PeripheralTests.test_lcd_bgr_and_rotation_and_fonts(self)
 248  PeripheralTests.test_vdma_snapshot_and_independent_channels(self)
 268  PeripheralTests.test_vdma_rejects_upper_cma_window(self)
 275  PeripheralTests.test_dma_halt_timeout_retains_target_globally(self)
 292  PeripheralTests.test_wrong_vdma_configuration_fails_before_io(self)
```

## sim/test_ui.py

[查看完整源码](sim/test_ui.py)

```python
  13  class UITests
  14  UITests.setUp(self)
  17  UITests.test_six_labels_render_without_mutating_camera(self)
  27  UITests.test_touch_targets_match_drawn_buttons_and_half_open_edges(self)
  35  UITests.test_output_rotation_is_exactly_once_and_render_is_independent(self)
  43  UITests.test_light_state_changes_only_the_light_button(self)
  52  UITests.test_invalid_image_or_prediction_fails(self)
  61  generate_previews()
```

## sim/test_workflow.py

[查看完整源码](sim/test_workflow.py)

```python
  21  class WorkflowTests
  23  WorkflowTests._cli_arguments(weights, output)
  29  WorkflowTests.test_int16_files_reject_odd_trailing_bytes(self)
  39  WorkflowTests.test_notebook_code_syntax_and_no_fabricated_outputs(self)
  48  WorkflowTests.test_all_python_sources_target_python_38(self)
  52  WorkflowTests.test_notebook_reentry_preserves_existing_handles(self)
  65  WorkflowTests.test_notebook_generator_has_no_live_application_guard(self)
  70  WorkflowTests.test_cli_downloads_overlay_before_xrt_allocation(self)
 123  WorkflowTests.test_cli_rejects_missing_or_invalid_weights_before_pl_download(self)
 146  WorkflowTests.test_cli_revalidates_files_changed_after_preflight(self)
```

## src/trash_pynq/__init__.py

[查看完整源码](src/trash_pynq/__init__.py)

此文件没有模块级函数或类方法；请查看其常量、配置或命令行执行体。

## src/trash_pynq/kernels.py

[查看完整源码](src/trash_pynq/kernels.py)

```python
   8  class KernelTimeout
  12  class Kernels
  13  Kernels.__init__(self, overlay, timeout=5.0)
  29  Kernels.address(buffer)
  45  Kernels._run(self, name, pointers, scalars, inputs, output)
  83  Kernels.conv(self, source, weight, bias, output)
  90  Kernels.pw(self, source, weight, bias, output, ch_in, ch_out, act, size)
 100  Kernels.dw(self, source, weight, bias, output, channel, size, stride)
 110  Kernels.shortcut(self, source1, source2, output, length)
 116  Kernels.fc(self, source, weight, bias, output)
```

## src/trash_pynq/model.py

[查看完整源码](src/trash_pynq/model.py)

```python
  16  class BlockConfig
  52  _exclusive(method)
  64  weight_specs()
  97  _free(buffer)
 102  _allocate_zeroed(allocator, count)
 113  _validated_weight_values(directory, retain_values)
 152  validate_weights(directory)
 161  load_weights(directory, allocator)
 185  preprocess_bgr(frame, green_gain_num=200, green_gain_den=256)
 208  class MobileNetRunner
 218  MobileNetRunner.__init__(self, kernels, allocator, weights)
 259  MobileNetRunner._weight(self, prefix, name)
 263  MobileNetRunner.run(self, image_q)
 321  MobileNetRunner.close(self, assume_hardware_stopped=False)
```

## src/trash_pynq/overlay.py

[查看完整源码](src/trash_pynq/overlay.py)

```python
  19  inspect_overlay(directory)
  57  load_overlay(directory, board, io_voltage)
```

## src/trash_pynq/peripherals.py

[查看完整源码](src/trash_pynq/peripherals.py)

```python
  25  class PeripheralError
  29  _data_dir(directory=None)
  35  load_data(name, directory=None)
  45  raw_mmio(overlay, name)
  60  class _I2CMessage
  65  class _I2CTransfer
  69  discover_ps_i2c(controller, sysfs='/sys/class/i2c-dev')
  92  class LinuxI2C
  98  LinuxI2C.__init__(self, bus, *, frequency_hz=None, dev_root='/dev')
 109  LinuxI2C.for_ps_controller(cls, controller, *, bus=None, sysfs='/sys/class/i2c-dev')
 115  LinuxI2C._ioctl(self, request, argument)
 122  LinuxI2C._transfer(self, address, payload, read_length=0)
 144  LinuxI2C.check_address(self, address)
 149  LinuxI2C.write_reg(self, address, register, payload)
 154  LinuxI2C.read_reg(self, address, register, length=1)
 159  LinuxI2C.close(self)
 164  LinuxI2C.__enter__(self)
 167  LinuxI2C.__exit__(self, *args)
 171  class OV5640
 174  OV5640.__init__(self, bus, *, data_dir=None, sleep=time.sleep, timeout=2.0)
 179  OV5640._write(self, register, payload)
 188  OV5640._read(self, register)
 194  OV5640._wait(self, register, expected)
 202  OV5640.initialize(self, *, autofocus=True)
 225  OV5640.initialize_autofocus(self)
 245  OV5640.focus(self)
 257  OV5640.release_focus(self)
 263  OV5640.set_light(self, enabled)
 270  OV5640.set_test_pattern(self, pattern=0)
 279  make_ps_gpio_factory(hwh_path)
 301  class GT911
 303  GT911.__init__(self, bus, gpio_factory, *, data_dir=None, flip=True, sleep=time.sleep)
 311  GT911.initialize(self)
 342  GT911.poll(self)
 373  GT911.close(self)
 382  class LCDFrame
 384  LCDFrame.__init__(self, *, flip=True, data_dir=None)
 389  LCDFrame._bgr(color)
 392  LCDFrame.clear(self, color=0)
 395  LCDFrame.rectangle(self, x, y, width, height, color)
 402  LCDFrame.picture(self, frame_bgr, x=352, y=16, scale=2)
 413  LCDFrame.text(self, x, y, text, *, font=32, color=65280, background=0)
 433  LCDFrame.physical_frame(self)
 437  class VideoDMA
 446  VideoDMA.__init__(self, mmio, parameters, *, allocator=None, timeout=2.0)
 466  VideoDMA._wait(self, predicate, message)
 474  VideoDMA._stop(self, channel)
 483  VideoDMA._reset(self, channel)
 492  VideoDMA._allocate(self, shape)
 504  VideoDMA.start_capture(self)
 512  VideoDMA.read_frame(self)
 530  VideoDMA._capture_once(self)
 552  VideoDMA.start_display(self, vtc_mmio)
 571  VideoDMA.write_display(self, frame_bgr)
 583  VideoDMA.close(self)
```

## src/trash_pynq/preview.py

[查看完整源码](src/trash_pynq/preview.py)

```python
   6  class PreviewPresenter
   8  PreviewPresenter.__init__(self, ui, video=None)
  15  PreviewPresenter.present(self, raw, **state)
```

## src/trash_pynq/reference.py

[查看完整源码](src/trash_pynq/reference.py)

```python
  11  pack_chw(chw)
  21  unpack_chw(packed, channels, height, width)
  31  _saturate(value)
  35  multiply_q10(left, right)
  41  mac_q10(accumulator, left, right)
  48  shortcut_q10(left, right)
  57  avgpool_fc_q10(packed_input, weights, bias)
```

## src/trash_pynq/ui.py

[查看完整源码](src/trash_pynq/ui.py)

```python
  22  class LeafUI
  34  LeafUI.__init__(self, data_dir=None)
  51  LeafUI._bgr(color)
  54  LeafUI._blend(self, x, y, mask, color)
  66  LeafUI._rounded(self, x, y, w, h, radius, color, alpha=1.0)
  81  LeafUI._remember_geometry(self, key, mask)
  87  LeafUI._line(self, x1, y1, x2, y2, color, width=1.5)
 106  LeafUI._text(self, x, y, text, size=16, color=None, bold=False)
 120  LeafUI._center_text(self, x, y, width, text, size=16, color=None, bold=False)
 123  LeafUI._leaf(self, cx, cy, size, color, vein)
 142  LeafUI._camera_decoration(self)
 155  LeafUI._compile_camera_overlay(self)
 200  LeafUI._update_camera(self, frame)
 208  LeafUI.hit_test(self, x, y)
 214  LeafUI.render(self, frame_bgr=None, label=None, latency_ms=None, light=False, status='Ready', saved_count=0)
 243  LeafUI._render_uncached(self, frame_bgr=None, label=None, latency_ms=None, light=False, status='Ready', saved_count=0)
 330  LeafUI.physical_frame(self, frame=None)
```

## tests/test_lanuch.py

[查看完整源码](tests/test_lanuch.py)

```python
  72  class LauncherTests
  73  async LauncherTests.asyncSetUp(self)
  90  LauncherTests.write_notebook(self, updates=None)
  97  async LauncherTests.asyncTearDown(self)
 109  async LauncherTests.test_start_duplicate_request_and_idempotent_stop(self)
 126  async LauncherTests.test_optional_model_touch_and_web_stop(self)
 137  async LauncherTests.test_initialization_exception_cleans_partial_resources(self)
 148  async LauncherTests.test_preview_failure_automatically_cleans(self)
 160  async LauncherTests.test_cleanup_failure_retains_owner_and_lock_then_retries(self)
 174  async LauncherTests.test_cancelled_waiter_cannot_cancel_cleanup(self)
 188  async LauncherTests.test_legacy_notebook_is_rejected_before_hardware(self)
 195  async LauncherTests.test_missing_or_duplicate_tag_is_rejected(self)
```

## Notebook 控制函数

### 01_bringup_and_demo.ipynb

```python
cell 9: request_action(action)
cell 9: async preview_loop()
```

### 01_bringup_and_demo_optimized.ipynb

```python
cell 9: request_action(action)
cell 9: async preview_loop()
```

