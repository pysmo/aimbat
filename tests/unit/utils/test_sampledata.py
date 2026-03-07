"""Unit tests for aimbat.utils._sampledata."""

import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aimbat.utils._sampledata import delete_sampledata, download_sampledata


def _make_zip_bytes(filenames: list[str]) -> bytes:
    """Return the bytes of a ZIP archive containing empty files with the given names.

    Args:
        filenames (list[str]): List of filenames to include in the ZIP.

    Returns:
        bytes: The bytes of the ZIP archive.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        for name in filenames:
            zf.writestr(name, b"")
    return buf.getvalue()


@pytest.fixture()
def sampledata_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point settings.sampledata_dir at a temp directory for each test.

    Args:
        tmp_path (Path): Temporary directory path.
        monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.

    Returns:
        Path: The temporary sample data directory.
    """
    d = tmp_path / "sample-data"
    import aimbat

    monkeypatch.setattr(aimbat.settings, "sampledata_dir", d)
    return d


class TestDeleteSampledata:
    """Tests for the delete_sampledata function."""

    def test_removes_directory(self, sampledata_dir: Path) -> None:
        """Verifies that the sample data directory is removed.

        Args:
            sampledata_dir (Path): The sample data directory.
        """
        sampledata_dir.mkdir()
        (sampledata_dir / "file.txt").write_text("x")
        delete_sampledata()
        assert not sampledata_dir.exists()

    def test_raises_if_dir_missing(self, sampledata_dir: Path) -> None:
        """Verifies that FileNotFoundError is raised if the directory is missing.

        Args:
            sampledata_dir (Path): The sample data directory.
        """
        assert not sampledata_dir.exists()
        with pytest.raises(FileNotFoundError):
            delete_sampledata()


class TestDownloadSampledata:
    """Tests for the download_sampledata function."""

    def _mock_urlopen(self, filenames: list[str]) -> MagicMock:
        """Return a context-manager mock that yields ZIP bytes for urlopen.

        Args:
            filenames (list[str]): List of filenames for the mock ZIP.

        Returns:
            MagicMock: A mock object behaving like urlopen's return value.
        """
        zip_bytes = _make_zip_bytes(filenames)
        mock_resp = MagicMock()
        mock_resp.read.return_value = zip_bytes
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen = MagicMock(return_value=mock_resp)
        return mock_urlopen

    def test_extracts_files(self, sampledata_dir: Path) -> None:
        """Verifies that files are extracted to the sample data directory.

        Args:
            sampledata_dir (Path): The sample data directory.
        """
        mock_urlopen = self._mock_urlopen(["data/file1.sac", "data/file2.sac"])
        with patch("aimbat.utils._sampledata.urlopen", mock_urlopen):
            download_sampledata()
        assert sampledata_dir.exists()

    def test_raises_if_dir_non_empty(self, sampledata_dir: Path) -> None:
        """Verifies that FileExistsError is raised if the directory is not empty.

        Args:
            sampledata_dir (Path): The sample data directory.
        """
        sampledata_dir.mkdir()
        (sampledata_dir / "existing.txt").write_text("x")
        mock_urlopen = self._mock_urlopen(["data/file.sac"])
        with patch("aimbat.utils._sampledata.urlopen", mock_urlopen):
            with pytest.raises(FileExistsError):
                download_sampledata()
        mock_urlopen.assert_not_called()

    def test_force_overwrites_existing(self, sampledata_dir: Path) -> None:
        """Verifies that existing files are overwritten when force=True.

        Args:
            sampledata_dir (Path): The sample data directory.
        """
        sampledata_dir.mkdir()
        (sampledata_dir / "old.txt").write_text("old")
        mock_urlopen = self._mock_urlopen(["data/new.sac"])
        with patch("aimbat.utils._sampledata.urlopen", mock_urlopen):
            download_sampledata(force=True)
        assert not (sampledata_dir / "old.txt").exists()

    def test_empty_dir_not_blocked(self, sampledata_dir: Path) -> None:
        """Verifies that an existing empty directory does not block download.

        Args:
            sampledata_dir (Path): The sample data directory.
        """
        sampledata_dir.mkdir()
        mock_urlopen = self._mock_urlopen(["data/file.sac"])
        with patch("aimbat.utils._sampledata.urlopen", mock_urlopen):
            download_sampledata()
        mock_urlopen.assert_called_once()

    def test_urlopen_called_with_src(self, sampledata_dir: Path) -> None:
        """Verifies that urlopen is called with the configured source URL.

        Args:
            sampledata_dir (Path): The sample data directory.
        """
        import aimbat

        mock_urlopen = self._mock_urlopen(["data/file.sac"])
        with patch("aimbat.utils._sampledata.urlopen", mock_urlopen):
            download_sampledata()
        mock_urlopen.assert_called_once_with(aimbat.settings.sampledata_src)
