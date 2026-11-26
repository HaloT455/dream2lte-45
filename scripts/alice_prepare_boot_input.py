#!/usr/bin/env python3
"""Recover the genuine uploaded EGO boot from checksum-pinned ZIP parts."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile


def prepare(bundle, output):
    receipt = json.loads((bundle / "bundle.json").read_text())
    expected = "c09f62145c47926a423114a525ae695e10a127f4e8015f697082abd969729873"
    if receipt["image_sha256"] != expected or output.exists():
        raise ValueError("Wrong EGO source identity or existing output")
    output.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with tempfile.TemporaryFile() as archive:
        for part in receipt["parts"]:
            if Path(part["name"]).name != part["name"]:
                raise ValueError("Invalid boot ZIP part name")
            data = (bundle / part["name"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != part["sha256"]:
                raise ValueError("Boot ZIP part checksum mismatch")
            archive.write(data)
            digest.update(data)
        if digest.hexdigest() != receipt["archive_sha256"]:
            raise ValueError("Boot ZIP checksum mismatch")
        archive.seek(0)
        with zipfile.ZipFile(archive) as zipped:
            if zipped.namelist() != ["boot.img"]:
                raise ValueError("Expected exactly one genuine boot.img")
            image = zipped.read("boot.img")
        if len(image) != receipt["image_bytes"] or hashlib.sha256(image).hexdigest() != expected:
            raise ValueError("Original EGO boot image checksum mismatch")
        if image[:8] != b"ANDROID!":
            raise ValueError("Original EGO boot header missing")
        output.write_bytes(image)
    print("Verified real EGO boot SHA256:", expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.bundle, args.output)
