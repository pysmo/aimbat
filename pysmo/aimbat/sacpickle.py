#!/usr/bin/env python
#------------------------------------------------
# Filename: sacpickle.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2011 Xiaoting Lou
#------------------------------------------------
"""
Python module for converting SAC files to python pickle data structure to increase 
data processing efficiency by avoiding frequent SAC file I/O.

Read and write SAC files are done only once each before and after data processing. 
Intermediate processing are performed on python objects and pickles. 
Changes made during data processing are not saved instantly, which is different from pysmo.


               disk I/O                        (un)pickling
SAC files <----------------> Python objects <----------------> pickle file
            sac2obj/obj2sac        |         read/writePickle
                                   v
                             data processing

Pickling and unpickling preserve python object hierarchy. See this website for documents:
    http://docs.python.org/library/pickle.html

Pickle files are optionally compressed using either bzip2 or gzip to save disk space.
    http://docs.python.org/library/bz2.html
    http://docs.python.org/library/gzip.html


Class SacDataHdrs reads in data and headers of a SAC file.
Class SacGroup includes SacDataHdrs of multiple SAC files.

Structure:
    SacGroup
         ||
    gsac.saclist + gsac.stadict       + gsac.event
         ||        (station locations)  (event origin and hypocenter)
         || 
    list of SacDataHdrs 
               ||
        sacdh.b/delta/npts/y
        sacdh.thdrs/users/kusers
        sacdh.az/baz/dist/gcarc
        sacdh.netsta/filename
        sacdh.staloc = [stla, stlo, stel]

gsac.event parameters:
    [ year, mon, day, isac.nzhour, isac.nzmin, isac.nzsec+isac.nzmsec*0.001, 
      isac.evla, isac.evlo, isac.evdp*0.001, mag ]

Time array is not saved in sacdh object but is generated and used in memeory. 
Time array is always in absolute sense. Reference time is an independent variable
 and relative is calculated whenever needed.

Function loadData() reads either SAC, pickle, .pkl.gz or .pkl.bz2 files into python object.
Output file type (filemode and zipmode) is always the same as input file.
Run script sac2pkl.py to convert SAC to pkl.


*** Note ***:
Don't pickle inside the __main__ namespace to avoid the following error in unpickling (readPickle):
    AttributeError: 'FakeModule' object has no attribute 'SacGroup'
http://stackoverflow.com/questions/3431419/how-to-get-unpickling-to-work-with-ipython


:copyright:
    Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""


from numpy import array, linspace, mean, ones, zeros, pi, cos, concatenate
from scipy import signal
from gzip import GzipFile
from bz2  import BZ2File
from pysmo.core.sac import SacIO
import os, sys
import pickle


# ############################################################################### #
#                                                                                 #
#                         MANIPULATING PICKLE FILES                               #
#                                                                                 #
# ############################################################################### #

def zipFile(zipmode='gz'):
    """ Return file compress method: bz2 or gz.
    """
    if zipmode not in (None, 'bz2', 'gz'):
        raise ValueError('zipmode={:s} not in (bz2, gz)'.format(zipmode))
    if zipmode == 'bz2':
        zfile = BZ2File
    elif zipmode == 'gz':
        zfile = GzipFile
    return zfile

def fileZipMode(ifilename):
    """ Determine if an input file is SAC, pickle or compressed pickle file
    """
    zipmode = ifilename.split('.')[-1] 
    if zipmode in ('bz2', 'gz'):
        filemode = 'pkl'
    elif zipmode == 'pkl':
        filemode = 'pkl'
        zipmode = None
    else:
        filemode = 'sac'
        zipmode = None
    return filemode, zipmode


def writePickle(d, picklefile, zipmode=None):
    """ Write python objects to pickle file and compress with highest protocal (binary) if zipmode is not None.
    """
    if zipmode is None:
        with open(picklefile, 'wb') as f:
            pickle.dump(d, f, pickle.HIGHEST_PROTOCOL)
    else:
        zfile = zipFile(zipmode)
        with open(zfile(picklefile+'.'+zipmode, 'wb')) as f:
            pickle.dump(d, f, pickle.HIGHEST_PROTOCOL)

def readPickle(picklefile, zipmode=None):
    """ Read compressed pickle file to python objects.
    """
    if zipmode is None:
        with open(picklefile, 'rb') as f:
            d = pickle.load(f)
    else:
        zfile = zipFile(zipmode)
        with open(zfile(picklefile+'.'+zipmode, 'rb')) as f:
            d = pickle.load(f)
    return d


            
# ############################################################################### #
#                                                                                 #
#                         MANIPULATING PICKLE FILES                               #
#                                                                                 #
# ############################################################################### #

# ############################################################################### #
#                                                                                 #
#                                CLASS: SacDataHdrs                               #
#                                                                                 #
# ############################################################################### #

class SacDataHdrs:
    """ Class for individual SAC file's data and headers.
    """
    def __init__(self, ifile, delta=-1):
        """ Read SAC file to python objects in memory.
        """
        print('Reading SAC file: '+ifile)
        isac = SacIO.from_file(ifile)
        nthdr = 10
        nkhdr = 3
        thdrs  = [-12345.,] * nthdr
        users  = [-12345.,] * nthdr
        kusers = ['-1234567',] * nkhdr
        for i in range(nthdr):
            thdr = getattr(isac, 't'+str(i))
            user = getattr(isac, 'user'+str(i))
            if thdr is not None:
                thdrs[i] = thdr
            if user is not None:
                users[i] = user
        for i in range(nkhdr):
            kuser = getattr(isac, 'kuser'+str(i))#.rstrip()
            if kuser is not None:
                kusers[i] = kuser
        self.thdrs = thdrs
        self.users = users
        self.kusers = kusers
        self.az = isac.az
        self.baz = isac.baz
        self.dist = isac.dist
        self.gcarc = isac.gcarc
        self.stla = isac.stla
        self.stlo = isac.stlo
        self.stel = isac.stel*0.001
        self.staloc = [self.stla, self.stlo, self.stel]
        self.filename = ifile
        # resample data if given a different positive delta
        self.data, self.delta = resampleSeis(array(isac.data), isac.delta, delta)
        self.npts = len(self.data)
        self.b = isac.b
        self.e = isac.e
        self.o = isac.o
        self.kstnm = isac.kstnm.replace('\x00','')
        self.knetwk = isac.knetwk.replace('\x00','')
        self.netsta = '.'.join([self.knetwk, self.kstnm])
        self.cmpaz = isac.cmpaz
        self.cmpinc = isac.cmpinc
        self.kcmpnm = isac.kcmpnm.replace('\x00','')
        del isac

    def resampleData(self, delta):
        self.data, self.delta = resampleSeis(self.data, self.delta, delta)
        self.npts = len(self.data)

    def gethdr(self, hdr):
        """ Read a header variable (t_n, user_n, or kuser_n).
        """
        if hdr[0] == 't':
            hdrs = self.thdrs
        elif hdr[0] == 'u':
            hdrs = self.users
        elif hdr[0] == 'k':
            hdrs = self.kusers
        else:
            print('Not a t_n, user_n or kuser_n header. Exit')
            sys.exit()
        ind = int(hdr[-1])
        return hdrs[ind]
    
    def sethdr(self, hdr, val):
        """ Write a header variable (t_n, user_n, or kuser_n).
        """
        if hdr[0] == 't':
            hdrs = self.thdrs
        elif hdr[0] == 'u':
            hdrs = self.users
        elif hdr[0] == 'k':
            hdrs = self.kusers
        else:
            print('Not a t_n, user_n or kuser_n header. Exit')
            sys.exit()
        ind = int(hdr[-1])
        hdrs[ind] = val

    def writeHdrs(self):
        """
        Write SAC headers (t_n, user_n, and kuser_n) in python obj to existing SAC file.
        """
        sacobj = SacIO.from_file(self.filename)
        self.sethdrs(sacobj)
        sacobj.write(self.filename)
        del sacobj

    def sethdrs(self, sacobj):
        """
        Write SAC headers (t_n, user_n, and kuser_n) in python obj to SAC obj.
        """
        thdrs, users, kusers = self.thdrs, self.users, self.kusers
        nthdr = 10
        nkhdr = 3
        for i in range(nkhdr):
            setattr(sacobj, 'kuser'+str(i), kusers[i])
        for i in range(nthdr):
            setattr(sacobj, 't'+str(i), thdrs[i])
            setattr(sacobj, 'user'+str(i), users[i])
        
    def savesac(self):
        """
        Save all data and header variables to an existing or new sacfile.
        """
        if os.path.isfile(self.filename):
            sacobj = SacIO.from_file(self.filename)
        else:
            fspl = self.filename.split('/')
            if len(fspl) > 1:
                os.system('mkdir -p '+ '/'.join(fspl[:-1]))
            sacobj = SacIO()
            sacobj.stla =  0
            sacobj.stlo =  0
            sacobj.stel =  0
        hdrs = ['o', 'b', 'delta', 'data', 'gcarc', 'az', 'baz', 'dist', 'kstnm', 'knetwk']
        hdrs += ['cmpaz', 'cmpinc', 'kcmpnm', 'stla', 'stlo', 'stel']
        for hdr in hdrs:
            setattr(sacobj, hdr, self.__dict__[hdr])
        self.sethdrs(sacobj)
        sacobj.write(self.filename)
        del sacobj

# ############################################################################### #
#                                                                                 #
#                                CLASS: SacDataHdrs                               #
#                                                                                 #
# ############################################################################### #

# ############################################################################### #
#                                                                                 #
#                                  CLASS: SacGroup                                #
#                                                                                 #
# ############################################################################### #

class SacGroup:
    """ Read a group of SAC files' headers and data to python objects in memory.
        Get event information.
    """
    def __init__(self, ifiles, delta=-1):
        self.stadict = {}
        self.saclist = []
        for ifile in ifiles:
            sacdh = SacDataHdrs(ifile, delta)
            self.stadict[sacdh.netsta] = sacdh.staloc
            self.saclist.append(sacdh)
            del sacdh.staloc
        # get event info
        isac = SacIO.from_file(ifiles[0])
        year, jday = isac.nzyear, isac.nzjday
        mon, day = jul2date(year, jday)
        mag = isac.mag or 0.
        self.event = [ year, mon, day, isac.nzhour, isac.nzmin, isac.nzsec+isac.nzmsec*0.001, isac.evla, isac.evlo, isac.evdp*0.001, mag ]
        self.idep = isac.idep
        self.iztype = isac.iztype
        self.kevnm = isac.kevnm or 'unknown'
        del isac
        if delta > 0:
            self.resampleData(delta)

    def resampleData(self, delta):
        """ resample data of all sacdh """
        for sacdh in self.saclist:
            sacdh.resampleData(delta)




# ############################################################################### #
#                                                                                 #
#                                  CLASS: SacGroup                                #
#                                                                                 #
# ############################################################################### #

def resampleSeis(data, deltaold, delta):
    """ Resample data of a seismogram if given a different positive delta """
    nptsold = len(data)
    npts = int(round(nptsold*deltaold/delta))
    if npts > 0 and npts != nptsold:
        data = signal.resample(data, npts)
    else:
        delta = deltaold
    return data, delta

def sac2obj(ifiles, delta=-1):
    """ Convert SAC files to python objects.
    """
    gsac = SacGroup(ifiles, delta)
    return gsac

def sac2pkl(ifiles, pkfile='sac.pkl', delta=-1, zipmode='gz'):
    """ Convert SAC files to python pickle files.
    """
    gsac = SacGroup(ifiles, delta)
    writePickle(gsac, pkfile, zipmode)

def obj2sac(gsac):
    """ Save headers in python objects to SAC files.
    """
    for sacdh in gsac.saclist:
        sacdh.savesac()
        # save more headers 
        nzyear, mon, day, nzhour, nzmin, nzsec, evla, evlo, evdp, mag = gsac.event
        kevnm = gsac.kevnm
        idep = gsac.idep
        iztype = gsac.iztype
        nzjday = date2jul(nzyear, mon, day)
        nzmsec = int(round((nzsec - int(nzsec))*1000))
        nzsec = int(nzsec)
        evdp *= 1000
        stla, stlo, stel = gsac.stadict[sacdh.netsta]
        stel *= 1000
        hdrs = ['nzyear', 'nzjday', 'nzhour', 'nzmin', 'nzsec', 'nzmsec', 'evla', 'evlo', 'evdp', 'mag', ]
        hdrs += ['stla', 'stlo', 'stel' ]
        hdrs += ['kevnm', 'idep', 'iztype']
        for sacdh in gsac.saclist:
                sacobj = SacIO.from_file(sacdh.filename)
                for hdr in hdrs:
                        setattr(sacobj, hdr, eval(hdr))
                sacobj.write(sacdh.filename)
                del sacobj
    if 'stkdh' in gsac.__dict__:
        gsac.stkdh.savesac()

def pkl2sac(pkfile, zipmode):
    """ Save headers in python pickle to SAC files.
    """
    gsac = readPickle(pkfile, zipmode)
    obj2sac(gsac)

def _days(year):
    """ Get number of days for each month of a year."""
    idays = [31, 0, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if year%4 == 0:
        idays[1] = 29
    else:
        idays[1] = 28
    return idays

def date2jul(year, mon, day):
    """ date --> julian day """
    idays = _days(year)
    jday = 0
    for i in range(mon-1):
        jday += idays[i]
    jday += day
    return jday

def jul2date(year, jday):
    """ julian day --> date """
    idays = _days(year)
    mon = 1
    while jday > idays[mon-1]:
        jday -= idays[mon-1]
        mon += 1
    return mon, jday

def taper(data, taperwidth=0.1, tapertype='hanning'):
    """ Apply a symmetric taper to each end of data.
        http://www.iris.edu/software/sac/commands/taper.html
        Default width: 0.1/2=0.05 on each end.
    """
    if taperwidth == 0: return data
    npts = len(data)
    if npts == 0:
        print ('Zero length data. Exit')
        sys.exit()
    taperlen = round(0.5*taperwidth*npts)
    taperdata = ones(npts)
    if tapertype == 'hanning':
        f0, f1, w = 0.5, 0.5, pi/taperlen
    elif tapertype == 'hamming':
        f0, f1, w = 0.54, 0.46, pi/taperlen
    elif tapertype == 'cosine':
        f0, f1, w = 1, 1, pi/taperlen/2
    else:
        print(('Unknown taper type: {:s} ! Exit'.format(tapertype)))
        sys.exit(1)
    for i in range(npts):
        if i <= taperlen:
            taperdata[i] = f0 - f1 * cos(w*i)
        elif i >= npts-taperlen:
            taperdata[i] = f0 - f1 * cos(w*(npts-i-1))
    taperdata *= data
    return taperdata

def taperWindow(timewindow, taperwidth=0.1):
    """ Calculate length of taper window from time window so that:
        taperwidth = (taperwindow)/(taperwindow+timewindow)
    """
    return taperwidth/(1.0-taperwidth)*(timewindow[1]-timewindow[0])

def windowIndex(saclist, reftimes, timewindow=(-5.0,5.0), taperwindow=1.0):
    """ Calculate indices for cutting data at a time window and taper window.
        Indices nstart and notal bound the entire window, which is sum of time window and taper window.
        Only the taper window part of data is tapered:            __-----------__
        The original MCCC code defines taper window differently:  ____-------____
        Parameters
        ----------
        saclist:  list of sacdh 
        reftimes: list of reference times for the time window
        timewindow: relative time window to cut data
        taperwindow: length of taper window
        nstart: index of first sample point of datacut in each sacdh.data
        ntotal: length of data within the time window
    """
    delta = saclist[0].delta
    tw0, tw1 = timewindow
    twleft = tw0 - taperwindow*.5
    ntotal = int(round((tw1-tw0+taperwindow)/delta)) + 1
    nstart = [ int(round((twleft+reftimes[i]-saclist[i].b)/delta)) for i in range(len(saclist)) ] 
    return nstart, ntotal

def windowData(saclist, nstart, ntotal, taperwidth, tapertype='hanning', datatype='data'):
    """ Cut data within a time window using given indices.
        Pad dat with zero if not enough sample.
        Use sacdh.data or sacdh.datamem based on data type
    """
    datawin = []
    if datatype == 'data':
        datalist = [ sacdh.data     for sacdh in saclist ]
    elif datatype == 'datamem':
        datalist = [ sacdh.datamem  for sacdh in saclist ]
    for i in range(len(saclist)):
        sacd = datalist[i]
        na = nstart[i] 
        nb = na + ntotal
        data = sacd[na:nb].copy()
        if len(data) < ntotal:
            nd = len(sacd)
            zpada = zeros(max(0, -na))
            zpadb = zeros(max(nb-nd,0))
            na0 = max(0, na)
            nb0 = min(nb,nd)
            data = concatenate((zpada, sacd[na0:nb0], zpadb))
            print((saclist[i].netsta+': not enough sample around reftime. Pad left {0:d} right {1:d} zeros'.format(len(zpada),len(zpadb))))
        data -= mean(data)
        data = taper(data, taperwidth, tapertype)
        datawin.append(data)
    return array(datawin)

def windowTime(saclist, nstart, ntotal, taperwidth, tapertype='hanning'):
    """ Cut time within a time window using given indices.
    """
    delta = saclist[0].delta
    timewin = []
    for i in range(len(saclist)):
        sacdh = saclist[i]
        ta = sacdh.b + nstart[i]*delta
        tb = ta + ntotal*delta
        time = linspace(ta, tb, ntotal) 
        timewin.append(time)
    return array(timewin)

def windowTimeData(saclist, nstart, ntotal, taperwidth, tapertype='hanning'):
    """ Cut part of the time and data based on given indices.
    """
    delta = saclist[0].delta
    timecut, datacut = [], []
    for i in range(len(saclist)):
        sacdh = saclist[i]
        na = nstart[i] 
        nb = na + ntotal
        data = sacdh.data[na:nb].copy()
        data -= mean(data)
        data = taper(data, taperwidth, tapertype)
        ta = sacdh.b + nstart[i]*delta
        tb = ta + ntotal*delta
        time = linspace(ta, tb, ntotal) 
        datacut.append(data)
        timecut.append(time)
    return array(timecut), array(datacut)


def loadData(ifiles, opts, para):
    """ Load data either from SAC files or (gz/bz2 compressed) pickle file.
        Get sampling rate from command line option or default config file.
        Resample data if a positive sample rate is given.
        Output file type is the same as input file (filemode and zipmode do not change).
        If filemode == 'sac': zipmode = None
        If filemode == 'pkl': zipmode = None/bz2/gz 
    """
    if opts.srate is not None:
        srate = opts.srate
    else:
        srate = para.srate
    ifile0 = ifiles[0]
    filemode, zipmode = fileZipMode(ifile0)
    opts.filemode = filemode
    opts.zipmode = zipmode
    if filemode == 'sac':
        if srate <= 0:
            isac = SacIO.from_file(ifile0)
            delta = isac.delta
            del isac
        else:
            delta = 1.0/srate
        gsac = sac2obj(ifiles, delta)
        opts.delta = delta
        opts.pklfile = None
    elif len(ifiles) > 1:
        print('More than one pickle file given. Exit.')
        sys.exit()
    else:
        if zipmode is not None:
            pklfile = ifile0[:-len(zipmode)-1]
        else:
            pklfile = ifile0
        gsac = readPickle(pklfile, zipmode)
        opts.pklfile = pklfile
        if srate > 0:
            sacdh0 = gsac.saclist[0]
            if int(round(sacdh0.npts * sacdh0.delta * srate)) != sacdh0.npts:
                gsac.resampleData(1./srate)
        opts.delta = gsac.saclist[0].delta

    # warn user if sampling rates are inconsistent
    class BreakIt(Exception): pass
    length_of_saclist = len(gsac.saclist)
    try:
        for k in range(length_of_saclist):
            for j in range(length_of_saclist):
                if gsac.saclist[k].delta - gsac.saclist[j].delta > 0.01:
                    print('WARNING: sampling rates inconsistent. If sampling rates not all equal, errors in cross correlation may occur.')
                    raise BreakIt
    except BreakIt:
        pass

    print(('Read {0:d} seismograms with sampling interval: {1:f}s'.format(len(gsac.saclist), opts.delta)))
    return gsac 


# saves headers for TTPICK.PY
def saveData(gsac, opts):
    """ Save pickle or sac files.
    """
    if opts.filemode == 'sac':
        for sacdh in gsac.saclist: 
            sacdh.writeHdrs()
        if 'stkdh' in gsac.__dict__:
            gsac.stkdh.savesac()
    elif opts.filemode == 'pkl':
        writePickle(gsac, opts.pklfile, opts.zipmode)
    else:
        print ('Unknown file type. Exit..')
        sys.exit()
    print ('SAC headers saved!')


def getOptions():
    """ Parse arguments and options. """
    from optparse import OptionParser
    usage = "Usage: %prog [options] <sacfile(s)>"
    parser = OptionParser(usage=usage)

    ofilename = 'sac.pkl'
    delta = -1
    parser.set_defaults(delta=delta)
    parser.set_defaults(ofilename=ofilename)
    parser.add_option('-s', '--s2p', action="store_true", dest='s2p',
        help='Convert SAC files to pickle file. Default is True.')
    parser.add_option('-p', '--p2s', action="store_true", dest='p2s',
        help='Convert pickle file (save headers) to SAC files.')
    parser.add_option('-d', '--delta',  dest='delta', type='float',
        help='Time sampling interval. Default is %f ' % delta)
    parser.add_option('-o', '--ofilename',  dest='ofilename', type='str',
        help='Output filename which works only with -s option.')
    parser.add_option('-z', '--zipmode',  dest='zipmode', type='str',
        help='Zip mode: bz2 or gz. Default is None.')

    opts, files = parser.parse_args(sys.argv[1:])
    opts.s2p = True
    if opts.p2s:
        opts.s2p = False
    if len(files) == 0:
        print(parser.usage)
        sys.exit()
    return opts, files

def main():
    opts, ifiles = getOptions()
    if opts.s2p:
        print('File conversion: sac --> pkl')
        sac2pkl(ifiles, opts.ofilename, opts.delta, opts.zipmode)
    elif opts.p2s:
        print('File conversion: pkl --> sac')
        filemode, zipmode = fileZipMode(ifiles[0])
        for pkfile in ifiles:
            pkl2sac(pkfile, zipmode)

if __name__ == '__main__':
    main()
