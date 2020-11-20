"""
Run tests for the sacpickle.py module.
"""

import pytest
import os
import filecmp
import bz2
import gzip
import pickle
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
    to a reference pickle file. Direct comparrison of the binary files
    is a bit tricky, so instead the files are unpickled again and then
    compared.
    """
    outfile = tmpdir + '/sac2pkl.pkl'
    outfile_gz = tmpdir + '/sac2pkl.pkl.gz'
    outfile_bz2 = tmpdir + '/sac2pkl.pkl.bz2'
    sacpickle.sac2pkl(_sacfiles, pkfile=outfile, zipmode=None)
    assert pickle.load(open(outfile, "rb")).stadict == \
        pickle.load(open(_pklfile, "rb")).stadict
    sacpickle.sac2pkl(_sacfiles, pkfile=outfile, zipmode='gz')
    assert pickle.load(gzip.open(outfile_gz, "rb")).stadict == \
        pickle.load(open(_pklfile, "rb")).stadict
    sacpickle.sac2pkl(_sacfiles, pkfile=outfile, zipmode='bz2')
    assert pickle.load(bz2.open(outfile_bz2, "rb")).stadict == \
        pickle.load(open(_pklfile, "rb")).stadict
