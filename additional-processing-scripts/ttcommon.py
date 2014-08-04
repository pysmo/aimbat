#!/usr/bin/env python
"""
File: ttcommon.py

Commons for travel time processing.


Formats and file names related:
  class Formats
  class Filenames
  function mcNme

Function getPDE and readPDE 
  for processing earthquake catalog: hypocenter and origin time.
  Not restricted to PDE, HDS, GS...

PDE: Preliminary Determination of Epicenters
HDS: Multi-Catalog Historical Earthquake Data Base

** Ugly PDE style, change to explicit style.



xlou 04/29/2011
"""

from numpy import array, loadtxt
import sys
try:
	import cPickle as pickle
except:
	import pickle


def writePickle(d, picklefile):
	print('Write pickle to file: '+picklefile)
	fh = open(picklefile, 'w')
	pickle.dump(d, fh)
	fh.close()
	
def	readPickle(picklefile):
	print('Read pickle from file: '+picklefile)
	fh = open(picklefile, 'r')
	d = pickle.load(fh)
	fh.close()
	return d

class Filenames:
	""" Store file names """
	def __init__(self):
		self.moddir = '/Users/lkloh/aimbat/models/'
		self.staloc = 'loc.sta'
		self.evtloc = 'loc.evt'
		self.refsta = 'ref.tsta'
		self.refeqs = 'ref.teqs'
		self.refray = 'ref.rays'
		self.stacal = 'ref.tcals'
		self.evtcal = 'ref.tcale'
		#self.stacut = 'cut.sta_cut'
		self.evstloc = 'ref.evst'
		self.ccrust = 'ref.csta'


class Formats:
	""" 
	Store formats of files and file names. 
	Format of loc.sta:
		E.g.: ' SLM      38.63556   -90.23600   0.161 '
	Format of mccc output filename (mcname):
		E.g.: 19600102.03214806.mc for an event on 1960/01/02 03:21:48.06.
	Format of mccc output file (mcfile):
		E.g.: ' SLM      10.6667    0.0000    0.0600    0.1200    0 ehb \n'
	Format of mccc2delay file (sxfile): 
		mcfile[:-1] + 4%9.4f + mcfile[-1]
	Format of pde: origin time + hypo + magnitudes
		E.g.: DEQ 196001020321480617697S069244W1446  0mb             60Ms 
	"""
	def __init__(self):
		self.staloc = ' {0:<9s} {1:10.5f} {2:11.5f} {3:7.3f} \n'
		self.mcname = '{0!s:0>4}{1!s:0>2}{2!s:0>2}.{3!s:0>2}{4!s:0>2}{5!s:0>4}.mc'
		self.mcfile = ' {0:<9s} {1:9.4f} {2:9.4f} {3:>9.4f} {4:>9.4f} {5:4d}  {6:<s} \n'
		self.sxfile = ' {0:<9s} {1:9.4f} {2:9.4f} {3:>9.4f} {4:>9.4f} {5:4d} '
		self.sxfile += ' {6:9.4f} {7:9.4f} {8:9.4f} {9:9.4f}  {10:<s} \n'
#		self.sxfile = '{0:s} {1:9.4f} {2:9.4f} {3:9.4f} {4:9.4f} {5:<s}'
		self.mchead = 'station,  obstt,   fprec,   wgt,   elcor,    pol     \n'
		pde  = '{0:4s}{1!s:0>4}{2!s:0>2}{3!s:0>2}{4!s:0>2}{5!s:0>2}{6!s:0>4}'
		pde += '{7!s:0>5}{8:1s}{9!s:0>6}{10:1s}{11!s:0>4} '
		pde += '{12!s:>2}mb             {13!s:>2}Ms'
		self.pde = pde
		self.refray = '{0:>7d} {1:s} {2:<9s} {3:9.4f} {4:7.5f} {5:6.5f} {6:9.6f} {7:9.6f} {8:9.4f} {9:8.5f} {10:8s} \n'
		event  = '{0:<6s} {1:4d} {2:2d} {3:2d} {4:2d} {5:2d} {6:5.2f} '
		event += '{7:9.3f} {8:9.3f} {9:6.1f} {10:4.1f} {11:4.1f} '
		self.event = event

	def example(self):
		sta, slat, slon, selv = ['SLM   ', 38.63556, -90.23600, 0.161]
		isol, iyr, imon, iday, ihr, imin, sec = ['DEQ', 1960, 1, 2, 3, 21, 48.06]
		elat, elon, depth, fmb, fms = [-17.697, -69.244, 144.6, 0.0, 6.0]
		sta, obstt, prec, elcor, wgt = ['SLM   ', 1060.94, 1, 0.06, 0.12]
		staloc = self.staloc.format(sta, slat, slon, selv)
		mcname = mcName(self.mcname, iyr, imon, iday, ihr, imin, sec)
		mcfile = self.mcfile.format(sta, obstt, prec, elcor, wgt, 0, 'file')
		pde = getPDE(self.pde, isol, iyr, imon, iday, ihr, imin, sec, elat, elon, depth, fmb, fms)
		event = self.event.format(isol, iyr, imon, iday, ihr, imin, sec, elat, elon, depth, fmb, fms)
		print('Example of staloc: \n' + staloc)
		print('Example of mcname: \n' + mcname)
		print('Example of mcfile: \n' + mcfile)
		print('Example of pde: \n' + pde)
		print('Example of event: \n' + event)
		self.eg_staloc = staloc
		self.eg_mcname = mcname
		self.eg_mcfile = mcfile
		self.eg_pde    = pde

def getVel0(tvel):
	""" Get surface P and S velocity """
	vals = loadtxt(tvel, skiprows=2)
	vel0 = vals[0][1:3]
	return vel0

def getVel(dpvpvs, dep):
	""" Get 1D velocity at a depth. """
	deps, velp, vels = dpvpvs
	n = len(deps)
	for i in range(n-1):
		d0, d1 = deps[i:i+2]
		if dep >= d0 and dep < d1:
			break
	dd = d1 - d0
	w1 = (dep-d0)/dd
	w0 = (d1-dep)/dd
	ww = array([w0,w1])
	vp = sum(ww * velp[i:i+2])
	vs = sum(ww * vels[i:i+2])
	vel1 = [vp, vs]
	return vel1
	

def mcName(fmt, iyr, imon, iday, ihr, imin, sec):
	""" Get MCCC output filename """
	isec = int(round(sec*100))
	mcname = fmt.format( iyr, imon, iday, ihr, imin, isec )
	return mcname


def getPDE(fmt, isol, iyr, imon, iday, ihr, imin, sec, elat, elon, depth, fmb, fms):
	""" Create pde line for the end of MCCC output """
	isec = int(round(sec*100))
	ilat = int(round(elat*1000))
	ilon = int(round(elon*1000))
	idep = int(round(depth*10))
	imb = int(round(fmb * 10))
	ims = int(round(fms * 10))
	if ilat >= 0:
		ns = 'N'
	else:
		ns = 'S'
		ilat = -ilat
	if ilon >= 0:
		ew = 'E'
	else:
		ew = 'W'
		ilon = -ilon
	pde = fmt.format( isol, iyr, imon, iday, ihr, imin, isec, ilat, ns, ilon, ew, idep, imb, ims )
	return pde

def readPDE(pde):
	""" Read origin time and hypocenter from pde. """
	isol = pde[:3]
	otime = pde[4:20]
	iyr = int(otime[:4])
	imon = int(otime[4:6])
	iday = int(otime[6:8])
	ihr = int(otime[8:10])
	imin = int(otime[10:12])
	sec = float(otime[12:16])/100.
	otime = [iyr, imon, iday, ihr, imin, sec]
	lat = float(pde[20:25])/1000.
	lon = float(pde[26:32])/1000.
	dep = float(pde[33:37])/10.
	ns = pde[25]
	ew = pde[32]
	if ns == 'S': lat = -lat
	if ew == 'W': lon = -lon
	mb = float(pde[38:40])/10
	ms = float(pde[55:57])/10
	return lat, lon, dep, otime, mb, ms



def readMLines(mcfile):
	""" 
	Read mccc and mccc2delay output file.
	Return three lists of lines.
	"""
	ifileh = open(mcfile, 'r')
	lines = ifileh.readlines()
	ifileh.close()
	nhead = 0
	for i in range(2):
		if lines[i][0] != ' ':
			nhead += 1

	headlines = [ lines[i] for i in range(nhead) ]
	mccclines, taillines = [], []
	for line in lines[nhead:]:
		if line[0] == ' ':
			mccclines.append(line)
		else:
			taillines.append(line)
	return headlines, mccclines, taillines

def parseMLines(mccclines, taillines):
	""" Parse lines of mccc file. Phase and PDE info in the last two lines.	"""
	phase = taillines[-2].split()[1]
	iyr, imon, iday, ihr, imin, sec, elat, elon, edep, fmb, fms = [ float(v) for v in taillines[-1].split()[1:] ]
	event = {}
	event['time'] = [ iyr, imon, iday, ihr, imin, sec ]
	for i in range(5): event['time'][i] = int(event['time'][i]) # convert float to int
	event['hypo'] = [ elat, elon, edep, fmb, fms ]
	stations = [ line.split()[0] for line in mccclines ]
	ttimes = array([ [ float(v) for v in line.split()[1:-1] ] for line in mccclines ])
	sacnames = [ line.split()[-1] for line in mccclines ]
	return phase, event, stations, ttimes, sacnames


def readStation(staloc, comment='#'):
	""" Read station location to a dict. """
	print('Read station file: '+staloc)
	stafile = open(staloc, 'r')
	stalines = stafile.readlines()
	stafile.close()
	stadict = {}
	for line in stalines:
		sline = line.split()
		if sline != [] and line[0] != comment:
			sta = sline[0]
			stadict[sta] = [ float(v) for v in sline[1:] ]
	return stadict

def writeStation(stadict, ofilename, fmt):
	""" Write station dict to ofile """
	ofile = open(ofilename, 'w')
	for sta, loc in sorted(stadict.items()):
		slat, slon, selv = loc
		ofile.write( fmt.format(sta, slat, slon, selv) )
	ofile.close()	

def saveStation(stadict, ofilename):
	""" Write station dict to file.
		Item of the dict has at least three fields such as lat/lon/elv and lat/lon/delay/std.
		Format is automatically adjusted according to number of fields.
	"""
	# convert dict to list
	values = [ [sta,] + stadict[sta]  for sta in sorted(stadict.keys()) ]
	fmt = ' {0:<9s} {1:10.5f} {2:11.5f} '
	nfmt = len(fmt.split())
	nval = len(values[0])
	for i in range(nfmt, nval):
		fmt += '{' + str(i) + ':8.3f} '
	fmt += '\n'
	print('Save dict to file "{0:s}" using format: {1:s}'.format(ofilename,fmt))
	ofile = open(ofilename, 'w')
	for line in values:
		ofile.write(fmt.format(*line))
	ofile.close()

if __name__ == '__main__':
	formats = Formats()
	formats.example()
	pde = formats.eg_pde
	readPDE(pde)

	tvel = '/iasp91.tvel'
	vals = loadtxt(tvel, skiprows=2)
	deps = vals[:,0]
	velp = vals[:,1]
	vels = vals[:,2]
	dpvpvs = deps, velp, vels
	dep = 5.
	vp, vs = getVel(dpvpvs, dep)
