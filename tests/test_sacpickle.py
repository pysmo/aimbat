"""
Run tests for the sacpickle.py module.

A lot of the tests here are a bit circular, in that the reference data are
calculated with the code we are testing. So the assumption is that the code
is correct at the time the reference data are calculated. This should still
mean that code breaking changes in the future will be detected.
"""

import pytest
import os
import bz2
import gzip
import pickle
import shutil
import numpy as np
import numpy.testing as npt
from pysmo import SacIO
from glob import glob
from pysmo.aimbat import sacpickle


_curdir = os.path.dirname(__file__)
_sacfiles = glob(_curdir + '/test_files/*/*.BHZ')
_pklfile = _curdir + '/test_files/sac.pkl'


@pytest.fixture()
def sacfiles(tmpdir):
    """
    Copy reference SAC files to the working tmp directory and
    return a list of the copied files.
    """
    filenames = []
    for sacfile in _sacfiles:
        new_filename = f"{tmpdir}/{os.path.basename(sacfile)}"
        shutil.copy(sacfile, new_filename)
        filenames.append(new_filename)
    return(filenames)


@pytest.fixture()
def pklfile(tmpdir):
    """
    Copy reference pickle file to the working tmp directory and
    return the full filename.
    """
    new_filename = str(tmpdir + os.path.basename(_pklfile))
    shutil.copy(_pklfile, new_filename)
    return(new_filename)


@pytest.fixture()
def testdata(tmpdir):
    """
    Create some simple test data and generate pickle files.
    """
    test_array = np.sin(np.linspace(-np.pi, np.pi, 1000))
    test_pickle = tmpdir + '/test.pkl'
    test_pickle_gz = tmpdir + '/test.pkl.gz'
    test_pickle_bz2 = tmpdir + '/test.pkl.bz2'
    pickle.dump(test_array, open(test_pickle, "wb"))
    pickle.dump(test_array, gzip.open(test_pickle_gz, "wb"))
    pickle.dump(test_array, bz2.open(test_pickle_bz2, "wb"))
    return(test_array, test_pickle, test_pickle_gz, test_pickle_bz2)


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


@pytest.mark.depends(on=["test_zipFile"])
def test_writePickle(tmpdir, testdata):
    """
    Test writing a simple string variable to a pickle.
    """
    test_array, *_ = testdata
    outfile = tmpdir + '/writePickle.pkl'
    outfile_gz = tmpdir + '/writePickle.pkl.gz'
    outfile_bz2 = tmpdir + '/writePickle.pkl.bz2'
    sacpickle.writePickle(test_array, outfile, zipmode=None)
    assert all(pickle.load(open(outfile, "rb")) == test_array)
    sacpickle.writePickle(test_array, outfile, zipmode="gz")
    assert all(pickle.load(gzip.open(outfile_gz, "rb")) == test_array)
    sacpickle.writePickle(test_array, outfile, zipmode="bz2")
    assert all(pickle.load(bz2.open(outfile_bz2, "rb")) == test_array)
    return(test_array, outfile, outfile_gz, outfile_bz2)


@pytest.mark.depends(on=["test_zipFile"])
def test_readPickle(tmpdir, testdata):
    """
    Test reading a simple variable from a pickle.
    """
    test_array, test_pickle, test_pickle_gz, test_pickle_bz2, *_ = testdata
    assert all(sacpickle.readPickle(test_pickle, zipmode=None) == test_array)
    assert all(sacpickle.readPickle(test_pickle, zipmode='gz') == test_array)
    assert all(sacpickle.readPickle(test_pickle, zipmode='bz2') == test_array)


@pytest.mark.depends(on=["test_resampleSeis"])
def test_SacDataHdrs(sacfiles, tmpdir):
    """
    Test reading header values from a SAC file.
    """
    _delta_multiplier = 10
    infile = sacfiles[0]
    test_sdh = sacpickle.SacDataHdrs(infile)
    assert test_sdh.filename == f"{tmpdir}/AR.113A.__.BHZ"
    assert test_sdh.thdrs[0] == pytest.approx(678.967)
    assert test_sdh.users[0] == pytest.approx(0.994858)
    assert test_sdh.kusers == ["True", "-1234567", "-1234567"]
    assert test_sdh.az == pytest.approx(50.73949)
    assert test_sdh.baz == pytest.approx(238.77966)
    assert test_sdh.dist == pytest.approx(9219.27636)
    assert test_sdh.gcarc == pytest.approx(82.841346)
    assert test_sdh.stla == pytest.approx(32.768299)
    assert test_sdh.stlo == pytest.approx(-113.76670)
    assert test_sdh.stel == pytest.approx(0.1180)
    assert test_sdh.staloc == [test_sdh.stla, test_sdh.stlo, test_sdh.stel]
    assert test_sdh.filename == infile
    assert test_sdh.data[0] == pytest.approx(-2.9874900e-08)
    assert test_sdh.delta == pytest.approx(0.0250)
    assert test_sdh.npts == 4001
    assert test_sdh.b == pytest.approx(638.97003)
    assert test_sdh.e == pytest.approx(738.97003)
    assert test_sdh.o == 0
    assert test_sdh.kstnm == "113A"
    assert test_sdh.knetwk == "AR"
    assert test_sdh.netsta == "AR.113A"
    assert test_sdh.cmpaz == 0
    assert test_sdh.cmpinc == 0
    assert test_sdh.kcmpnm == "BHZ"

    # Same thing but with resampling
    newdelta = _delta_multiplier * test_sdh.delta
    test_resampled_sdh = sacpickle.SacDataHdrs(infile, delta=newdelta)
    assert test_resampled_sdh.delta == pytest.approx(0.250)
    assert test_resampled_sdh.npts == 400
    assert test_resampled_sdh.b == pytest.approx(638.97003)
    assert test_resampled_sdh.e == pytest.approx(738.97003)

    # test resampleData method - this should make the two instances
    # created above equal.
    test_sdh.resampleData(newdelta)
    assert test_sdh.delta == test_resampled_sdh.delta
    assert test_sdh.npts == test_resampled_sdh.npts
    assert all(test_sdh.data == test_resampled_sdh.data)

    # test gethdr method
    assert test_sdh.gethdr('t1') == pytest.approx(679.167297)
    assert test_sdh.gethdr('u1') == pytest.approx(1.482726097)
    assert test_sdh.gethdr('k1') == '-1234567'
    with pytest.raises(ValueError):
        assert test_sdh.gethdr('invalid_input')

    # test sethdr method
    test_sdh.sethdr('k1', 'aimbat')
    assert test_sdh.gethdr('k1') == 'aimbat'
    with pytest.raises(ValueError):
        assert test_sdh.sethdr('invalid_header', 'aimbat')

    # test writeHdrs method.
    # (also calls sethdrs method, so that is also tested).
    test_sdh.writeHdrs()
    sacobj = SacIO.from_file(test_sdh.filename)
    assert sacobj.kuser1.rstrip('\x00') == 'aimbat'
    del sacobj

    # test the savesac method.
    del test_sdh
    testfile = str(tmpdir + '/savesac.sac')
    shutil.copy(sacfiles[0], testfile)
    test_sdh_tmp = sacpickle.SacDataHdrs(testfile)
    test_sdh_tmp.savesac()
    del test_sdh_tmp
    sac_org = SacIO.from_file(sacfiles[0])
    sac_tmp = SacIO.from_file(testfile)
    assert sac_org.data == sac_tmp.data
    assert sac_org.b == sac_tmp.b
    assert sac_org.e == sac_tmp.e
    assert sac_org.delta == sac_tmp.delta
    del sac_org
    del sac_tmp


@pytest.mark.depends(on=["test_jul2date", "test_SacDataHdrs"])
def test_SacGroup(sacfiles):
    test_group = sacpickle.SacGroup(sacfiles)
    assert test_group.event == [2011, 9, 15, 19, 31, 4.08, -21.611000061035156,
                                -179.5279998779297, 644.6, 7.300000190734863]
    delta_org = test_group.saclist[0].delta
    del test_group
    test_group = sacpickle.SacGroup(sacfiles, delta=delta_org*10)
    assert test_group.saclist[0].delta == delta_org*10


def test_resampleSeis(testdata):
    """
    Resample test data and compare a few corresponding points in
    the old/new data.
    """
    test_array, *_ = testdata
    delta_old = 0.1
    delta_new = 1
    resampled, delta_calc = sacpickle.resampleSeis(test_array, delta_old,
                                                   delta_new)
    assert delta_calc == 1
    assert resampled[10] == pytest.approx(test_array[100], rel=1e-4)
    assert resampled[20] == pytest.approx(test_array[200], rel=1e-4)
    assert resampled[30] == pytest.approx(test_array[300], rel=1e-4)
    assert resampled[40] == pytest.approx(test_array[400], rel=1e-4)


@pytest.mark.depends(on=["test_SacGroup"])
def test_sac2obj(sacfiles):
    assert isinstance(sacpickle.sac2obj(sacfiles), sacpickle.SacGroup)


@pytest.mark.depends(on=["test_SacGroup", "test_writePickle"])
def test_sac2pkl(tmpdir, pklfile):
    """
    Convert a group of SAC files to a pickle file and compare output
    to a reference pickle file. Direct comparison of the binary files
    is a bit tricky, so instead the files are unpickled again and then
    compared.
    """
    outfile = tmpdir + '/sac2pkl.pkl'
    outfile_gz = tmpdir + '/sac2pkl.pkl.gz'
    outfile_bz2 = tmpdir + '/sac2pkl.pkl.bz2'
    sacpickle.sac2pkl(_sacfiles, pkfile=outfile, zipmode=None)
    assert pickle.load(open(outfile, "rb")).stadict == \
        pickle.load(open(pklfile, "rb")).stadict
    sacpickle.sac2pkl(_sacfiles, pkfile=outfile, zipmode='gz')
    assert pickle.load(gzip.open(outfile_gz, "rb")).stadict == \
        pickle.load(open(pklfile, "rb")).stadict
    sacpickle.sac2pkl(_sacfiles, pkfile=outfile, zipmode='bz2')
    assert pickle.load(bz2.open(outfile_bz2, "rb")).stadict == \
        pickle.load(open(pklfile, "rb")).stadict


@pytest.mark.depends(on=["test_SacGroup", "test_writePickle"])
def test_obj2sac(sacfiles):
    """
    Test the obj2sac function. The test is done by resampling the
    members of the sacgroup which is written to disk and compare
    it to the original files.
    """
    sacobj = SacIO.from_file(sacfiles[0])
    delta_org = sacobj.delta
    del sacobj
    gsac = sacpickle.SacGroup(sacfiles, delta=10*delta_org)
    sacpickle.obj2sac(gsac)
    sacobj = SacIO.from_file(sacfiles[0])
    delta_new = sacobj.delta
    assert delta_new == pytest.approx(delta_org * 10)


@pytest.mark.depends(on=["test_obj2sac", "test_readPickle", "test_sac2pkl"])
def test_pkl2sac(sacfiles, tmpdir):
    """
    Test the pkl2sac function. We create a new pickle file first
    so that we don't overwrite the reference sac files.
    """
    sac_org = SacIO.from_file(sacfiles[0])
    data_org = sac_org.data
    del sac_org
    mtime_org = os.path.getmtime(sacfiles[0])
    tmp_pkl_file = str(tmpdir + '/tmp.pkl')
    sacpickle.sac2pkl(sacfiles, pkfile=tmp_pkl_file, zipmode=None)
    sacpickle.pkl2sac(tmp_pkl_file, zipmode=None)
    sac_new = SacIO.from_file(sacfiles[0])
    mtime_new = os.path.getmtime(sacfiles[0])
    # check the sac file has been changed/overwritten
    assert mtime_new != mtime_org
    # but that the data are still the same
    assert data_org == sac_new.data


def test_date2jul():
    """
    Test the date2jul function.
    """
    assert sacpickle.date2jul(2001, 7, 19) == 200
    assert sacpickle.date2jul(2000, 2, 29) == 60
    assert sacpickle.date2jul(2100, 3, 1) == 60


def test_jul2date():
    """
    Test the jul2date function.
    """
    assert sacpickle.jul2date(2001, 200) == (7, 19)
    assert sacpickle.jul2date(2000, 60) == (2, 29)
    assert sacpickle.jul2date(2100, 60) == (3, 1)


def test_taper(testdata):
    """
    Test the taper function.
    """
    data, *_ = testdata

    # test hanning taper
    hanning = sacpickle.taper(data, taperwidth=0.1, tapertype='hanning')[:5]
    hanning_expected = np.array([0, -6.20537998e-06, -4.95930794e-05,
                                 -1.67095920e-04, -3.95149146e-04])
    npt.assert_array_almost_equal(hanning, hanning_expected)

    # test hanning taper, but with different width
    hanning = sacpickle.taper(data, taperwidth=0.2, tapertype='hanning')[:5]
    hanning_expected = np.array([0, -1.551728e-06, -1.241051e-05,
                                 -4.186688e-05, -9.917831e-05])
    npt.assert_array_almost_equal(hanning, hanning_expected)

    # test hamming taper
    hamming = sacpickle.taper(data, taperwidth=0.1, tapertype='hamming')[:5]
    hamming_expected = np.array([-9.797174e-18, -5.088636e-04, -1.051915e-03,
                                 -1.663113e-03, -2.375957e-03])
    npt.assert_array_almost_equal(hamming, hamming_expected)

    # test cosine taper
    cosine = sacpickle.taper(data, taperwidth=0.1, tapertype='cosine')[:5]
    cosine_expected = np.array([0, -3.103456e-06, -2.482103e-05,
                                -8.373377e-05, -1.983566e-04])
    npt.assert_array_almost_equal(cosine, cosine_expected)


def test_taperWindow():
    """
    Test the taperwindow function.
    """
    timewindow = (1.75, 2.25)
    assert sacpickle.taperWindow(timewindow) == pytest.approx(0.05555555555)
    assert sacpickle.taperWindow(timewindow, taperwidth=0.2) == 0.125


def test_windowIndex(sacfiles):
    """
    Test the windowIndex function.
    """
    sdhlist = [sacpickle.SacDataHdrs(sacfile) for sacfile in sacfiles[:3]]
    reftimes = [648, 661, 663]
    start, total = sacpickle.windowIndex(sdhlist, reftimes)
    assert start == [141, 145, 165]
    assert total == 441


@pytest.mark.depends(on=["test_taper"])
def test_windowData(sacfiles):
    """
    Test the windowData function.
    """
    sdhlist = [sacpickle.SacDataHdrs(sacfile) for sacfile in sacfiles[:3]]
    nstart = [141, 145, 165]
    ntotal = 441
    window_data = sacpickle.windowData(sdhlist, nstart, ntotal, taperwidth=0.1)
    assert sum(window_data[0]) == pytest.approx(1.8043414065283498e-06)
    assert sum(window_data[1]) == pytest.approx(-1.0954959457874985e-06)
    assert sum(window_data[2]) == pytest.approx(4.744353712703557e-07)


def test_windowTime(sacfiles):
    """
    Test the windowTime function.
    """
    sdhlist = [sacpickle.SacDataHdrs(sacfile) for sacfile in sacfiles[:3]]
    nstart = [141, 145, 165]
    ntotal = 441
    timewin = sacpickle.windowTime(sdhlist, nstart, ntotal, taperwidth=0.1)
    assert sum(timewin[0]) == pytest.approx(285771.3215559711)
    assert sum(timewin[1]) == pytest.approx(291504.30540672585)
    assert sum(timewin[2]) == pytest.approx(292386.30541001156)


@pytest.mark.depends(on=["test_taper"])
def test_windowTimeData(sacfiles):
    """
    Test the windowTimeData function
    """
    sdhlist = [sacpickle.SacDataHdrs(sacfile) for sacfile in sacfiles[:3]]
    nstart = [141, 145, 165]
    ntotal = 441
    timecut, datacut = sacpickle.windowTimeData(sdhlist, nstart, ntotal,
                                                taperwidth=0.1)
    assert sum(timecut[0]) == pytest.approx(285771.3215559711)
    assert sum(timecut[1]) == pytest.approx(291504.30540672585)
    assert sum(timecut[2]) == pytest.approx(292386.30541001156)
    assert sum(datacut[0]) == pytest.approx(1.8043414065283498e-06)
    assert sum(datacut[1]) == pytest.approx(-1.0954959457874985e-06)
    assert sum(datacut[2]) == pytest.approx(4.744353712703557e-07)


@pytest.mark.depends(on=["test_SacGroup", "test_fileZipMode"])
def test_loadData(sacfiles, pklfile):
    class DummyClass():
        pass
    # loadData does not use the options from the parser in
    # sackpickle.py. This is a bit confusing.
    opts = DummyClass()
    para = DummyClass()
    opts.srate = -1
    gsac_from_sacfiles = sacpickle.loadData(sacfiles, opts, para)
    gsac_from_pklefile = sacpickle.loadData([pklfile], opts, para)
    assert isinstance(gsac_from_sacfiles, sacpickle.SacGroup)
    assert isinstance(gsac_from_pklefile, sacpickle.SacGroup)
    assert gsac_from_pklefile.saclist == gsac_from_pklefile.saclist
    assert gsac_from_pklefile.event == gsac_from_pklefile.event


def test_saveData(sacfiles):
    class DummyClass():
        pass
    # saveData does not use the options from the parser in
    # sackpickle.py. This is a bit confusing.
    opts = DummyClass()
    opts.filemode = "sac"
    gsac = sacpickle.SacGroup(sacfiles)
    gsac.saclist[0].sethdr("k1", "aimbat")
    sacpickle.saveData(gsac, opts)
    assert SacIO.from_file(sacfiles[0]).kuser1.rstrip('\x00') == "aimbat"


def test_get_arguments(sacfiles):
    """
    Test the get_arguments function.
    """
    test_args = ["prog"]
    test_args.extend(sacfiles)
    opts, files = sacpickle.get_arguments(test_args)
    assert files.sort() == sacfiles.sort()
    # check defaults which is sac2p
    for arg in ["", "-s", "--s2p"]:
        assert opts.delta == -1
        assert opts.ofilename == "sac.pkl"
        assert opts.s2p is True
        assert opts.p2s in [None, False]
        assert opts.zipmode is None
    # check pickle2sac
    for arg in ["-p", "--p2s"]:
        test_args = ["prog", arg]
        test_args.extend(sacfiles)
        opts, files = sacpickle.get_arguments(test_args)
        assert opts.p2s is True
        assert opts.s2p in [None, False]
    # check delta
    for arg in ["-d 1", "--delta=1"]:
        test_args = ["prog", arg]
        test_args.extend(sacfiles)
        opts, files = sacpickle.get_arguments(test_args)
        assert opts.delta == 1
    # check ofilename
    for arg in ["-o aimbat.pkl", "--ofilename=aimbat.pkl"]:
        test_args = ["prog", arg]
        test_args.extend(sacfiles)
        opts, files = sacpickle.get_arguments(test_args)
        assert opts.ofilename.strip() == "aimbat.pkl"
    # check zipmode
    for arg in ["-z gz", "-z bz2", "--zipmode=gz", "--zipmode=bz2"]:
        test_args = ["prog", arg]
        test_args.extend(sacfiles)
        opts, files = sacpickle.get_arguments(test_args)
        assert opts.zipmode.strip() in ["gz", "bz2"]
