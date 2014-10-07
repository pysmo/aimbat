#!/usr/bin/env python
#------------------------------------------------
# Filename: sacpickle.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2011-2012 Xiaoting Lou
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


from __future__ import with_statement
from numpy import array, linspace, arange, mean, ones, zeros, pi, cos, concatenate
from scipy import signal
from gzip import GzipFile
from bz2  import BZ2File
import os, sys, contextlib
from pysmo.sac.sacio import sacfile
try:
	import cPickle as pickle
except:
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
		raise ValueError, 'zipmode={:s} not in (bz2, gz)'.format(zipmode)
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
		with contextlib.closing(open(picklefile, 'w')) as f:
			pickle.dump(d, f, pickle.HIGHEST_PROTOCOL)
	else:
		zfile = zipFile(zipmode)
		with contextlib.closing(zfile(picklefile+'.'+zipmode, 'wb')) as f:
			pickle.dump(d, f, pickle.HIGHEST_PROTOCOL)
	
def readPickle(picklefile, zipmode=None):
	""" Read compressed pickle file to python objects.
	"""
	if zipmode is None:
		with contextlib.closing(open(picklefile, 'r')) as f:
			d = pickle.load(f)
	else:
		zfile = zipFile(zipmode)
		with contextlib.closing(zfile(picklefile+'.'+zipmode, 'rb')) as f:
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
		isac = sacfile(ifile, 'rw')
		nthdr = 10
		nkhdr = 3
		thdrs  = [-12345.,] * nthdr
		users  = [-12345.,] * nthdr
		kusers = ['-12345  ',] * nkhdr
		for i in range(nthdr):
			try:
				thdrs[i] = isac.__getattr__('t'+str(i))
			except:
				pass
			try:
				users[i] = isac.__getattr__('user'+str(i))
			except:
				pass
		for i in range(nkhdr):
			try:
				kusers[i] = isac.__getattr__('kuser'+str(i))#.rstrip()
			except:
				pass
		self.thdrs = thdrs
		self.users = users
		self.kusers = kusers
		self.az = isac.az
		self.baz = isac.baz
		self.dist = isac.dist
		self.gcarc = isac.gcarc
		stla, stlo, stel = isac.stla, isac.stlo, isac.stel*0.001
		self.stla = stla
		self.stlo = stlo
		self.stel = stel
		self.staloc = [stla, stlo, stel]
		self.filename = ifile
		# resample data if given a different positive delta
		self.data, self.delta = resampleSeis(array(isac.data), isac.delta, delta)
		self.npts = len(self.data)
		self.b = isac.b
		self.e = isac.e
		self.kstnm = isac.kstnm
		self.knetwk = isac.knetwk
		net = isac.knetwk.rstrip()
		sta = isac.kstnm.rstrip()
		self.netsta = net + '.' + sta
		isac.close()

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
			print 'Not a t_n, user_n or kuser_n header. Exit'
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
			print 'Not a t_n, user_n or kuser_n header. Exit'
			sys.exit()
		ind = int(hdr[-1])
		hdrs[ind] = val

	def writeHdrs(self):
		""" Write SAC headers (t_n, user_n, and kuser_n) in python obj to existing SAC file.
		"""
		sacobj = sacfile(self.filename+'.sac', 'rw')
		self.savehdrs(sacobj)
		sacobj.close()

	def savehdrs(self, sacobj):
		""" Write SAC headers (t_n, user_n, and kuser_n) in python obj to SAC obj.
		"""
		thdrs, users, kusers = self.thdrs, self.users, self.kusers
		nthdr = 10
		nkhdr = 3
		for i in range(nkhdr):
			sacobj.__setattr__('kuser'+str(i), kusers[i])
		for i in range(nthdr):
			sacobj.__setattr__('t'+str(i), thdrs[i])
			sacobj.__setattr__('user'+str(i), users[i])		
		
	def savesac(self):
		""" Save all data and header variables to an existing or new sacfile. """
		if os.path.isfile(self.filename):
			sacobj = sacfile(self.filename, 'rw')
		else:
			sacobj = sacfile(self.filename, 'new')
			sacobj.stla =  0
			sacobj.stlo =  0
			sacobj.stel =  0
		for hdr in ['b', 'npts', 'data', 'delta', 'gcarc', 'az', 'baz', 'dist', 'kstnm', 'knetwk']:
			sacobj.__setattr__(hdr, self.__dict__[hdr])
		self.savehdrs(sacobj)
		sacobj.close()

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
		stadict = {}
		saclist = []
		for ifile in ifiles:
			sacdh = SacDataHdrs(ifile, delta)
			stadict[sacdh.netsta] = sacdh.staloc
			saclist.append(sacdh)
			del sacdh.staloc
		self.stadict = stadict
		self.saclist = saclist
		self.ifiles = ifiles
		# get event info
		isac = sacfile(ifiles[0], 'ro')
		year, jday = isac.nzyear, isac.nzjday
		mon, day = jul2date(year, jday)
		try:
			mag = isac.mag
		except:
			mag = 0.
		self.event = [ year, mon, day, isac.nzhour, isac.nzmin, isac.nzsec+isac.nzmsec*0.001, isac.evla, isac.evlo, isac.evdp*0.001, mag ]
		try:
			self.kevnm = isac.kevnm
		except:
			self.kevnm = 'unknown event'
		isac.close()
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
		sacdh.writeHdrs()
	if 'stkdh' in gsac.__dict__:
		gsac.stkdh.savesac()
	
def pkl2sac(pkfile, zipmode):
	""" Save headers in python pickle to SAC files.
	"""
	pass

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
		print 'Unknown taper type: %s ! Exit' % tapertype
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
	nseis = len(saclist)
	delta = saclist[0].delta
	tw0, tw1 = timewindow
	twleft = tw0 - taperwindow*.5
	ntotal = int(round((tw1-tw0+taperwindow)/delta)) + 1
	nstart = [ int(round((twleft+reftimes[i]-saclist[i].b)/delta)) for i in range(nseis) ] 
	return nstart, ntotal

def windowData(saclist, nstart, ntotal, taperwidth, tapertype='hanning'):
	""" Cut data within a time window using given indices.
		Pad dat with zero if not enough sample.
	"""
	nseis = len(saclist)
	datawin = []
	for i in range(nseis):
		sacd = saclist[i].data
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
			print (saclist[i].netsta+': not enough sample around reftime. Pad left {0:d} right {1:d} zeros'.format(len(zpada),len(zpadb)))
		data -= mean(data)
		data = taper(data, taperwidth, tapertype)
		datawin.append(data)
	return array(datawin)

def windowTime(saclist, nstart, ntotal, taperwidth, tapertype='hanning'):
	""" Cut time within a time window using given indices.
	"""
	nseis = len(saclist)
	delta = saclist[0].delta
	timewin = []
	for i in range(nseis):
		sacdh = saclist[i]
		ta = sacdh.b + nstart[i]*delta
		tb = ta + ntotal*delta
		time = linspace(ta, tb, ntotal) 
		timewin.append(time)
	return array(timewin)

def windowTimeData(saclist, nstart, ntotal, taperwidth, tapertype='hanning'):
	""" Cut part of the time and data based on given indices.
	"""
	nseis = len(saclist)
	delta = saclist[0].delta
	timecut, datacut = [], []
	for i in range(nseis):
		sacdh = saclist[i]
		na = nstart[i] 
		nb = na + ntotal
		data = sacdh.data[na:nb].copy()
		data -= mean(data)
		data = taper(data, taperwidth, tapertype)
		ta = sacdh.b + nstart[i]*delta
		tb = ta + ntotal*delta
		#time = arange(ta, tb, delta) 
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
			isac = sacfile(ifile0, 'ro')
			delta = isac.delta
			isac.close()
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
	print ('Read {0:d} seismograms with sampling interval: {1:f}s'.format(len(gsac.saclist), opts.delta))
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


