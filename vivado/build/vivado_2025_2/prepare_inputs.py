"""Stage BD, RTL, constraints and packaged IP without changing originals.

This checks and copies sources; it does not run Vivado. Original logic, IP,
constraints and BD are preserved byte for byte in the prepared input. The
separate Tcl entry can upgrade built-in system IP in Vivado 2025.2 while
retaining the supplied HLS algorithm and packaged RTL unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
from xml.etree import ElementTree as ET

PORT = Path(__file__).resolve().parents[1]
NS = {"s": "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009"}
PART = "xc7z020clg484-2"
NAMES = ("conv", "fc", "pwdwconv", "shortcut")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def within(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def inspect_ip(root):
    found = {}
    for component in Path(root).rglob("component.xml"):
        xml = ET.parse(str(component)).getroot()
        fields = [xml.findtext("s:" + key, namespaces=NS)
                  for key in ("vendor", "library", "name", "version")]
        if fields[:2] != ["xilinx.com", "hls"] or fields[2] not in NAMES:
            continue
        name = fields[2]
        if fields[3] != "0.0":
            raise ValueError("BD requires version 0.0, got " + ":".join(fields))
        if name in found:
            raise ValueError("Ambiguous duplicate packaged IP: " + name)
        files = sorted(set(node.text for node in xml.findall(".//s:file/s:name", NS)))
        for filename in files:
            relative = PurePosixPath(filename.replace("\\", "/"))
            candidate = (component.parent / str(relative)).resolve()
            if (relative.is_absolute() or ".." in relative.parts or ":" in filename or
                    not within(candidate, component.parent.resolve())):
                raise ValueError("Packaged IP contains a nonlocal path: " + filename)
            if not candidate.is_file():
                raise FileNotFoundError("Missing packaged IP file: " + str(candidate))
        found[name] = {"component": component, "files": files,
                       "vlnv": ":".join(fields)}
    if set(found) != set(NAMES):
        raise ValueError("Missing packaged HLS IP: " + ", ".join(sorted(set(NAMES) - set(found))))
    depths = []
    for filename in found["pwdwconv"]["files"]:
        if not re.search(r"(?:^|/)pwconv_bias_buff_[^/]+\.v$", filename):
            continue
        text = (found["pwdwconv"]["component"].parent / filename).read_text(encoding="utf-8")
        depths.extend(int(value) for value in re.findall(
            r"parameter\s+(?:AddressRange|MEM_SIZE)\s*=\s*(?:\d+'d)?(\d+)\s*;", text))
    return found, min(depths) if depths else None


def prepare(project_root, ip_root, output, timing_xdc=None, target_version="2025.2"):
    project_root, ip_root, output = [Path(p).resolve() for p in (project_root, ip_root, output)]
    if output.exists():
        raise FileExistsError("Use a new output directory: " + str(output))
    if target_version not in ("2019.2", "2025.2"):
        raise ValueError("Supported target versions are 2019.2 and 2025.2")
    if (within(output, project_root) or within(output, ip_root) or
            within(project_root, output) or within(ip_root, output)):
        raise ValueError("Output and original source/IP trees must not overlap")
    xpr = project_root / "trash.xpr"
    project = ET.parse(str(xpr)).getroot()
    part = project.find("./Configuration/Option[@Name='Part']").get("Val")
    if part != PART:
        raise ValueError("Unexpected project part: " + str(part))
    source_files = {
        "bd/design_1.bd": project_root / "trash.srcs/sources_1/bd/design_1/design_1.bd",
        "rtl/rgb888_to_rgb565.v": project_root / "trash.srcs/sources_1/new/RGB888toRGB565.v",
        "constraints/trash.xdc": project_root / "trash.srcs/constrs_1/new/Trash.xdc",
    }
    if timing_xdc is not None:
        source_files["constraints/user_timing.xdc"] = Path(timing_xdc).resolve()
    for path in source_files.values():
        if not path.is_file():
            raise FileNotFoundError(str(path))
    bd = json.loads(source_files["bd/design_1.bd"].read_text(encoding="utf-8"))["design"]
    if bd["design_info"]["device"] != PART:
        raise ValueError("BD part disagrees with project")
    for name in NAMES:
        if bd["components"][name + "_0"]["vlnv"] != "xilinx.com:hls:" + name + ":0.0":
            raise ValueError("Unexpected BD HLS identity: " + name)
    ip, bias_depth = inspect_ip(ip_root)
    output.mkdir(parents=True)
    manifest = {"schema": 1, "operation": "source_preparation_only_not_compiled",
                "source_xpr": str(xpr), "source_xpr_sha256": digest(xpr),
                "source_ip_root": str(ip_root), "part": part,
                "source_vivado": bd["design_info"]["tool_version"],
                "target_vivado": target_version,
                "pointwise_bias_rows": bias_depth,
                "logic_policy": "regenerated_2025_2_original_algorithm",
                "files": {}, "ips": {}}
    for relative, source in source_files.items():
        destination = output / "inputs" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        manifest["files"]["inputs/" + relative] = digest(destination)
    for name, item in ip.items():
        destination = output / "ip_repo" / name
        destination.mkdir(parents=True)
        for filename in ["component.xml"] + item["files"]:
            target = destination / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item["component"].parent / filename, target)
            manifest["files"][target.relative_to(output).as_posix()] = digest(target)
        manifest["ips"][name] = {"vlnv": item["vlnv"],
                                 "component_sha256": digest(destination / "component.xml"),
                                 "referenced_files": len(item["files"])}
    config = ["# Generated by prepare_vivado.py; preparation is not compilation.",
              "set prepare_root [file dirname [file normalize [info script]]]",
              "set prepare_part {" + part + "}",
              "set prepare_source_version {" + manifest["source_vivado"] + "}",
              "set prepare_target_version {" + target_version + "}",
              "set prepare_ip_dirs [list]"]
    config += ["lappend prepare_ip_dirs [file join $prepare_root {ip_repo} {" + name + "}]"
               for name in NAMES]
    config += ["set prepare_bd [file join $prepare_root {inputs} {bd} {design_1.bd}]",
               "set prepare_rtl [file join $prepare_root {inputs} {rtl} {rgb888_to_rgb565.v}]",
               "set prepare_xdc [list [file join $prepare_root {inputs} {constraints} {trash.xdc}]]"]
    if timing_xdc is not None:
        config.append("lappend prepare_xdc [file join $prepare_root {inputs} {constraints} {user_timing.xdc}]")
    (output / "prepare_config.tcl").write_text("\n".join(config) + "\n", encoding="ascii")
    (output / "prepare_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return manifest


def prepare_new(native_project, ip_root, output, timing_xdc=None):
    ip, _ = inspect_ip(ip_root)
    # The instance ID-disable configuration is authorized only for this reviewed
    # single-logical-ID adapter profile. Check again for every fresh export.
    import importlib.util
    helper = Path(__file__).with_name('review_single_id.py')
    spec = importlib.util.spec_from_file_location('_single_id_source_gate', helper)
    single_id = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(single_id)
    id_review = single_id.review(folders={name: item['component'].parent for name, item in ip.items()})
    if id_review['status'] != 'PASS':
        raise ValueError('Unsafe unreviewed AXI ID profile: ' + '; '.join(id_review['failures']))
    versions = {}
    for name, item in ip.items():
        top = item["component"].parent / "hdl/verilog" / (name + ".v")
        text = top.read_text(encoding="utf-8")
        if "Generated by Vitis HLS v2025.2" not in text[:1200] or "HLS_VERSION=2025_2" not in text[:5000]:
            raise ValueError("Expected an actual 2025.2 HLS export: " + str(top))
        versions[name] = {"component": str(item["component"]), "component_sha256": digest(item["component"]),
                          "top_sha256": digest(top), "tool_marker": "Vitis HLS v2025.2"}
    manifest = prepare(native_project, ip_root, output, timing_xdc, "2025.2")
    manifest["hls_exports"] = versions
    (Path(output) / 'single_id_source_gate.json').write_text(json.dumps(id_review, indent=2) + '\n', encoding='utf-8')
    reference = {"cores": {}}
    for core in NAMES:
        folder = Path(native_project) / "trash.srcs/sources_1/bd/design_1/ip"
        original = next(folder.glob("design_1_" + core + "_*/design_1_*.xci"))
        native_xci = json.loads(original.read_text())["ip_inst"]
        reference["cores"][core] = {"source": str(original), "source_sha256": digest(original),
                                     "ports": native_xci["boundary"]["ports"]}
    reference_path = Path(output) / "inputs/reference_hls_ports.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n", encoding="utf-8")
    manifest["files"]["inputs/reference_hls_ports.json"] = digest(reference_path)
    manifest["hls_validation_limit"] = "Version markers and bytes are checked. Algorithm preservation, scheduling directives and RTL cosim require the corresponding HLS evidence; markers alone are not equivalence proof."
    (Path(output) / "prepare_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage four verified 2025.2 HLS exports and an unchanged native AC820 Vivado source project")
    parser.add_argument("--native-project", required=True, type=Path)
    parser.add_argument("--ip-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timing-xdc", type=Path)
    args = parser.parse_args()
    result = prepare_new(args.native_project, args.ip_root, args.output, args.timing_xdc)
    print(json.dumps({"status": "STAGED_NOT_COMPILED", "hls_exports": result["hls_exports"]}, indent=2))
