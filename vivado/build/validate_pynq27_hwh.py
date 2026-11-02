"""Parse HWH offline with the unchanged official PYNQ 2.7.0 Zynq parser.

Only four architecture constants are supplied instead of importing pynq.ps.
No Overlay, MMIO, Device, allocator, board or hardware tool is invoked.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
from overlay_contract import CONTROL_REGISTERS, EXPECTED_REGISTERS, canonicalize_registers

PARSER_PATH = ROOT / "sim/vendor/pynq27_hwh_parser.py"
PARSER_SHA256 = "9038f5b618da3ed5f88504d150f9481487a6f0a0f73ec0a79f530415a87c37f0"
PARSER_SOURCE = "https://raw.githubusercontent.com/Xilinx/PYNQ/v2.7.0/pynq/pl_server/hwh_parser.py"
ARCH_CONSTANTS = {"CPU_ARCH_IS_SUPPORTED": True, "CPU_ARCH": "armv7l",
                  "ZYNQ_ARCH": "armv7l", "ZU_ARCH": "aarch64"}
EXPECTED_IPS = {"conv_0": 0x43C00000, "fc_0": 0x43C10000,
                "pwdwconv_0": 0x43C20000, "shortcut_0": 0x43C30000,
                "axi_vdma_0": 0x43000000, "v_tc_0": 0x43C40000}
EXPECTED_CLOCKS = {0: {"enable": 1, "divisor0": 6, "divisor1": 3},
                   1: {"enable": 1, "divisor0": 55, "divisor1": 1},
                   2: {"enable": 0, "divisor0": 1, "divisor1": 1},
                   3: {"enable": 0, "divisor0": 1, "divisor1": 1}}
EXPECTED_GPIO_PARAMETERS = {"PCW_GPIO_MIO_GPIO_ENABLE": "1",
                            "PCW_GPIO_EMIO_GPIO_ENABLE": "1",
                            "PCW_GPIO_EMIO_GPIO_IO": "1",
                            "PCW_GPIO_EMIO_GPIO_WIDTH": "1",
                            "PCW_MIO_0_DIRECTION": "inout"}


def _official_parser():
    """Import the original file in memory; leave no fake pynq modules behind."""
    payload = PARSER_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != PARSER_SHA256:
        raise ValueError("Official PYNQ 2.7.0 parser SHA256 differs")
    missing = object()
    saved = {name: sys.modules.get(name, missing) for name in ("pynq", "pynq.ps")}
    package = types.ModuleType("pynq")
    ps = types.ModuleType("pynq.ps")
    for key, value in ARCH_CONSTANTS.items():
        setattr(ps, key, value)
    package.ps = ps
    module = types.ModuleType("_official_pynq27_hwh_parser")
    module.__file__ = str(PARSER_PATH)
    try:
        sys.modules["pynq"] = package
        sys.modules["pynq.ps"] = ps
        exec(compile(payload, str(PARSER_PATH), "exec"), module.__dict__)
    finally:
        for name, value in saved.items():
            if value is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    if module.HWH.__name__ != "_HWHZynq":
        raise ValueError("Official parser did not select the Zynq-7000 architecture")
    return module.HWH


def _json_ready(value):
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (set, tuple, list)):
        return [_json_ready(item) for item in sorted(value)]
    return value


def validate(hwh):
    """Return metadata results, with explicit failures and no hardware access."""
    hwh = Path(hwh).resolve()
    result = {"passed": False, "hwh": str(hwh), "hardware_execution": False,
              "overlay_download": False, "device_allocation": False,
              "scope": "official PYNQ 2.7.0 offline HWH metadata parsing and AC820 interface checks only",
              "parser": {"version": "2.7.0", "source": PARSER_SOURCE,
                         "source_sha256": PARSER_SHA256,
                         "local_file": PARSER_PATH.relative_to(ROOT).as_posix(),
                         "architecture_constants_only": ARCH_CONSTANTS},
              "checks": {}, "errors": []}
    try:
        result["hwh_sha256"] = hashlib.sha256(hwh.read_bytes()).hexdigest()
        parsed = _official_parser()(hwh_name=str(hwh))
        result["parser"]["unchanged_source_verified"] = True
        result["parser"]["selected_class"] = type(parsed).__name__
        result["vivado_version"] = parsed.root.get("VIVADOVERSION")
        checks = result["checks"]
        checks["full_design"] = not parsed.partial and parsed.ps_name == "processing_system7_0"
        if not checks["full_design"]:
            result["errors"].append("Require full processing_system7_0 design")
        result["parsed_ip_names"] = sorted(parsed.ip_dict)
        result["required_ips"] = {}
        for name, expected_address in EXPECTED_IPS.items():
            ip = parsed.ip_dict.get(name)
            if ip is None:
                result["errors"].append("Official parser missed required IP: " + name)
                continue
            registers = ip.get("registers", {})
            raw = {key: {"address_offset": field["address_offset"], "size": field["size"]}
                   for key, field in registers.items()}
            details = {"phys_addr": ip.get("phys_addr"), "addr_range": ip.get("addr_range"),
                       "type": ip.get("type"), "registers": raw}
            result["required_ips"][name] = details
            if ip.get("phys_addr") != expected_address or ip.get("addr_range") != 0x10000:
                result["errors"].append("IP address/range differs: " + name)
            if name in EXPECTED_REGISTERS:
                if not raw or any(field["size"] != 32 for field in raw.values()):
                    result["errors"].append("Require parsed 32-bit HLS registers: " + name)
                controls = {key.upper(): field["address_offset"] for key, field in raw.items()
                            if key.upper() in CONTROL_REGISTERS}
                fields = {key: field["address_offset"] for key, field in raw.items()
                          if key.upper() not in CONTROL_REGISTERS}
                try:
                    details["canonical_registers"] = canonicalize_registers(name, fields)
                except ValueError as exc:
                    result["errors"].append(str(exc))
                if controls != CONTROL_REGISTERS:
                    result["errors"].append("Control register offsets differ: " + name)
            else:
                details["register_note"] = "Native IP metadata is recorded as parsed; baseline v_tc_0 has no REGISTER descriptions. The runtime uses direct MMIO, not v_tc_0.register_map."
        parameters = parsed.ip_dict.get(parsed.ps_name, {}).get("parameters", {})
        result["gpio_parameters"] = {key: parameters.get(key) for key in EXPECTED_GPIO_PARAMETERS}
        checks["ps_gpio_parameters"] = result["gpio_parameters"] == EXPECTED_GPIO_PARAMETERS
        if not checks["ps_gpio_parameters"]:
            result["errors"].append("PS MIO0/one EMIO GPIO metadata differs")
        result["gpio_dict"] = _json_ready(parsed.gpio_dict)
        result["gpio_note"] = "The baseline official parser gpio_dict is empty; runtime maps PS MIO0/EMIO0 from checked PS parameters using Linux GPIO, not an invented parser GPIO entry."
        result["clock_dict"] = parsed.clock_dict
        result["fclk0_hz_parameter"] = parameters.get("PCW_CLK0_FREQ")
        checks["ps_clocks"] = (parsed.clock_dict == EXPECTED_CLOCKS
                               and parameters.get("PCW_CLK0_FREQ") == "100000000")
        if not checks["ps_clocks"]:
            result["errors"].append("PS clock metadata differs from the supplied AC820 baseline")
        result["memory_names"] = sorted(parsed.mem_dict)
        result["passed"] = not result["errors"]
    except Exception as exc:
        result["errors"].append(type(exc).__name__ + ": " + str(exc))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hwh", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.output is not None and args.output.resolve() in (args.hwh.resolve(), PARSER_PATH.resolve()):
        parser.error("Output must differ from HWH and official parser source")
    result = validate(args.hwh)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("passed", "hwh", "hardware_execution", "errors")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
