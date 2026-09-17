"""Download and remove the bundled AIMBAT sample dataset."""

import os
import shutil
import stat
import tempfile
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile, ZipInfo

from aimbat import settings
from aimbat.logger import logger

__all__ = ["delete_sampledata", "download_sampledata"]

_SAMPLEDATA_SRC = (
    "https://github.com/pysmo/aimbat-sampledata/archive/refs/heads/master.zip"
)
_DOWNLOAD_TIMEOUT_SECONDS = 30
_MIN_SAFE_PATH_PARTS = 4
"""Minimum path components (e.g. `/`, `home`, `user`, `dir`) a delete target must have.

Rejects shallow, filesystem-critical paths like `/`, `/home`, `/tmp`, or a
user's home directory (`/home/someone`).
"""


def _check_safe_to_delete(path: Path) -> None:
    """Reject a path that looks unsafe to recursively delete.

    Args:
        path: The directory that would be deleted.

    Raises:
        ValueError: If `path` resolves to the filesystem root, any user's
            home directory (not just the current one - e.g. a sibling
            `/home/someone-else`), or another suspiciously shallow location -
            `Settings.sampledata_dir` is an ordinary path setting that can be
            overridden via an environment variable or `.env` file, so a typo
            or an untrusted `.env` should not be able to trigger a
            catastrophic recursive delete.
    """
    resolved = path.resolve()
    home = Path.home()
    if (
        resolved == Path(resolved.anchor)
        or resolved == home
        or resolved.parent == home.parent
        or len(resolved.parts) < _MIN_SAFE_PATH_PARTS
    ):
        raise ValueError(
            f"Refusing to delete {resolved}: this does not look like a sample data"
            + " directory."
        )


def _is_symlink_entry(member: ZipInfo) -> bool:
    """Whether a zip entry's stored Unix permissions mark it as a symlink.

    `extractall` sanitises `..` and absolute paths, but a symlink entry can
    still be materialised and later point outside the extraction directory
    when followed, so such entries are skipped entirely.
    """
    unix_mode = member.external_attr >> 16
    return stat.S_ISLNK(unix_mode)


def _extract_regular_files(zfile: ZipFile, dest: Path) -> None:
    """Extract every non-symlink member of `zfile` into `dest`."""
    for member in zfile.infolist():
        if _is_symlink_entry(member):
            logger.warning(
                f"Skipping symlink entry in sample data archive: {member.filename}"
            )
            continue
        zfile.extract(member, dest)


def delete_sampledata() -> None:
    """Delete the sample data directory (`Settings.sampledata_dir`) and its contents.

    Raises:
        ValueError: If `Settings.sampledata_dir` looks unsafe to delete (see
            `_check_safe_to_delete`).
    """

    _check_safe_to_delete(settings.sampledata_dir)

    logger.info(f"Deleting sample data in {settings.sampledata_dir}.")

    shutil.rmtree(settings.sampledata_dir)


def download_sampledata(force: bool = False) -> None:
    """Download and extract the AIMBAT sample dataset.

    Downloads the sample data archive and extracts it into
    `Settings.sampledata_dir`.

    Args:
        force: Delete and replace an existing non-empty sample data
            directory instead of raising an error.

    Raises:
        FileExistsError: If the sample data directory already exists and is
            non-empty, and `force` is False.
    """

    logger.info(
        f"Downloading sample data from {_SAMPLEDATA_SRC} to {settings.sampledata_dir}."
    )

    if (
        settings.sampledata_dir.exists()
        and len(os.listdir(settings.sampledata_dir)) != 0
    ):
        if force is True:
            delete_sampledata()
        else:
            raise FileExistsError(
                f"The directory {settings.sampledata_dir} already exists and is "
                + "non-empty."
            )

    with urlopen(_SAMPLEDATA_SRC, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as zipresp:
        with tempfile.NamedTemporaryFile() as tmpfile:
            shutil.copyfileobj(zipresp, tmpfile)
            tmpfile.flush()
            tmpfile.seek(0)
            logger.debug(f"Extracting sample data to {settings.sampledata_dir}.")
            with ZipFile(tmpfile) as zfile:
                _extract_regular_files(zfile, settings.sampledata_dir)

    logger.info("Sample data downloaded and extracted successfully.")
