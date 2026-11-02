"""Preserve tool-required filenames without using them as submission paths.

Snapshot entries are lowercase SHA-256 objects. Original paths are JSON data;
restoration reproduces the original names and bytes in an external workspace.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import uuid
import zipfile


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def disk_path(path):
    text = str(Path(path).absolute())
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return Path("\\\\?\\" + text)
    return Path(text)


def safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Invalid source path: {!r}".format(value))
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("", ".", "..") for p in value.split("/")):
        raise ValueError("Unsafe source path: " + value)
    return path


def create_snapshot(source, output, label):
    source, output = disk_path(source), disk_path(output)
    if output.exists():
        raise FileExistsError(str(output))
    if not source.is_dir():
        raise FileNotFoundError(str(source))
    if source == output or source in output.parents:
        raise ValueError("Snapshot output must be outside its source tree")
    files = []
    objects = set()
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + "." + uuid.uuid4().hex + ".partial")
    with zipfile.ZipFile(str(partial), "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise ValueError("Source symlinks are not accepted: " + str(path))
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            safe_relative(relative)
            digest = sha256_file(path)
            entry = "objects/" + digest + ".bin"
            if entry not in objects:
                archive.write(str(path), entry)
                objects.add(entry)
            files.append({"path": relative, "object": entry,
                          "sha256": digest, "bytes": path.stat().st_size})
        manifest = {"schema": 1, "label": label, "files": files,
                    "storage": "sha256_objects_original_paths_are_manifest_data"}
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False,
                                                     sort_keys=True, indent=2) + "\n")
    verify_snapshot(partial)
    # Hard-link creation fails if a target appeared meanwhile; no overwrite.
    os.link(str(partial), str(output))
    partial.unlink()
    return {"files": len(files), "objects": len(objects),
            "sha256": sha256_file(output), "bytes": output.stat().st_size}


def verify_snapshot(path):
    with zipfile.ZipFile(str(disk_path(path))) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(
                not re.fullmatch(r"(?:objects/[0-9a-f]{64}\.bin|manifest\.json)", n)
                for n in names):
            raise ValueError("Unexpected or duplicate snapshot member")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("schema") != 1 or not manifest.get("files"):
            raise ValueError("Unsupported or empty source manifest")
        seen, checked = set(), set()
        for record in manifest["files"]:
            relative = safe_relative(record["path"]).as_posix()
            identity = relative.casefold() if os.name == "nt" else relative
            if identity in seen:
                raise ValueError("Conflicting native source path: " + relative)
            seen.add(identity)
            digest = record["sha256"]
            entry = "objects/" + digest + ".bin"
            if not re.fullmatch("[0-9a-f]{64}", digest) or record["object"] != entry:
                raise ValueError("Invalid source object identity")
            if archive.getinfo(entry).file_size != record["bytes"]:
                raise ValueError("Source object size differs: " + relative)
            if entry not in checked:
                with archive.open(entry) as stream:
                    actual = hashlib.sha256()
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        actual.update(block)
                if actual.hexdigest() != digest:
                    raise ValueError("Corrupt source object: " + entry)
                checked.add(entry)
        if set(names) != checked | {"manifest.json"}:
            raise ValueError("Unreferenced snapshot members")
        return manifest


def restore_snapshot(snapshot, destination, project_root):
    project_root = Path(project_root).resolve()
    destination = Path(destination).expanduser().resolve()
    def canonical(path):
        text = str(path)
        if os.name == "nt" and text.startswith("\\\\?\\"):
            text = text[4:]
        return os.path.normcase(os.path.normpath(text))
    project_key, destination_key = canonical(project_root), canonical(destination)
    try:
        inside = os.path.commonpath((project_key, destination_key)) == project_key
    except ValueError:
        inside = False
    if inside:
        raise ValueError("Restore to a new directory outside the submission tree")
    if destination.exists():
        raise FileExistsError("Restore destination must be new: " + str(destination))
    manifest = verify_snapshot(snapshot)
    destination = disk_path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(str(disk_path(snapshot))) as archive:
        for record in manifest["files"]:
            relative = safe_relative(record["path"])
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(record["object"]) as src, target.open("xb") as dst:
                for block in iter(lambda: src.read(1024 * 1024), b""):
                    dst.write(block)
            if sha256_file(target) != record["sha256"]:
                raise ValueError("Restored source hash differs: " + record["path"])
    return len(manifest["files"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("snapshot", type=Path)
    create = commands.add_parser("create")
    create.add_argument("source", type=Path)
    create.add_argument("output", type=Path)
    create.add_argument("--label", required=True)
    args = parser.parse_args()
    result = (create_snapshot(args.source, args.output, args.label)
              if args.command == "create" else
              {"verified_files": len(verify_snapshot(args.snapshot)["files"])})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
