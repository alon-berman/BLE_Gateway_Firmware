"""Amazon Root CA 1, the CA the gateway uses to trust the AWS IoT endpoint.

A verified copy ships with the repo (scripts/certs/AmazonRootCA1.pem) so a
fresh machine does not need an older gateway's folder to copy it from.
"""
import hashlib
import os
import shutil

ROOT_CA_NAME = "AmazonRootCA1.pem"
BUNDLED_ROOT_CA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs", ROOT_CA_NAME)
# sha256 of the PEM file as published at https://www.amazontrust.com/repository/AmazonRootCA1.pem
ROOT_CA_PEM_SHA256 = "2c43952ee9e000ff2acc4e2ed0897c0a72ad5fa72c3d934e81741cbd54f05bd1"


def verify_root_ca(path: str) -> None:
    """Raise ValueError unless `path` is byte-identical to the published CA."""
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    if digest != ROOT_CA_PEM_SHA256:
        raise ValueError(f"{path} is not Amazon Root CA 1 (sha256 {digest[:16]}…)")


def ensure_root_ca(cert_folder: str) -> str:
    """Return the path of AmazonRootCA1.pem inside `cert_folder`, copying the
    bundled copy there when the folder has none. The file is verified either way."""
    target = os.path.join(cert_folder, ROOT_CA_NAME)
    if not os.path.isfile(target):
        verify_root_ca(BUNDLED_ROOT_CA)
        os.makedirs(cert_folder, exist_ok=True)
        shutil.copyfile(BUNDLED_ROOT_CA, target)
    verify_root_ca(target)
    return target
