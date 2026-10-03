"""Hardware-free tests for mcumgr_certificate_upload.py, root_ca.py and mcumgr_bin.py.

Run with `python -m pytest scripts/tests` or `python scripts/tests/test_mcumgr_certificate_upload.py`.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import mcumgr_bin  # noqa: E402
import mcumgr_certificate_upload as up  # noqa: E402
import root_ca  # noqa: E402

IMEI = "354616090681581"


class Fake:
    """Stands in for mcumgr and the serial line.

    `fail_upload` names a destination whose upload returns exit code 1;
    `corrupt` names a destination whose read-back differs from the source.
    """

    def __init__(self, fail_upload=None, corrupt=None):
        self.fail_upload, self.corrupt = fail_upload, corrupt
        self.cmds, self.serial, self.log = [], [], []

    def run(self, cmd, label):
        self.cmds.append(cmd)
        action = cmd[cmd.index("fs") + 1] if "fs" in cmd else cmd[-1]
        if action == "upload":
            src, dest = cmd[-2], cmd[-1]
            if dest == self.fail_upload:
                return 1
            self.device = getattr(self, "device", {})
            self.device[dest] = open(src, "rb").read()
            if dest == self.corrupt:
                self.device[dest] = b"garbage"
            return 0
        if action == "download":
            dest, local = cmd[-2], cmd[-1]
            with open(local, "wb") as fh:
                fh.write(self.device[dest])
            return 0
        return 0  # reset

    def serial_cmd(self, command, port):
        self.serial.append(command)


def make_folder(tmp, with_root_ca=True, with_key=True):
    folder = os.path.join(tmp, IMEI)
    os.makedirs(folder)
    open(os.path.join(folder, f"deviceId-{IMEI}-certificate.pem.crt"), "w").write("CERT\n")
    if with_key:
        open(os.path.join(folder, f"deviceId-{IMEI}-private.pem.key"), "w").write("KEY\n")
    if with_root_ca:
        shutil.copyfile(root_ca.BUNDLED_ROOT_CA, os.path.join(folder, root_ca.ROOT_CA_NAME))
    return folder


def upload(folder, fake, monkeypatch=None):
    mcumgr_bin_path = mcumgr_bin.mcumgr_path
    mcumgr_bin.mcumgr_path = lambda: "/fake/mcumgr"
    up.mcumgr_path = lambda: "/fake/mcumgr"
    try:
        return up.upload_certificates(folder, "/dev/fake", log=fake.log.append,
                                      run=fake.run, serial_cmd=fake.serial_cmd, settle_s=0)
    finally:
        mcumgr_bin.mcumgr_path = mcumgr_bin_path
        up.mcumgr_path = mcumgr_bin_path


def test_bundled_root_ca_is_the_published_one():
    root_ca.verify_root_ca(root_ca.BUNDLED_ROOT_CA)
    assert open(root_ca.BUNDLED_ROOT_CA).read().startswith("-----BEGIN CERTIFICATE-----")


def test_missing_root_ca_is_added_from_the_repo():
    with tempfile.TemporaryDirectory() as tmp:
        folder = make_folder(tmp, with_root_ca=False)
        fake = Fake()
        assert upload(folder, fake) is True
        assert os.path.isfile(os.path.join(folder, root_ca.ROOT_CA_NAME))
        uploads = [c[-1] for c in fake.cmds if "upload" in c]
        assert uploads == ["/lfs/root_ca.pem", "/lfs/client_cert.pem", "/lfs/client_key.pem"]
        assert fake.serial[-3:] == [f"attr set endpoint {up.AWS_ENDPOINT}", "attr set commissioned 1", "log go"]
        assert fake.cmds[-1][-1] == "reset" and "mtu=1024" in fake.cmds[-1][-2]


def test_upload_failure_stops_and_leaves_gateway_decommissioned():
    with tempfile.TemporaryDirectory() as tmp:
        fake = Fake(fail_upload="/lfs/client_cert.pem")
        assert upload(make_folder(tmp), fake) is False
        assert "attr set commissioned 1" not in fake.serial
        assert fake.serial[:2] == ["log halt", "attr set commissioned 0"]
        assert not any(c[-1] == "reset" for c in fake.cmds)
        assert any("certificate.pem.crt" in c and "failed" in c for c in fake.log)


def test_corrupt_readback_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        fake = Fake(corrupt="/lfs/client_key.pem")
        assert upload(make_folder(tmp), fake) is False
        assert "attr set commissioned 1" not in fake.serial
        assert any("does not match" in c for c in fake.log)


def test_missing_key_file_writes_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        fake = Fake()
        assert upload(make_folder(tmp, with_key=False), fake) is False
        assert fake.cmds == [] and fake.serial == []


def test_missing_mcumgr_is_reported_before_touching_the_device():
    with tempfile.TemporaryDirectory() as tmp:
        fake = Fake()
        saved = up.mcumgr_path
        up.mcumgr_path = mcumgr_bin.mcumgr_path
        old_path, old_home = os.environ.get("PATH", ""), os.environ.get("HOME")
        os.environ["PATH"], os.environ["HOME"] = tmp, tmp
        try:
            if os.path.exists("/usr/local/bin/mcumgr") or os.path.exists("/opt/homebrew/bin/mcumgr"):
                return  # cannot hide a system-wide install from here
            assert up.upload_certificates(make_folder(tmp), "/dev/fake", log=fake.log.append,
                                          run=fake.run, serial_cmd=fake.serial_cmd) is False
            assert fake.cmds == [] and fake.serial == []
            assert any("mcumgr not found" in c for c in fake.log)
        finally:
            os.environ["PATH"] = old_path
            if old_home is not None:
                os.environ["HOME"] = old_home
            up.mcumgr_path = saved


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} tests passed")
