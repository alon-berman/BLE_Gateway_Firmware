"""Hardware-free tests for mcumgr_flash.py.

Run with `python -m pytest scripts/tests` or `python scripts/tests/test_mcumgr_flash.py`.
"""

import hashlib
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import mcumgr_flash as mf  # noqa: E402

IMAGE_LIST = """Images:
 image=0 slot=0
    version: 7.1.0.1788342009
    bootable: true
    flags: active confirmed
    hash: E85D527ABF6C3F32D65D8B322B46417195F35424FCE9C51F51832B7F04D5700C
 image=0 slot=1
    version: 7.2.0.1790411131
    bootable: true
    flags: 
    hash: c8d5ca442f0f3ddebac9636bc8408f859df4ce1bf41cd5a4ea18529eca3672c4
Split status: N/A (0)
"""


def build_image(payload=b"\xAA" * 64, protected=False, with_hash=True):
    hdr_size = 32
    header = struct.pack("<IIHHII", mf.MCUBOOT_IMAGE_MAGIC, 0, hdr_size, 0,
                         len(payload), 0) + struct.pack("<BBHI", 7, 2, 0, 1) + b"\0" * 4
    digest = hashlib.sha256(header + payload).digest()
    tlvs = b""
    if with_hash:
        tlvs += struct.pack("<HH", mf.MCUBOOT_TLV_SHA256, len(digest)) + digest
    tlvs += struct.pack("<HH", 0x20, 4) + b"\1\2\3\4"
    image = header + payload
    if protected:
        prot = struct.pack("<HH", 0x50, 2) + b"\0\0"
        image += struct.pack("<HH", mf.MCUBOOT_TLV_PROT_INFO_MAGIC, 4 + len(prot)) + prot
    image += struct.pack("<HH", mf.MCUBOOT_TLV_INFO_MAGIC, 4 + len(tlvs)) + tlvs
    return image, digest.hex()


def write_tmp(data):
    handle, path = tempfile.mkstemp(suffix=".bin")
    with os.fdopen(handle, "wb") as tmp:
        tmp.write(data)
    return path


def test_parse_image_list():
    slots = mf.parse_image_list(IMAGE_LIST)
    assert sorted(slots) == [0, 1]
    assert slots[0]["version"] == "7.1.0.1788342009"
    assert slots[0]["flags"] == {"active", "confirmed"}
    assert slots[0]["hash"].startswith("e85d527a"), "hash must be lower-cased"
    assert slots[1]["flags"] == set()
    assert slots[1]["hash"].startswith("c8d5ca44")


def test_parse_image_list_garbage():
    assert mf.parse_image_list("Error: NMP timeout\n") == {}
    assert mf.parse_image_list("") == {}
    noisy = "[00:00:03.1] <inf> lte: x\n" + IMAGE_LIST
    assert sorted(mf.parse_image_list(noisy)) == [0, 1]


def test_local_image_hash_plain_and_protected():
    for protected in (False, True):
        image, digest = build_image(protected=protected)
        path = write_tmp(image)
        try:
            assert mf.local_image_hash(path) == digest
        finally:
            os.remove(path)


def test_local_image_hash_rejects_non_images():
    for data in (b"", b"not an image at all" * 4, build_image(with_hash=False)[0],
                 build_image()[0][:40]):
        path = write_tmp(data)
        try:
            assert mf.local_image_hash(path) is None
        finally:
            os.remove(path)


def test_str2bool():
    assert mf.str2bool("False") is False, "argparse type=bool treated this as True"
    assert mf.str2bool("0") is False
    assert mf.str2bool("true") is True
    assert mf.str2bool(True) is True


def test_describe():
    text = mf.describe(mf.parse_image_list(IMAGE_LIST))
    assert "slot0: 7.1.0.1788342009 [active confirmed] e85d527abf6c" in text
    assert mf.describe({}) == "(no images reported)"


if __name__ == "__main__":
    failures = 0
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
