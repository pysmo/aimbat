"""
Run tests for the sacpickle.py module.
"""

import pytest
import os
import filecmp
import bz2
import gzip
import shutil
from glob import glob
from pysmo.aimbat import sacpickle

_curdir = os.path.dirname(__file__)
_sacfiles = glob(_curdir + '/test_files/*/*.BHZ')
_pklfile = _curdir + '/test_files/sac.pkl'


def test_zipFile():
    """
    Test if the correct compression type is returned.
    """
    assert sacpickle.zipFile() is gzip.GzipFile
    assert sacpickle.zipFile("gz") is gzip.GzipFile
    assert sacpickle.zipFile("bz2") is bz2.BZ2File
    with pytest.raises(ValueError):
        assert sacpickle.zipFile("invalid_input")


def test_fileZipMode():
    """
    Test if the correct filetype and compression type is returned.
    """
    assert sacpickle.fileZipMode("file.bz2") == ("pkl", "bz2")
    assert sacpickle.fileZipMode("file.gz") == ("pkl", "gz")
    assert sacpickle.fileZipMode("file.pkl") == ("pkl", None)
    assert sacpickle.fileZipMode("file.sac") == ("sac", None)


def test_sac2pkl(tmpdir):
    """
    Convert a group of SAC files to a pickle file and compare output
    to a reference pickle file. Gzip compressed pickle files are
    decompressed and compared to the reference file.
    """
    outfile = tmpdir + '/sac2pkl.pkl'
    outfile_gz = tmpdir + '/sac2pkl.pkl.gz'
    outfile_gz_decompressed = tmpdir + '/sac2pkl_gz_decompressed.pkl'
    outfile_bz2 = tmpdir + '/sac2pkl.pkl.bz2'
    sacpickle.sac2pkl(_sacfiles, pkfile=outfile, zipmode=None)
    assert filecmp.cmp(outfile, _pklfile, shallow=False)
    sacpickle.sac2pkl(_sacfiles, pkfile=outfile, zipmode='gz')
    with gzip.open(outfile_gz, 'rb') as f_in, \
            open(outfile_gz_decompressed, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    assert filecmp.cmp(outfile_gz_decompressed, _pklfile, shallow=False)
    sacpickle.sac2pkl(_sacfiles, pkfile=outfile, zipmode='bz2')
    assert filecmp.cmp(outfile_bz2, _pklfile+'.bz2', shallow=False)
