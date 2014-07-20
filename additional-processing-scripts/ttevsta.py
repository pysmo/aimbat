#!/usr/bin/env python
"""
Invert delay times for (nsta + nevt*4 + nreg) terms in an over determined linear system using lsqr.

Station term: nsta
Event terms: otime, lat, lon, dep
Region termns: 2 ( west and east)

buildGD0 : event terms  nevt*1 (ot) 
buildGD1 : event terms  nevt*1 (ot)          + region 2 
buildGD2 : event terms  nevt*2 (ot,dp)       + region 2
buildGD3 : event terms  nevt*3 (ot,la,lo)    + region 2 
buildGD4 : event terms  nevt*4 (ot,la,lo,dp) + region 2 
buildGD5 : event terms  nevt*2 (ot,dp)       
buildGD6 : event terms  nevt*3 (ot,la,lo)    
buildGD7 : event terms  nevt*4 (ot,la,lo,dp) 
buildGD8 : event terms  nevt*4 (ot,la,lo,dp) + region 2 x2deps
buildGD9 : event terms  nevt*4 (ot,la,lo,dp) + damp only event terms


Steps:
(1) run "ttdict.py *x -o dtdict.pkl" to get delay time dicts.
(2) run "ttevsta.py -m [0-7]", each mode corresponds to a buildGD?


Notes:

Changing sign of dt/dxyz derivative does  not change solution of station correction terms but only 
  reverses the sign of event terms.

Removing mean dt/dxyz for each event does not change solution of station correction terms but 
  limits the magnitude of origin times and change the regional terms (same W-E contrast though).

Scaling event terms dt/dxyz by mean values does not help to converge the problem.
Tested only on mode 3 and 6 and not scale the solution..

Damping does help to converge.

**
Plotting the effects of dtdla/dtdlo/dtddp terms helps to understand the reason of not converging: 
the event terms also explain the big W-E contrast by big change in hypocenter locations. 
Therefore, damping is needed to avoid large solutions.

Relative derivatives are preferred, to focus on effects of wavefront tilt beneath the network (e.g., caused by high velocity craton) but leave out the mean arrival time change.
**

xlou 10/08/2012
"""

from pylab import *
import os, sys
from optparse import OptionParser
from time import clock
from datetime import datetime, timedelta
import matplotlib.transforms as transforms
from mpl_toolkits.mplot3d import axes3d
from matplotlib import gridspec
from scipy.sparse import dok_matrix
from scipy.sparse.linalg import *
from ttcommon import getVel0, getVel, readPickle, writePickle, readStation, saveStation
from ppcommon import saveFigure, plotcoast, plotphysio#, plotdelaymap
from getime import getime
from deltaz import deltaz

d2r = pi/180
r2d = 180/pi
ra = 6371.
ie, id, ic = 0, 0, 1


def getOptions():
	""" Create a parser for options """
	usage = "Usage: %prog [options] <phases>"
	parser = OptionParser(usage=usage)
	refmodel = 'iasp91'
	locsta = 'loc.sta'
	tfilename = 'dtdict.pkl'
	dfilename = 'dtderi.pkl'
	sfilename = 'sol.pkl'
	mode = 0
	plotsta = 'num'
	dampcoef = 0.
	figfmt = 'png'
	parser.set_defaults(dampcoef=dampcoef)
	parser.set_defaults(plotsta=plotsta)
	parser.set_defaults(mode=mode)
	parser.set_defaults(locsta=locsta)
	parser.set_defaults(refmodel=refmodel)
	parser.set_defaults(tfilename=tfilename)
	parser.set_defaults(dfilename=dfilename)
	parser.set_defaults(sfilename=sfilename)
	parser.set_defaults(figfmt=figfmt)
	parser.add_option('-m', '--mode',  dest='mode', type='int',
		help='Matrix mode. Default is {:d}'.format(mode))
	parser.add_option('-r', '--refmodel',  dest='refmodel', type='str',
		help='Reference model (iasp91/mc35/xc35). Default is {:s}'.format(refmodel))
	parser.add_option('-t', '--tfilename',  dest='tfilename', type='str',
		help='File name for delay time. Default is {:s}'.format(tfilename))
	parser.add_option('-d', '--dfilename',  dest='dfilename', type='str',
		help='File name for delay time derivatives. Default is {:s}'.format(dfilename))
	parser.add_option('-s', '--sfilename',  dest='sfilename', type='str',
		help='File name for solution. Default is {:s}'.format(sfilename))
	parser.add_option('-l', '--locsta',  dest='locsta', type='str',
		help='File for station location.')
	parser.add_option('-N', '--multinet', action="store_true", dest='multinet',
		help='Delay stats for multiple networks')
	parser.add_option('-p', '--plotfig', action="store_true", dest='plotfig',
		help='Plot solutions')
	parser.add_option('-g', '--savefig', type='str', dest='savefig',
		help='Save figure to file instead of showing (png/pdf).')
	parser.add_option('-G', '--figfmt',type='str', dest='figfmt',
		help='Figure format for savefig. Default is {:s}'.format(figfmt))
	parser.add_option('-S', '--plotsta', dest='plotsta', type='str',
		help='Plot station terms by num/lon/loc(3d). Default is {:s}'.format(plotsta))
	parser.add_option('-E', '--plotevt', action="store_true", dest='plotevt',
		help='Plot event terms in 3D.')
	parser.add_option('-P', '--plotcoast', action="store_true", dest='plotcoast',
		help='Plot coast boundaries')
	parser.add_option('-A', '--absdd', action="store_true", dest='absdd',
		help='Absolute dtderi')
	parser.add_option('-c', '--escale', action="store_true", dest='escale',
		help='Scale event terms')
	parser.add_option('-n', '--newsol', action="store_true", dest='newsol',
		help='New solution instead of reading from file')
	parser.add_option('-D', '--dampcoef',  dest='dampcoef', type='float',
		help='Damping coefficient. Default is {:f}'.format(dampcoef))
	parser.add_option('-e', '--effevt', dest='effevt', type='int', nargs=2,
		help='Effects of event terms. Give event index range')
	parser.add_option('-T', '--sestats', action="store_true", dest='sestats',
		help='Stats of se terms')
	parser.add_option('-z', '--azimdiv', action="store_true", dest='azimdiv',
		help='Azimuth divsion of event-term effects')
	parser.add_option('-R', '--rmeffevt', action="store_true", dest='rmeffevt',
		help='Remove event-term effects from delay times')

	opts, files = parser.parse_args(sys.argv[1:])
	if files == []:
		files = ['P', 'S']
	if opts.plotsta not in ['num', 'lon', 'loc', '3d']:
		print('Wrong -S option for plotting station terms.')
		sys.exit()
	return opts, files

def calTime(dt, note=''):
	sec = timedelta(seconds=dt)
	d = datetime(1,1,1) + sec
	print('--> Calculation time in {:s}: {:d} days, {:d} hours, {:d} min, {:d} sec'.format(note, d.day-1, d.hour, d.minute, d.second))
	return

def getModel(opts):
	'Get reference model and velocities'
	modnam = opts.refmodel
	moddir = '/opt/local/seismo/data/models/'
	opts.model = moddir + modnam
	mtvel = opts.model + '.tvel'
	print('Read reference model : '+mtvel)
	vp, vs = getVel0(mtvel)
	opts.vel0 = [vp, vs]
	#print('--> Surface P and S velocities from {:s}: {:.2f} {:.2f} km/s'.format(modnam, vp, vs))
	vals = loadtxt(mtvel, skiprows=2)
	deps = vals[:,0]
	velp = vals[:,1]
	vels = vals[:,2]
	opts.dpvpvs = deps, velp, vels
	return opts.dpvpvs

def ttime(mod, phase, slat, slon, elat, elon, edep):
	""" Calculte travel time and ray parameter using getime.
	"""
	time, elcr, dtdd = getime(mod, phase, slat, slon, elat, elon, edep, ie, id, ic)
	return time+elcr, dtdd

def dtdmoho(p, hvel):
	""" 
	Calculate derivative of travel time wrt moho depth.
	Formulation based on plane wave approximation at teleseismic incidence
	so that the change of ray parameter is neglected.

	Input: 
		p   : ray parameter in s/deg
		hvel: moho depth, surface velocity, crust/mantle velocity at Moho
	"""
	h, v0, vc, vm = hvel
	#i0 = arcsin((p*v0)/ra)
	p *= r2d
	ic = arcsin((p*vc)/(ra-h))
	im = arcsin((p*vm)/(ra-h))
	dh = 1.
	# original ray path
	t0 = dh/cos(im)/vm
	# deviated ray path
	t1 = dh/cos(ic)/vc + dh*(tan(im) - tan(ic))*sin(im)/vm
	dtdh = (t1-t0)/dh
	return dtdh

def dtdhypo(mod, phase, slat, slon, elat, elon, edep, vdep):
	"""
	Calculate derivative of travel time wrt hypocenter and origin time.
	Same assumption as dtdmoho.

	dtdd : ray parameter in s/deg
	edep : focal depth in km
	vdep : velocity at focal depth in km/s
	azim : azimuth in radians (from event to station)
	dtddp: dt/ddepth in s/km
	dtdla: dt/dlat   in s/km
	dtdlo: dt/dlon   in s/km
	"""
	tt, dtdd = ttime(mod, phase, slat, slon, elat, elon, edep)
	ih = arcsin((dtdd*r2d*vdep)/(ra-edep))
	dt, az = deltaz(elat, elon, slat, slon)
	azim = az*d2r
	dtddp = -cos(ih) / vdep
	dtdlo = -sin(ih) / vdep * sin(azim)
	dtdla = -sin(ih) / vdep * cos(azim)
	return dtdla, dtdlo, dtddp

def getDtderi(opts, dtdict, stadict):
	'Calculate dtdhypo derivatives for each event-station pair according to dtdict.pkl'
	mod = opts.model
	dpvpvs = opts.dpvpvs
	phases = opts.phases
	evids = sorted(dtdict.keys())
	dddict = {}
	t0 = clock()
	for evid in evids:
		evdict = dtdict[evid]
		elat, elon, edep, mb, ms = evdict['event']['hypo']
		# get reference velocity at focal depth:
		evp, evs = getVel(dpvpvs, edep)
		evps = {'P': evp, 'S': evs}
		print('Calculate dtdhypo for event: {:s}. Vel: {:.3f}  {:.3f} km/s'.format(evid, evp, evs))
		# calculate dt derivatives for each station
		dddict[evid] = {}
		for phase in phases:
			if phase in evdict:
				vdep = evps[phase]
				xdict, xdelay = evdict[phase]
				ddict = {}
				evdds = []
				for sta in xdict.keys():
					slat, slon, selv = stadict[sta]
					dtdla, dtdlo, dtddp = dtdhypo(mod, phase, slat, slon, elat, elon, edep, vdep)
					ddict[sta] = [1., dtdla, dtdlo, dtddp]
					evdds.append([dtdla, dtdlo, dtddp])
					#print evid, sta, ddict[sta]
				#remove mean
				evddm = mean(evdds, 0)
				for sta in xdict.keys():
					for i in range(3):
						ddict[sta][i+1] -= evddm[i]
				dddict[evid][phase] = ddict, evddm
	t1 = clock()
	#calTime(t1-t0, 'getting dtderi')
	return dddict




def getDictST(opts):
	'get station dict'
	if opts.multinet:
		print('--> For multiple arrays: {:s} {:s} {:s}'.format(*opts.nets))
		stadict, xdicts = addStation(opts)
	else:
		stadict = readStation(opts.locsta)
	return stadict

def getDictDT(opts):
	'get dtdict'
	if opts.multinet:
		dtdict, ddicts = addDelay(opts)
	else:
		dtdict = readPickle(opts.tfilename)
	return dtdict

def getDictSE(opts):
	'get sta and evt dicts'
	if not os.path.isfile(opts.stfile):
		stadict = getDictST(opts)
		dtdict = getDictDT(opts)
		stdict = getSta(stadict, dtdict)
		saveStation(stdict, opts.stfile)
	else:
		stdict = readStation(opts.stfile)
	if not os.path.isfile(opts.eqfile):
		eqdict = getEvt(dtdict, opts.eqfile)
	else:
		eqdict = readStation(opts.eqfile)
	return stdict, eqdict

def getDictDD(opts):
	'get dtdict and dddict(dtderi) '
	dtdict = getDictDT(opts)
	if os.path.isfile(opts.dfilename):
		dddict = readPickle(opts.dfilename)
	else:
		dddict = getDtderi(opts, dtdict, stdict)
		writePickle(dddict, opts.dfilename)
	return dtdict, dddict


def addDelay(opts):
	ddicts = []
	dtdict = {}
	for net in opts.nets:
		ddict = readPickle(net + '-' + opts.tfilename)
		ddicts.append(ddict)
		for evid in ddict.keys():
			dtdict[evid] = ddict[evid]
	return dtdict, ddicts

def addStation(opts):
	xdicts = []
	stadict = {}
	for net in opts.nets:
		locsta = opts.locsta + '.' + net
		xdict = readStation(locsta)
		xdicts.append(xdict)
		for sta in xdict.keys():
			stadict[sta] = xdict[sta]
	return stadict, xdicts

def uniqDictsDeprecated(stadict, dtdict, dddict, phase='S'):
	'Get uniq station and event dicts for a phase'
	xstdict, xdtdict, xdddict = {}, {}, {}
	for evid in dtdict.keys():
		evdict = dtdict[evid]
		if phase in evdict:
			xdtdict[evid] = evdict[phase]
			xdddict[evid] = dddict[evid][phase]
			for sta in evdict[phase][0].keys():
				xstdict[sta] = stadict[sta]
	astas = sorted(xstdict.keys())
	aevts = sorted(xdtdict.keys())
	nsta = len(astas)
	nevt = len(aevts)
	print('Number of event, station : {:d}  {:d}  (for {:s})'.format(nevt, nsta, phase))
	return xstdict, xdtdict, xdddict

def getSta(stadict, dtdict):
	'Get a station dict for stations with delay time measurements'
	phases = opts.phases
	astas = []
	for evid in dtdict.keys():
		evdict = dtdict[evid]
		for phase in phases:
			if phase in evdict:
				astas += evdict[phase][0].keys()
	seen = set()
	seen_add = seen.add
	astas = [ x  for x in astas  if x not in seen and not seen_add(x) ]
	stdict = {}
	for sta in astas:
		stdict[sta] = stadict[sta]
	return stdict

def getEvt(dtdict, eqfile):
	'Get event dict with origin time and hypocenter locations'
	eqdict = {}
	ef = open(eqfile, 'w')
	fmt = '{:4d} {:2d} {:2d} {:2d} {:2d} {:5.2f} {:9.3f} {:9.3f} {:6.1f} {:4.1f} {:4.1f} \n'
	for evid in sorted(dtdict):
		ed = dtdict[evid]['event']
		eqdict[evid] = ed['time'] + ed['hypo']
		ef.write('{:<20s} '.format(evid) + fmt.format(*eqdict[evid]))
	ef.close()
	print('Save dict to file "{:s}" '.format(eqfile))
	return eqdict

def writeGD(gdict, d, gdim, gfile, dfile):
	nx, ny = gdim
	print('Write G ({:d} x {:d}) d ({:d} x 1) matrices to   files: {:s} {:s}'.format(nx, ny, nx, gfile, dfile))
	gfh = open(gfile, 'w')
	dfh = open(dfile, 'w')
	for k in range(nx):
		dfh.write('{:11.6f}\n'.format(d[k]))
		gd = gdict[k]
		for m in sorted(gd):
			gfh.write('{:7d} {:7d} {:11.6f}\n'.format(k, m, gd[m]))
	gfh.close()
	dfh.close()

def readGD(gfile, dfile, ny):
	d = loadtxt(dfile)
	nx = len(d)
	print('Read  G ({:d} x {:d}) d ({:d} x 1) matrices from files: {:s} {:s}'.format(nx, ny, nx, gfile, dfile))
	#g = zeros(nx*ny).reshape(nx,ny)
	gmat = dok_matrix((nx,ny))
	for ga in loadtxt(gfile):
		i, j, v = ga
		gmat[int(i), int(j)] = v
	g = gmat.tocsr()
	return g, d

def buildGD0(gfile, dfile, phase='S'):
	"""
	Build matrices for Gm=d inversion.
	G matrix (nsta+nevt*1) x (ndt): 
		(nsta station terms, nevt*1 event terms (ot))
	"""
	nsta = len(astas)
	nevt = len(aevts)
	nreg = 2
	ny = nsta + nevt
	if not os.path.isfile(gfile) or not os.path.isfile(dfile):
		dtdict = getDictDT(opts)
		print('--> Building matrices Gm=d for phase: '+phase)
		t0 = clock()
		k = 0 
		gdict, d = {}, []
		for i in range(nevt):
			evid = aevts[i]
			if evid in dtdict:
				evdict = dtdict[evid]
				if phase in evdict:
					xdict, xdelay = evdict[phase]
					if not absdt: xdelay = 0
					for j in range(nsta):
						sta = astas[j]
						if sta in xdict:
							dt = xdict[sta] + xdelay
							d.append(dt)
							# station term & dtdhypo (ot):
							gdict[k] = {}
							gdict[k][j] = 1
							gdict[k][nsta+i] = 1
							k += 1
		gdim = k, ny
		t1 = clock()
		#calTime(t1-t0, 'building matrices')
		writeGD(gdict, d, gdim, gfile, dfile)
	g, d = readGD(gfile, dfile, ny)	
	return g, d 

def buildGD1(gfile, dfile, phase='S'):
	"""
	Build matrices for Gm=d inversion.
	G matrix (nsta+nevt*1+2)x(ndt):
		(nsta station terms, nevt*1 event terms (ot), 2 regions)
	"""
	nsta = len(astas)
	nevt = len(aevts)
	nreg = 2
	ny = nsta + nevt + nreg
	if not os.path.isfile(gfile) or not os.path.isfile(dfile):
		dtdict = getDictDT(opts)
		print('--> Building matrices Gm=d for phase: '+phase)
		t0 = clock()
		k = 0 
		gdict, d = {}, []
		for i in range(nevt):
			evid = aevts[i]
			if evid in dtdict:
				evdict = dtdict[evid]
				if phase in evdict:
					xdict, xdelay = evdict[phase]
					if not absdt: xdelay = 0
					for j in range(nsta):
						sta = astas[j]
						if sta in xdict:
							dt = xdict[sta] + xdelay
							d.append(dt)
							# station term & dtdhypo (ot):
							gdict[k] = {}
							gdict[k][j] = 1
							gdict[k][nsta+i] = 1
							if sta in stawest:
								gdict[k][nsta+nevt] = 1
							else:
								gdict[k][nsta+nevt+1] = 1
							k += 1
		gdim = k, ny
		t1 = clock()
		#calTime(t1-t0, 'building matrices')
		writeGD(gdict, d, gdim, gfile, dfile)
	g, d = readGD(gfile, dfile, ny)	
	return g, d

def buildGD2(gfile, dfile, phase='S'):
	"""
	Build matrices for Gm=d inversion.
	G matrix (nsta+nevt*2+2)x(ndt):
		(nsta station terms,  nevt*2 event terms, 2 region terms)
	"""
	nsta = len(astas)
	nevt = len(aevts)
	nreg = 2
	ny = nsta + nevt*2 + nreg
	if not os.path.isfile(gfile) or not os.path.isfile(dfile):
		dtdict, dddict = getDictDD(opts)
		print('--> Building matrices Gm=d for phase: '+phase)
		t0 = clock()
		k = 0 
		gdict, d = {}, []
		for i in range(nevt):
			evid = aevts[i]
			if evid in dtdict:
				evdict = dtdict[evid]
				if phase in evdict:
					xdict, xdelay = evdict[phase]
					ddict, dtderi = dddict[evid][phase]
					if not absdt: xdelay = 0
					if not absdd: dtderi = [0, 0, 0]
					for j in range(nsta):
						sta = astas[j]
						if sta in xdict:
							dt = xdict[sta] + xdelay
							d.append(dt)
							# station term & dtdhypo (ot, dp):
							gdict[k] = {}
							gdict[k][j] = 1
							n = nsta+i*2
							dds = ddict[sta]
							gdict[k][n]   = dds[0] 
							gdict[k][n+1] = (dds[3] + dtderi[2])
							if sta in stawest:
								gdict[k][nsta+nevt*2] = 1
							else:
								gdict[k][nsta+nevt*2+1] = 1
							k += 1
		gdim = k, ny
		t1 = clock()
		#calTime(t1-t0, 'building matrices')
		writeGD(gdict, d, gdim, gfile, dfile)
	g, d = readGD(gfile, dfile, ny)	
	return g, d

def buildGD3(gfile, dfile, phase='S'):
	"""
	Build matrices for Gm=d inversion.
	G matrix (nsta+nevt*3+2)x(ndt):
		(nsta station terms,  nevt*3 event terms, 2 region terms)
	"""
	nsta = len(astas)
	nevt = len(aevts)
	nreg = 2
	ny = nsta + nevt*3 + nreg
	if opts.escale:
		esca = esdict[phase]
	else:
		esca = ones(3)
	if not os.path.isfile(gfile) or not os.path.isfile(dfile):
		dtdict, dddict = getDictDD(opts)
		print('--> Building matrices Gm=d for phase: '+phase)
		print('Event term scales: {:f} {:f} {:f}'.format(*esca))
		t0 = clock()
		k = 0 
		gdict, d = {}, []
		for i in range(nevt):
			evid = aevts[i]
			if evid in dtdict:
				evdict = dtdict[evid]
				if phase in evdict:
					xdict, xdelay = evdict[phase]
					ddict, dtderi = dddict[evid][phase]
					if not absdt: xdelay = 0
					if not absdd: dtderi = [0, 0, 0]
					for j in range(nsta):
						sta = astas[j]
						if sta in xdict:
							dt = xdict[sta] + xdelay
							d.append(dt)
							# station term & dtdhypo (ot, la, lo):
							gdict[k] = {}
							gdict[k][j] = 1
							n = nsta+i*3
							dds = ddict[sta]
							gdict[k][n]   = dds[0]
							gdict[k][n+1] = (dds[1] + dtderi[0])/esca[0]
							gdict[k][n+2] = (dds[2] + dtderi[1])/esca[1]
							if sta in stawest:
								gdict[k][nsta+nevt*3] = 1
							else:
								gdict[k][nsta+nevt*3+1] = 1
							k += 1
		gdim = k, ny
		t1 = clock()
		#calTime(t1-t0, 'building matrices')
		writeGD(gdict, d, gdim, gfile, dfile)
	g, d = readGD(gfile, dfile, ny)	
	return g, d

def buildGD4(gfile, dfile, phase='S'):
	"""
	Build matrices for Gm=d inversion.
	G matrix (nsta+nevt*4+2)x(ndt):
		(nsta station terms,  nevt*4 event terms, 2 region terms)
	"""
	nsta = len(astas)
	nevt = len(aevts)
	nreg = 2
	ny = nsta + nevt*4 + nreg
	if not os.path.isfile(gfile) or not os.path.isfile(dfile):
		dtdict, dddict = getDictDD(opts)
		print('--> Building matrices Gm=d for phase: '+phase)
		t0 = clock()
		k = 0 
		gdict, d = {}, []
		for i in range(nevt):
			evid = aevts[i]
			if evid in dtdict:
				evdict = dtdict[evid]
				if phase in evdict:
					xdict, xdelay = evdict[phase]
					ddict, dtderi = dddict[evid][phase]
					if not absdt: xdelay = 0
					if not absdd: dtderi = [0, 0, 0]
					for j in range(nsta):
						sta = astas[j]
						if sta in xdict:
							dt = xdict[sta] + xdelay
							d.append(dt)
							# station term & dtdhypo (ot, la, lo, dp):
							gdict[k] = {}
							gdict[k][j] = 1
							n = nsta+i*4
							dds = ddict[sta]
							gdict[k][n]   = dds[0]
							gdict[k][n+1] = dds[1] + dtderi[0]
							gdict[k][n+2] = dds[2] + dtderi[1]
							gdict[k][n+3] = dds[3] + dtderi[2]
							if sta in stawest:
								gdict[k][nsta+nevt*4] = 1
							else:
								gdict[k][nsta+nevt*4+1] = 1
							k += 1
		gdim = k, ny
		t1 = clock()
		#calTime(t1-t0, 'building matrices')
		writeGD(gdict, d, gdim, gfile, dfile)
	g, d = readGD(gfile, dfile, ny)	
	return g, d

def buildGD5(gfile, dfile, phase='S'):
	"""
	Build matrices for Gm=d inversion.
	G matrix (nsta+nevt*2)x(ndt):
		(nsta station terms,  nevt*2 event terms)
	"""
	nsta = len(astas)
	nevt = len(aevts)
	ny = nsta + nevt*2
	if not os.path.isfile(gfile) or not os.path.isfile(dfile):
		dtdict, dddict = getDictDD(opts)
		print('--> Building matrices Gm=d for phase: '+phase)
		t0 = clock()
		k = 0 
		gdict, d = {}, []
		for i in range(nevt):
			evid = aevts[i]
			if evid in dtdict:
				evdict = dtdict[evid]
				if phase in evdict:
					xdict, xdelay = evdict[phase]
					ddict, dtderi = dddict[evid][phase]
					if not absdt: xdelay = 0
					if not absdd: dtderi = [0, 0, 0]
					for j in range(nsta):
						sta = astas[j]
						if sta in xdict:
							dt = xdict[sta] + xdelay
							d.append(dt)
							# station term & dtdhypo (ot, dp):
							gdict[k] = {}
							gdict[k][j] = 1
							n = nsta+i*2
							dds = ddict[sta]
							gdict[k][n]   = dds[0] 
							gdict[k][n+1] = (dds[3] + dtderi[2])
							k += 1
		gdim = k, ny
		t1 = clock()
		#calTime(t1-t0, 'building matrices')
		writeGD(gdict, d, gdim, gfile, dfile)
	g, d = readGD(gfile, dfile, ny)	
	return g, d

def buildGD6(gfile, dfile, phase='S'):
	"""
	Build matrices for Gm=d inversion.
	G matrix (nsta+nevt*3)x(ndt):
		(nsta station terms,  nevt*3 event terms)
	"""
	nsta = len(astas)
	nevt = len(aevts)
	ny = nsta + nevt*3
	if opts.escale:
		esca = esdict[phase]
	else:
		esca = ones(3)
	if not os.path.isfile(gfile) or not os.path.isfile(dfile):
		dtdict, dddict = getDictDD(opts)
		print('--> Building matrices Gm=d for phase: '+phase)
		print('Event term scales: {:f} {:f} {:f}'.format(*esca))
		t0 = clock()
		k = 0 
		gdict, d = {}, []
		for i in range(nevt):
			evid = aevts[i]
			if evid in dtdict:
				evdict = dtdict[evid]
				if phase in evdict:
					xdict, xdelay = evdict[phase]
					ddict, dtderi = dddict[evid][phase]
					if not absdt: xdelay = 0
					if not absdd: dtderi = [0, 0, 0]
					for j in range(nsta):
						sta = astas[j]
						if sta in xdict:
							dt = xdict[sta] + xdelay
							d.append(dt)
							# station term & dtdhypo (ot, la, lo):
							gdict[k] = {}
							gdict[k][j] = 1
							n = nsta+i*3
							dds = ddict[sta]
							gdict[k][n]   = dds[0]
							gdict[k][n+1] = (dds[1] + dtderi[0])/esca[0]
							gdict[k][n+2] = (dds[2] + dtderi[1])/esca[1]
							k += 1
		gdim = k, ny
		t1 = clock()
		#calTime(t1-t0, 'building matrices')
		writeGD(gdict, d, gdim, gfile, dfile)
	g, d = readGD(gfile, dfile, ny)	
	return g, d

def buildGD7(gfile, dfile, phase='S'):
	"""
	Build matrices for Gm=d inversion.
	G matrix (nsta+nevt*4)x(ndt):
		(nsta station terms,  nevt*4 event terms)
	"""

	nsta = len(astas)
	nevt = len(aevts)
	ny = nsta + nevt*4
	if not os.path.isfile(gfile) or not os.path.isfile(dfile):
		dtdict, dddict = getDictDD(opts)
		print('--> Building matrices Gm=d for phase: '+phase)
		t0 = clock()
		k = 0 
		gdict, d = {}, []
		for i in range(nevt):
			evid = aevts[i]
			if evid in dtdict:
				evdict = dtdict[evid]
				if phase in evdict:
					xdict, xdelay = evdict[phase]
					ddict, dtderi = dddict[evid][phase]
					if not absdt: xdelay = 0
					if not absdd: dtderi = [0, 0, 0]
					for j in range(nsta):
						sta = astas[j]
						if sta in xdict:
							dt = xdict[sta] + xdelay
							d.append(dt)
							# station term & dtdhypo (ot, la, lo, dp):
							gdict[k] = {}
							gdict[k][j] = 1
							n = nsta+i*4
							dds = ddict[sta]
							gdict[k][n]   = dds[0]
							gdict[k][n+1] = dds[1] + dtderi[0]
							gdict[k][n+2] = dds[2] + dtderi[1]
							gdict[k][n+3] = dds[3] + dtderi[2]
							k += 1
		gdim = k, ny
		t1 = clock()
		#calTime(t1-t0, 'building matrices')
		writeGD(gdict, d, gdim, gfile, dfile)
	g, d = readGD(gfile, dfile, ny)	
	return g, d

def buildGD8(gfile, dfile, phase='S'):
	"""
	Build matrices for Gm=d inversion.
	G matrix (nsta+nevt*4+2)x(ndt):
		(nsta station terms,  nevt*4 event terms, 2 region terms x 2deps)
	"""
	nsta = len(astas)
	nevt = len(aevts)
	nreg = 2*2
	ny = nsta + nevt*4 + nreg
	if not os.path.isfile(gfile) or not os.path.isfile(dfile):
		dtdict, dddict = getDictDD(opts)
		print('--> Building matrices Gm=d for phase: '+phase)
		t0 = clock()
		k = 0 
		gdict, d = {}, []
		for i in range(nevt):
			evid = aevts[i]
			if evid in dtdict:
				evdict = dtdict[evid]
				if phase in evdict:
					xdict, xdelay = evdict[phase]
					ddict, dtderi = dddict[evid][phase]
					if not absdt: xdelay = 0
					if not absdd: dtderi = [0, 0, 0]
					for j in range(nsta):
						sta = astas[j]
						if sta in xdict:
							dt = xdict[sta] + xdelay
							d.append(dt)
							# station term & dtdhypo (ot, la, lo, dp):
							gdict[k] = {}
							gdict[k][j] = 1
							n = nsta+i*4
							dds = ddict[sta]
							gdict[k][n]   = dds[0]
							gdict[k][n+1] = dds[1] + dtderi[0]
							gdict[k][n+2] = dds[2] + dtderi[1]
							gdict[k][n+3] = dds[3] + dtderi[2]
							if sta in stawest:
								gdict[k][nsta+nevt*4] = 1
								gdict[k][nsta+nevt*4+2] = 1
							else:
								gdict[k][nsta+nevt*4+1] = 1
								gdict[k][nsta+nevt*4+3] = 1
							k += 1
		gdim = k, ny
		t1 = clock()
		#calTime(t1-t0, 'building matrices')
		writeGD(gdict, d, gdim, gfile, dfile)
	g, d = readGD(gfile, dfile, ny)	
	return g, d


def buildGD9(gfile, dfile, phase='S'):
	"""
	Build matrices for Gm=d inversion.
	G matrix (nsta+nevt*4)x(ndt):
		(nsta station terms,  nevt*4 event terms)
	"""
	nsta = len(astas)
	nevt = len(aevts)
	ny = nsta + nevt*4
	if not os.path.isfile(gfile) or not os.path.isfile(dfile):
		dtdict, dddict = getDictDD(opts)
		print('--> Building matrices Gm=d for phase: '+phase)
		k = 0 
		gdict, d = {}, []
		for i in range(nevt):
			evid = aevts[i]
			if evid in dtdict:
				evdict = dtdict[evid]
				if phase in evdict:
					xdict, xdelay = evdict[phase]
					ddict, dtderi = dddict[evid][phase]
					if not absdt: xdelay = 0
					if not absdd: dtderi = [0, 0, 0]
					for j in range(nsta):
						sta = astas[j]
						if sta in xdict:
							dt = xdict[sta] + xdelay
							d.append(dt)
							# station term & dtdhypo (ot, la, lo, dp):
							gdict[k] = {}
							gdict[k][j] = 1
							n = nsta+i*4
							dds = ddict[sta]
							gdict[k][n]   = dds[0]
							gdict[k][n+1] = dds[1] + dtderi[0]
							gdict[k][n+2] = dds[2] + dtderi[1]
							gdict[k][n+3] = dds[3] + dtderi[2]
							k += 1
		# damp event terms
		edamp = [1, .5, .5, .2]
		edamp = [2, 1, 1, .4]
		for i in range(nevt):
			n = nsta+i*4
			for j in range(4):
				gdict[k] = {}
				gdict[k][n+j] = edamp[j]
				k += 1
				d.append(0)
		gdim = k, ny
		writeGD(gdict, d, gdim, gfile, dfile)
	g, d = readGD(gfile, dfile, ny)	
	return g, d

def solveGD(opts, phase='S'):
	mode = opts.mode
	gfile = 'matrix{:d}-{:s}-g'.format(mode, phase.lower())
	dfile = 'matrix{:d}-{:s}-d'.format(mode, phase.lower())
	if opts.newsol:
		os.system('/bin/rm -f {:s} {:s}'.format(gfile, dfile))
	if mode == 0:
		buildGD = buildGD0
	elif mode == 1:
		buildGD = buildGD1
	elif mode == 2:
		buildGD = buildGD2
	elif mode == 3:
		buildGD = buildGD3
	elif mode == 4:
		buildGD = buildGD4
	elif mode == 5:
		buildGD = buildGD5
	elif mode == 6:
		buildGD = buildGD6
	elif mode == 7:
		buildGD = buildGD7
	elif mode == 8:
		buildGD = buildGD8
	elif mode == 9:
		buildGD = buildGD9
	g, d = buildGD(gfile, dfile, phase)
	nx, ny = g.shape
	#print('  G matrix dimension: {:d} x {:d}'.format(nx, ny))
	#print('  d matrix dimension: {:d} x 1'.format(len(d)))
	print('--> Solving G^TGm = G^Td by least squares...')
	t0 = clock()
	if mode <= 8:
		xsol = lsqr(g, d, damp=opts.dampcoef, show=True)
	else:
		xsol = lsqr(g, d, show=True)
#	if opts.escale:
#		xsol
	t1 = clock()
	#calTime(t1-t0, 'solving matrices')
	return xsol

def getN(opts):
	' get number of event and station terms (matrix dimension)'
	mode = opts.mode
	if mode >= 1 and mode <= 4:
		nreg = 2
	elif mode == 8:
		nreg = 2*2
	else:
		nreg = 0
	ny = nsta + nevt*mode + nreg
	ns, nr = nsta, nreg
	ne = nsta + nevt*max(1, mode)
	if mode >= 5 and mode <=8:
		ny -= nevt*3
		ne -= nevt*3
	elif mode == 9:
		ne = nsta + nevt*4
		ny = ne
	print('Number of S/E/R terms: {:d} {:d} {:d} {:d}'.format(ns, ne, nr, ny))
	# inds for event terms
	if mode <= 1:
		inds = [0,]
	elif mode == 2 or mode == 5:
		inds = [0, 3]
	elif mode <= 4:
		inds = range(mode)
	elif mode <= 7:
		inds = range(mode-3)
	elif mode == 8 or mode == 9:
		inds = range(4)
	opts.inds = inds
	opts.ndim = ns, ne, nr, ny

def sol2terms(xx):
	'Get st/ev/re terms from solution'
	mode = opts.mode
	ns, ne, nr, ny = opts.ndim
	# station terms
	xs = xx[:ns]
	# event terms (divide to ot/la/lo/dp in xevs):
	xe = xx[ns:ne]
	xevs = [ zeros(nevt) for i in range(4) ]
	if mode <= 1:
		inds = [0,]
		for i in inds: 
			xevs[i] = xe
	elif mode == 2 or mode == 5:
		xevs[0] = xe[0::2]
		xevs[3] = xe[1::2]
		inds = [0, 3]
	elif mode <= 4:
		inds = range(mode)
		for i in inds:
			xevs[i] = xe[i::mode]
	elif mode <= 7:
		inds = range(mode-3)
		for i in inds:
			xevs[i] = xe[i::mode-3]
	elif mode == 8 or mode == 9:
		inds = range(4)
		for i in inds:
			xevs[i] = xe[i::4]
	if nr > 0:
		xr = xx[-nr:]
	else:
		xr = None
	return xs, xevs, xr


def getSol(opts, phases):
	'Solve and write solution (ev/st/re terms) explicitly. '
	for phase in phases:
		sofile = opts.sfilename.replace('.pkl', '{:d}-{:s}.pkl'.format(opts.mode, phase.lower()))
		if os.path.isfile(sofile) and not opts.newsol:
			xsol = readPickle(sofile)
		else:
			xsol = solveGD(opts, phase)
			writePickle(xsol, sofile)
		#sodict[phase] = xsol
		xx, istop, itn, r1norm, r2norm, anorm, acond, arnorm, xnorm, var = xsol
		#print('  istop  = {:11d};   itn    = {:11d}; '.format(istop, itn))
		#print('  r1norm = {:11f};   r2norm = {:11f}; '.format(r1norm, r2norm))
		#print('  anorm  = {:11f};   acond  = {:11f}; '.format(anorm, acond))
		#print('  arnorm = {:11f};   xnorm  = {:11f}; '.format(arnorm, xnorm))

		# write station/event/region terms explictly
		xs, xevs, xr = sol2terms(xx)
		sfile = 'stadt-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		efile = 'evtco-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		rfile = sfile + '-region'
		if not os.path.isfile(sfile):
			print('Save station terms to file: '+sfile)
			tdict = {}
			for j in range(nsta):
				sta = astas[j]
				tdict[sta] = stdict[sta][:2] + [xx[j], var[j]]
			saveStation(tdict, sfile)
		fmt = '{:7.2f} '*4 + '\n'
		if not os.path.isfile(efile):
			print('Save event terms to file: '+efile)
			with open(efile, 'w') as f:
				for j in range(nevt):
					tt = [ xevs[i][j] for i in range(4) ]
					f.write('{:s} '.format(aevts[j]) + fmt.format(*tt))
		if xr is not None:
			#sxw, sxe = xr
			if not os.path.isfile(rfile):
				print('Save region terms to file: '+rfile)
				print(xr)
				#os.system('echo {:7.2f} {:7.2f} > {:s}'.format(sxw, sxe, rfile))
				fmt = '{:f} '*len(xr) + '\n' 
				with open(rfile, 'w') as f:
					f.write(fmt.format(*xr))


def readSol(opts, phases):
	'read solution into arrays of station, event, region terms'
	ns, ne, nr, ny = opts.ndim
	dosolve = False
	for phase in phases:
		sfile = 'stadt-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		efile = 'evtco-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		rfile = sfile + '-region'
		if nr > 0:
			xfiles = [sfile, efile, rfile]
		else:
			xfiles = [sfile, efile]
		for xfile in xfiles:
			if not os.path.isfile(xfile):
				dosolve = True
	if dosolve:
		getSol(opts, phases)
	sodict = {}
	for phase in phases:
		sfile = 'stadt-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		efile = 'evtco-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		rfile = sfile + '-region'
		#sdict = readStation(sfile)
		#edict = readStation(efile)
		#xs = [ sdict[sta][-1]  for sta in astas ]
		#xe = array([ edict[evt]  for evt in aevts ]
		xs = loadtxt(sfile, usecols=(3,))
		vals = loadtxt(efile, usecols=(1,2,3,4))
		xe = array([ vals[:,i] for i in range(4) ])
		if nr > 0:
			xr = loadtxt(rfile)
		else:
			xr = None
		sodict[phase] = xs, xe, xr
	return sodict


def plotSol(opts, phases, sodict):
	print('Plot solutions')
	axsta, axevts = makeAxes(opts)
	trans = transforms.blended_transform_factory(axsta.transData, axsta.transAxes)
	rcParams['legend.fontsize'] = 11
	ns, ne, nr, ny = opts.ndim 
	inds = opts.inds
	cols = 'b', 'r'
	for phase, col in zip(phases, cols):
		# station terms, event terms and indices
		xs, xevs, xr = sodict[phase]
		tt = phase
		xxw = array([ xs[i] for i in indstaw ])
		xxe = array([ xs[i] for i in indstae ])
		if nr > 0:
			sxw, sxe = xr
			tt += ' (Region {:.1f} {:.1f} s)'.format(sxw, sxe)
			print('==> {:s}       region terms for W E : {:6.2f} {:6.2f} s '.format(phase, sxw, sxe))
		else:
			sxw, sxe = 0, 0
		if opts.plotnum: # station number
			xnw, xne = range(nstaw), range(nstaw, ns)
			axsta.plot(xnw, xxw+sxw, '.'+col, label=tt)
			axsta.plot(xne, xxe+sxe, '.'+col)
		elif opts.plotlon:  # station longitude 
			axsta.plot(stawlon, xxw+sxw, '.'+col, label=tt)
			axsta.plot(staelon, xxe+sxe, '.'+col)
		elif opts.plotloc:  # station location
			axsta.scatter(aslons, aslats, xs, c=col, marker='o', s=25, lw=.5, label=tt)
		print('==> {:s} mean station terms for W E : {:6.2f} {:6.2f} s '.format(phase, mean(xxw), mean(xxe)))
		n = nstaw+nstae
		if nr > 0 and opts.plotnum:
			axsta.plot([0,nstaw], [sxw,sxw], color=col, ls='-')
			axsta.plot([nstaw,n], [sxe,sxe], color=col, ls='-')
		# event terms (divide to ot/la/lo/dp in xevs): 
		mexevs = [ mean(xevs[i]) for i in range(4)] + [ mean(abs(xevs[i])) for i in range(4)]
		fmt = '{:6.2f} s {:5.1f} {:5.1f} {:5.1f} km. ' 
		fmt = fmt + '|| Abs ' + fmt
		print('==> {:s} mean event   terms :'.format(phase) + fmt.format(*mexevs))
		for i in inds:
			ms = 3
			if i == 0 and opts.plotloc:
				axevts[i].plot(xevs[i], '.'+col, ms=ms, label=phase)
				axevts[i].legend()
			else:
				axevts[i].plot(xevs[i], '.'+col, ms=ms)
		if opts.plotevt:
			ax = axevts[4]
			for j in range(nevt):
				if abs(xevs[0][j]) > 0. or abs(xevs[1][j]) > 0. or abs(xevs[2][j]) > 0.:
					aa = aelons[j], aelons[j]+xevs[2][j]
					bb = aelats[j], aelats[j]+xevs[1][j]
					dd = 0, xevs[0][j]
					ax.plot(aa, bb, dd, color=col)
	if opts.plotevt:
		# wirefram:
		fx0, fx1 = ax.get_xlim()
		fy0, fy1 = ax.get_ylim()
		n = 3
		fx, fy = meshgrid(linspace(fx0, fx1, n), linspace(fy0, fy1, n))
		fz = zeros((n,n))
		ax.plot_wireframe(fx, fy, fz, color='g')
		if opts.plotcoast:
			plotcoast(True, False, False, 'g')
		ax.text2D(0.5, 1.01, 'Event Terms', transform=ax.transAxes, ha='center', va='bottom', size=15)
	if opts.plotnum:
		axsta.axvline(x=nstaw, color='k', ls=':')
		axsta.text(nstaw-10, 0.97, 'West', transform=trans, va='center', ha='right', size=16)
		axsta.text(nstaw+10, 0.97, 'East', transform=trans, va='center', ha='left', size=16)
	elif opts.plotlon:
		axsta.set_xlabel('Station Longitude '+r'[$^{\circ}$]')
	elif opts.plotloc:
		axsta.set_xlabel('Station Longitude '+r'[$^{\circ}$]')
		axsta.set_ylabel('Station Latitude '+r'[$^{\circ}$]')
		axsta.set_zlabel('Station Correction [s]')
		sca(axsta)
		if opts.plotcoast:
			plotcoast(True, True, False, 'g')
			axsta.set_xlim(-127,-65)
			axsta.set_ylim(25,50)
	axsta.legend(loc=1)
	if opts.plotloc:
		axsta.text2D(0.5, 1.01, 'Station Terms: '+ notes[opts.mode], transform=axsta.transAxes, ha='center', va='bottom', size=15)
		axsta.set_title('')
	else: 
		#axsta.set_title('Station Terms: '+ notes[opts.mode])
		axsta.set_title('Station Terms')
		axsta.set_ylim(-6,8)
		if opts.mode <= 8:
			axevts[0].set_ylim(-6,12)
			axevts[1].set_ylim(-150,150)
			axevts[2].set_ylim(-150,150)
			axevts[3].set_ylim(-150,150)
		else:
			axevts[0].set_ylim(-10,10)
			axevts[1].set_ylim(-20,20)
			axevts[2].set_ylim(-20,20)
			axevts[3].set_ylim(-20,20)

	if opts.plotnum:
		fignm = opts.sfilename.replace('.pkl', '{:d}.png'.format(opts.mode))
	else:
		fignm = opts.sfilename.replace('.pkl', '{:d}{:s}.png'.format(opts.mode, opts.plotsta))

	saveFigure(fignm, opts)


def makeAxes(opts):
	# axes
	if not opts.plotevt:
		fig = figure(figsize=(12,6))
		#subplots_adjust(left=0.07, right=0.97, bottom=.1, top=0.93)
		xa, xb = 0.07, 0.74
		dxa, dxb = 0.6, 0.24
	else:
		fig = figure(figsize=(18,6))
		xa, xb, xc = 0.01, 0.48, 0.69
		dxa, dxb, dxc = 0.4, 0.2, 0.3
	ya, dya = 0.1, 0.83
	bsta = xa, ya, dxa, dya
	if opts.plotloc:
		axsta = fig.add_axes(bsta, projection='3d', azim=-95, elev=0)
	else:
		axsta = fig.add_axes(bsta)
	dyb = 0.19
	bevt0 = xb, ya, dxb, dyb
	axevt0 = fig.add_axes(bevt0)
	ddy = 0.02
	#axevts = [axevt0,] + [ fig.add_axes([xb, ya+i*(dyb+ddy), dxb, dyb], sharex=axevt0)  for i in range(1,4) ]
	axevts = [axevt0,] + [ fig.add_axes([xb, ya+i*(dyb+ddy), dxb, dyb])  for i in range(1,4) ]
	if opts.plotevt:
		ax = fig.add_axes([xc, ya, dxc, dya], projection='3d', azim=-70, elev=20)
		axevts.append(ax)
		ax.set_xlabel('Lon '+r'$[^{\circ}$]'+' + dLon [km]')
		ax.set_ylabel('Lat '+r'$[^{\circ}$]'+' + dLat [km]')
		ax.set_zlabel('Origin Time [s]')
	# label, title:
	ylabs = 'Origin Time [s]', 'Lat [km]', 'Lon [km]', 'Depth [km]'
	for i in range(4):
		if i > 0: axevts[i].set_xticklabels([])
		axevts[i].set_ylabel(ylabs[i])
	axsta.set_ylabel('Station Correction [s]')
	axsta.set_title('Station Terms')
	axevts[3].set_title('Event Terms')
	axevts[0].set_xlabel('Event Number')
	axsta.set_xlabel('Station Number')
	return axsta, axevts



def plotdelaymap(vdict, vindex, cmap, clabel, opts):
	""" Plot delay times in map view. Use vindex to specify the column number.
	"""
	vals = array([ stdict[sta][:2] + [vdict[sta][vindex],]  for sta in vdict.keys() ])
	lat = vals[:,0]
	lon = vals[:,1]
	dtv = vals[:,2]
	vmin, vmax = opts.vlims
	scatter(lon, lat, c=dtv, vmin=vmin, vmax=vmax, cmap=cmap, marker=opts.marker, alpha=opts.alpha, s=opts.msize**2)
	pcbar = opts.plotcbar
	if pcbar is not None:
		if pcbar == 'h':
			cbar = colorbar(orientation='horizontal', pad=.07, aspect=30., shrink=0.95)
		else:
			cbar = colorbar(orientation='vertical', pad=.01, aspect=20., shrink=0.95)
		cbar.set_label(clabel)
		cbar.formatter.set_scientific(True)
		cbar.formatter.set_powerlimits((0,0)) 
		cbar.update_ticks() 
		plotphysio(opts.physio, True)
		#plotcoast(True, True, True)
	if opts.axlims is not None:
		axis(opts.axlims)
	else:
		axis('equal')

def getGMD(opts, phases):
	gmfile = 'gm-sol{:d}.pkl'.format(opts.mode)
	if os.path.isfile(gmfile):
		gmdict = readPickle(gmfile)
	else:
		print('Get effects of event terms on delay times. d = G*m')
		dtdict, dddict = getDictDD(opts)
		gmdict = {}
		for evid in sorted(dddict):
			eind = aevts.index(evid)
			gmdict[evid] = {}
			for phase in phases:
				xevs = sodict[phase][1]
				if phase in dddict[evid]:
					ddict, dtderi = dddict[evid][phase]
					if not absdd: dtderi = [0, 0, 0]
					vdict = {}
					evdtd = zeros((nsta, 4))
					dtd = array([0,] + list(dtderi))
					for sta in sorted(ddict):
						dds = (ddict[sta] + dtd)
						vdict[sta] = [ dds[k]*xevs[k,eind]  for k in range(4) ]
					gmdict[evid][phase] = vdict
		writePickle(gmdict, gmfile)
	return gmdict


def plotEventGMD(gmdict, evid, phase, odir='.'):
	vinds = opts.inds
	xevs = sodict[phase][1]
	gmd = gmdict[evid]
	elat, elon = eqdict[evid][6:8]
	eind = aevts.index(evid)
	if phase in gmd:
		#print('  {:s} -- {:s} '.format(evid, phase))
		vdict = gmd[phase]
		for sta in sorted(vdict):
			# add sum of lat/lon/dep as the last column
			vs = sum(vdict[sta][1:])
			vdict[sta].append(vs)
		#fig = figure(figsize=(8,14))
		#subplots_adjust(left=.07, right=1, bottom=.03, top=.95, wspace=.01, hspace=.06)
		fig = figure(figsize=(14,9))
		subplots_adjust(left=.03, right=.99, bottom=.01, top=.95, wspace=.06, hspace=.0)
		#gs = gridspec.GridSpec(2, 3)
		#ax0 = subplot(gs[0, 0])
		#ax1 = subplot(gs[0, 1:])
		#axs = [ax0, ax1]
		#axs += [ subplot(gs[1,i]) for i in range(3) ]
		nv = len(vinds)
		for k in vinds:
			esol = xevs[k,eind]
			if k == 0:
				subplot(2, 3, k+1)
			else:
				subplot(2, 3, k+3)
			#if k == 0:
			#	ax = axs[0]
			#elif k == -1:
			#	ax = axs[1]
			#else:
			#	ax = axs[k+1]
			#sca(ax)
			clab = '{:s} Time [s] (by change in {:s})'.format(phase, elabs[k])
			plotdelaymap(vdict,  vinds[k], cmap, clab, opts)
			tlab = r'$\Delta$ {:s} = {:.1f} {:s}'.format(elabs[k], esol, units[k])
			text(0.95, 0.97, tlab, transform=gca().transAxes, ha='right', va='top', size=13)
			if k == 0:
				arrow(elon, elat, clon-elon, clat-elat, head_width=.77, color='g', ls='solid')
			#if k == 1:
			#	arrow(elon, elat+esol, clon-elon, clat-elat-esol, head_width=.77, color='g', ls='dashed')
			#elif k == 2:
			#	arrow(elon+esol, elat, clon-elon-esol, clat-elat, head_width=.77, color='g', ls='dashed')
		# plot sum of lat/lon/dep
		subplot(2, 3, 2)
		clab = '{:s} Time [s] (by change in {:s})'.format(phase, elabs[-1])
		plotdelaymap(vdict, -1, cmap, clab, opts)
		tlab = 'Lat+Lon+Dep'
		text(0.95, 0.97, tlab, transform=gca().transAxes, ha='right', va='top', size=13)
		suptitle(evid)
		fignm = odir+'/evgm-sol{:d}-{:s}-{:s}.png'.format(opts.mode, evid, phase.lower())
		saveFigure(fignm, opts)

def plotGMD(opts, phases, gmdict):
	print('Plot effects of event terms (d = G*m) on delay times ')
	gdir = 'evgm-sol{:d}'.format(opts.mode)
	if not os.path.isdir(gdir): os.mkdir(gdir)
	ia, ib = opts.effevt
	if ia > ib:
		ia, ib = ib, ia
	ia = max(0, ia)
	ib = min(nevt, ib)
	for evid in sorted(gmdict)[ia:ib]:
		for phase in phases:
			fignm = gdir+'/evgm-sol{:d}-{:s}-{:s}.png'.format(opts.mode, evid, phase.lower()) 
			fignm = fignm.replace('png', opts.figfmt)
			print('  {:s} -- {:s} '.format(evid, phase))
			if not os.path.isfile(fignm):
				plotEventGMD(gmdict, evid, phase, gdir)
	#os.system('mv {:s}*pdf {:s}'.format(gdir, gdir))


def getEstats(opts, phases):
	'Get stats of event term effects'
	gmdict = getGMD(opts, phases)
	# event effects terms
	for phase in phases:
		ssfile = 'evgm-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		fmt = '{:s} {:4d} {:10.6f} {:10.6f}   {:10.6f} {:10.6f}\n'
		fhead = '# evid            nsta   otime      hypo         abs-ot     abs-hypo\n'
		if not os.path.isfile(ssfile):
			print('Save event effects to file: '+ssfile)
			with open(ssfile ,'w') as f:
				f.write(fhead)
				for evid in sorted(gmdict):
					if phase in gmdict[evid]:
						gmd = gmdict[evid][phase]
						ista = len(gmd)
						vals = array([ gmd[sta]  for sta in sorted(gmd) ])
						mo = sum(vals[:,0])  / ista
						mh = sum(vals[:,1:]) / ista
						amo = sum(abs(vals[:,0])) / ista
						amh = sum(abs(sum(vals[:,1:], 1))) / ista
						print(fmt.format(evid, ista, mo, mh, amo, amh))
						f.write(fmt.format(evid, ista, mo, mh, amo, amh))

def getSEstatsDeprecated(opts, phases):
	'get stats for S E '
	doget = False
	for phase in phases:
		ssfile = 'evgm-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		if not os.path.isfile(ssfile):
			doget = True
	if doget:
		getEstats(opts, phases)
	for phase in phases:
		# stats for S terms
		xs, xevs, xr = sodict[phase]
		xxw = array([ xs[i] for i in indstaw ])
		xxe = array([ xs[i] for i in indstae ])
		print('==> {:s} mean station  terms for W E : {:6.2f} {:6.2f} s '.format(phase, mean(xxw), mean(xxe)))
		# stats for E terms
		mexevs = [ mean(xevs[i]) for i in range(4)] + [ mean(abs(xevs[i])) for i in range(4)]
		fmt = '{:6.2f} s {:5.1f} {:5.1f} {:5.1f} km. ' 
		fmt = fmt + '|| Abs ' + fmt
		print('==> {:s} mean event    terms :'.format(phase) + fmt.format(*mexevs))
		# stats for E term effects
		ssfile = 'evgm-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		vals = loadtxt(ssfile, comments='#', usecols=(1,2,3,4,5))
		nv = len(vals[0])
		na = sum(vals[:,0])
		meveff = [ sum(vals[:,i]*vals[:,0])/na for i in range(1, nv) ]
		fmt = '{:6.2f} s {:6.2f} s. '
		fmt = fmt + '|| Abs' + fmt
		print('==> {:s} mean eventeff terms :'.format(phase) + fmt.format(*meveff))

def getSEstats(opts, phases):
	'get stats for S E '
	doget = False
	for phase in phases:
		ssfile = 'gm-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		if not os.path.isfile(ssfile):
			doget = True
	if doget:
		getGMDasc(opts, phases)
	for phase in phases:
		# stats for S terms
		xs, xevs, xr = sodict[phase]
		xxw = array([ xs[i] for i in indstaw ])
		xxe = array([ xs[i] for i in indstae ])
		print('==> {:s} station  terms (all, W, E) :'.format(phase))
		print('      AVE: {:6.2f} {:6.2f} {:6.2f} s'.format(mean(xs), mean(xxw), mean(xxe)))
		print('      STD: {:6.2f} {:6.2f} {:6.2f} s'.format(std(xs), std(xxw), std(xxe)))
		print('      RMS: {:6.2f} {:6.2f} {:6.2f} s'.format(rms(xs), rms(xxw), rms(xxe)))
		# stats for E terms
		eave = [ mean(xevs[i])  for i in range(4) ]
		estd = [  std(xevs[i])  for i in range(4) ]
		erms = [  rms(xevs[i])  for i in range(4) ]
		print('==> {:s} event    terms (otime, lat, lon, dep) :'.format(phase))
		print('      AVE: {:6.2f} s {:6.2f} {:6.2f} {:6.2f} km'.format(*eave))
		print('      STD: {:6.2f} s {:6.2f} {:6.2f} {:6.2f} km'.format(*estd))
		print('      RMS: {:6.2f} s {:6.2f} {:6.2f} {:6.2f} km'.format(*erms))
		# stats for E term effects
		ssfile = 'gm-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		vals = loadtxt(ssfile, comments='#')
		eeff = [ vals[:,i] for i in range(4) ]
		eave = [ mean(eeff[i])  for i in range(4) ]
		estd = [  std(eeff[i])  for i in range(4) ]
		erms = [  rms(eeff[i])  for i in range(4) ]
		print('==> {:s} eventeff terms (otime, lat, lon, dep) :'.format(phase))
		print('      AVE: {:6.2f} {:6.2f} {:6.2f} {:6.2f} s'.format(*eave))
		print('      STD: {:6.2f} {:6.2f} {:6.2f} {:6.2f} s'.format(*estd))
		print('      RMS: {:6.2f} {:6.2f} {:6.2f} {:6.2f} s'.format(*erms))
		# stats for E term effects
		eeff = [ vals[:,0], sum(vals[:,1:], 1) ]
		eave = [ mean(eeff[i])  for i in range(2) ]
		estd = [  std(eeff[i])  for i in range(2) ]
		erms = [  rms(eeff[i])  for i in range(2) ]
		print('==> {:s} eventeff terms (otime, lat+lon+dep) :'.format(phase))
		print('      AVE: {:6.2f} {:6.2f} s'.format(*eave))
		print('      STD: {:6.2f} {:6.2f} s'.format(*estd))
		print('      RMS: {:6.2f} {:6.2f} s'.format(*erms))

def getGMDasc(opts, phases):
	'write event term effects (ot, la, lo, dp for all events) to ascii file'
	gmdict = getGMD(opts, phases)
	# event effects terms
	for phase in phases:
		gmfile = 'gm-sol{:d}-{:s}'.format(opts.mode, phase.lower())
		fhead = '# otime      lat        lon        dep \n'
		fmt = '{:10.6f} '*4 + '\n'
		if not os.path.isfile(gmfile):
			print('Save event effects to file: '+gmfile)
			with open(gmfile ,'w') as f:
				f.write(fhead)
				for evid in sorted(gmdict):
					if phase in gmdict[evid]:
						gmd = gmdict[evid][phase]
						vals = [ f.write(fmt.format(*gmd[sta]))  for sta in sorted(gmd) ]



def getAYD(opts, phases, azims, years):
	ayfile = 'aygm-sol{:d}.pkl'.format(opts.mode)
	if os.path.isfile(ayfile):
		aydict = readPickle(ayfile)
	else:
		print('Get azimuth-year division of event-term effects')
		naz = len(azims)
		iaz = range(naz)
		nyy = len(years)
		iyy = range(nyy)
		evazs = [ readStation('evaz{:d}'.format(i)) for i in range(naz) ]
		aydict = {}
		for phase in phases:
			aydict[phase] = {}
			for ia in iaz:
				aydict[phase][ia] = {}
				for iy in iyy:
					aydict[phase][ia][iy] = {}
		gmdict = getGMD(opts, phases)
		# get all event-term effects binned by azimuth and year:
		for evid in sorted(gmdict):
			year = int(evid[:4])
			iy = -1
			for i in iyy:
				if year in years[i][0]:
					iy = i
					continue
			if iy >= 0:
				ia = -1
				for i in iaz:
					if evid in evazs[i]: 
						ia = i
						continue
				gmd = gmdict[evid]
				#elat, elon = eqdict[evid][6:8]
				for phase in sorted(gmd):
					vdict = gmd[phase]
					for sta in sorted(vdict):
						# ot, sum of lat/lon/dep
						vo, vh = vdict[sta][0], sum(vdict[sta][1:])
						if not sta in aydict[phase][ia][iy]:
							aydict[phase][ia][iy][sta] = [vh,]
						else:
							aydict[phase][ia][iy][sta].append(vh)
		# calculate means to replace all :
		for phase in phases:
			for ia in iaz:
				for iy in iyy:
					for sta in sorted(aydict[phase][ia][iy]):
						aydict[phase][ia][iy][sta] = mean(aydict[phase][ia][iy][sta])
		writePickle(aydict, ayfile)
	return aydict

def plotAYDazim(opts, phases, years, ia):
	'Plot hypo-term effects for an azimuth '
	nyy = len(years)
	fig = figure(figsize=(18,9))
	suptitle('Hypo-term effects : azim {:d} '.format(ia))
	subplots_adjust(left=.03, right=.99, bottom=.01, top=.92, wspace=.06, hspace=0.01)
	np = len(phases)
	vind = 0
	for ip in range(np):
		opts.vlims = opts.avlims[ip]
		phase = phases[ip]
		for iy in range(nyy):
			subplot(2, 4, nyy*ip + iy+1)
			if ip == 0:
				title(years[iy][1])
			ayd = aydict[phase][ia][iy]
			for sta in sorted(ayd):
				ayd[sta] = [ayd[sta],]
			clab = phase 
			plotdelaymap(ayd, vind, cmap, clab, opts)

	fignm = 'aygm-sol{:d}-az{:d}.png'.format(opts.mode, ia)
	saveFigure(fignm, opts)



def rmEventEffect(opts, phase):
	gmdict = getGMD(opts, phases)
	dtdict = getDictDT(opts)

	erfile = 'erdtdict.pkl'
	erdict = {}
	for evid in sorted(dtdict):
		erdict[evid] = {}
		gmd = gmdict[evid]
		print('remove event effects for event: ' + evid)
		for phase in phases:
			if phase in dtdict[evid]:
				print('phase: ' + phase)
				erd = {}
				xdict, xdelay = dtdict[evid][phase]
				vdict = gmd[phase]
				for sta in sorted(xdict):
					vo, vh = vdict[sta][0], sum(vdict[sta][1:])
					erd[sta] = xdict[sta] - vh 
				erdict[evid][phase] = erd, xdelay-vo
	writePickle(erdict, erfile)



def rms(data):
	'root-mean-square'
	return sqrt(mean(data**2))

def eventScale():
	'Get mean of event terms to scale G matrix'
	esdict = {}
	for phase in 'P', 'S':
		n = 0
		d = zeros(3)
		for evid in dddict.keys():
			evdict = dddict[evid]
			if phase in evdict:
				ddict, dtd = evdict[phase]
				n += len(ddict)
				d += len(ddict)*abs(dtd)
		esdict[phase] = d/n
	return esdict

def test():
	slat, slon, selv = 38.05570, -91.24460, 0.172
	elat, elon, edep = 52.258, -168.761, 16.0	
	vps = getVel(opts.dpvpvs, edep)
	vdep = vps[1]
	phase = 'S'
	#vdep = vps[0]
	#phase = 'P'
	mod = opts.model
	dtdla, dtdlo, dtddp = dtdhypo(mod, phase, slat, slon, elat, elon, edep, vdep)
	print dtdla, dtdlo, dtddp

def test2():
	phase = 'S'
	xstdict, xdtdict, xdddict = uniqDictsDeprecated(stadict, dtdict, dddict, phase)

def solveQR(g):
	print('Solving matrices by qr decomposition.')
	qq, rr = linalg.qr(g)
	qb = dot(qq.T, d)
	xq = linalg.solve(rr, qb)
	#qq, rr = linalg.qr(gtg)
	#qb = dot(qq.T, gtd)
	#xq = linalg.solve(rr, qb)
	return x

def solveLstsq(g, d):
	gtg = dot(g.T, g)
	gtd = dot(g.T, d)
	#xsol = linalg.lstsq(g, d)
	xsol = linalg.lstsq(gtg, gtd)
	return xsol



if __name__ == '__main__':	

	notes = {}
	notes[0] = 'nsta + nevt*1 (ot)' 
	notes[1] = 'nsta + nevt*1 (ot) + region 2' 
	notes[2] = 'nsta + nevt*1 (ot,dp) + region 2' 
	notes[3] = 'nsta + nevt*1 (ot,la,lo) + region 2' 
	notes[4] = 'nsta + nevt*1 (ot,la,lo,dp) + region 2' 
	notes[5] = 'nsta + nevt*1 (ot,dp)' 
	notes[6] = 'nsta + nevt*1 (ot,la,lo)' 
	notes[7] = 'nsta + nevt*1 (ot,la,lo,dp)' 
	notes[8] = 'nsta + nevt*1 (ot,la,lo,dp) + region 2x2' 
	notes[9] = 'nsta + nevt*1 (ot,la,lo,dp) (evdamp)' 

 	opts, phases = getOptions()
	getModel(opts)	
	phases = [ phase.upper()  for phase in phases]
	#test()
	#test2()

	opts.nets = 'ta', 'xa', 'xr'
	opts.phases = 'P', 'S'
	# get evt and sta list
	opts.eqfile = 'ref.teqs'
	opts.stfile = 'ref.tsta'

	absdt = True	# absolute delay time
	absdd = False	# relative dtdla, dtdlo, dtddp
	absdd = True	# absolute dtdla, dtdlo, dtddp
	absdd = opts.absdd
	#if opts.reldd:
	#	absdd = False
	#else:
	#	absdd = True

	# global variables: stawest, staeast, dtdict, dddict..
	fwest, feast = 'loc.sta.west', 'loc.sta.eastx'
	stawest = readStation(fwest)
	staeast = readStation(feast)

	#dtdict, dddict, stdict, eqdict = getDicts(opts)
	stdict, eqdict = getDictSE(opts)
	astas = sorted(stdict.keys())
	aevts = sorted(eqdict.keys())
	nsta = len(astas)
	nevt = len(aevts)
	print('Number of station, event : {:d}  {:d}'.format(nsta, nevt))

	# get number of event and station terms 
	getN(opts)

	# determine x (and y) of station terms to plot
	opts.plotnum, opts.plotlon, opts.plotloc = False, False, False
	if opts.plotsta == 'num':
		opts.plotnum = True
	elif opts.plotsta == 'lon':
		opts.plotlon = True
	elif opts.plotsta == 'loc' or opts.plotsta == '3d':
		opts.plotloc = True

	# sort by lon
	staw, stae = {}, {}
	for sta in astas:
		if sta in stawest:
			staw[sta] = stdict[sta]
		elif sta in staeast:
			stae[sta] = stdict[sta]
	staw = sorted(staw.items(), key=lambda x: x[1][1])
	stae = sorted(stae.items(), key=lambda x: x[1][1])
	indstaw = [ astas.index(a[0]) for a in staw ]
	indstae = [ astas.index(a[0]) for a in stae ]
	stawlon = [ a[1][1] for a in staw ]
	staelon = [ a[1][1] for a in stae ]
	nstaw = len(indstaw)
	nstae = len(indstae)
	# sta loc
	aslocs = array([ stdict[sta][:2]  for sta in astas])
	aslats = aslocs[:,0]
	aslons = aslocs[:,1]
	# evt loc
	aelocs = array([ eqdict[evt][6:9] for evt in aevts])
	aelats = aelocs[:,0]
	aelons = aelocs[:,1]
	aedeps = aelocs[:,2]

	# event term scales
	#esdict = eventScale() 

	# get solution and plot
	sodict = readSol(opts, phases)
	if opts.plotfig:
		plotSol(opts, phases, sodict)


	# effects of event terms
	elabs = 'OT', 'Lat', 'Lon', 'Dep', 'Lat+Lon+Dep'
	units = 's', 'km', 'km', 'km'
	opts.axlims = [-126, -66, 25, 50]
	clon, clat = -96, 37.5
	#opts.axlims = [-126, -106, 30, 40]
	#clon, clat = -116, 35
	opts.alpha = 0.8
	opts.msize = 5
	opts.marker = 'o'
	opts.physio = True
	opts.plotcbar = 'h'
	opts.vlims = None, None

	if opts.effevt:
		ckey = 'RdBu_r'
		print('Build color palatte using key: '+ckey)
		cdict = cm.datad[ckey]
		cmap = get_cmap(ckey)
		gmdict = getGMD(opts, phases)
		plotGMD(opts, phases, gmdict)

	if opts.sestats:
		getSEstats(opts, phases)


	azims = [10, 100, 200, 280] # azimuth
	#years = range(2005, 2012)
	years = {}
	years[0] = [2005, 2006], '2005-2006'
	years[1] = [2007, 2008], '2007-2008'
	years[2] = [2009, 2010], '2009-2010'
	years[3] = [2011,     ], '2011'

	if opts.azimdiv:
		ckey = 'RdBu_r'
		print('Build color palatte using key: '+ckey)
		cdict = cm.datad[ckey]
		cmap = get_cmap(ckey)
		aydict = getAYD(opts, phases, azims, years)
		opts.avlims = (-0.05, 0.05), (-0.15, 0.15)
		for ia in range(len(azims)):
			plotAYDazim(opts, phases, years, ia)

	if opts.rmeffevt:
		rmEventEffect(opts, phase)

	sys.exit()
