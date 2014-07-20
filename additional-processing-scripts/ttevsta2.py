#!/usr/bin/env python
"""
Invert delay times for (nsta + nevt*4) terms in an over determined linear system using lsqr.

Difference from ttevsta.py:  Damp only event terms but not station terms

This program is integrated to ttevsta.py and kept for probable P/S joint inversion.

xlou 01/17/2013
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
from ttevsta import getDictSE, getDictST, getDictDT, getDictDD, getSta, getEvt
from ttevsta import readGD, writeGD, makeAxes


def getOptions():
	""" Create a parser for options """
	usage = "Usage: %prog [options] <phases>"
	parser = OptionParser(usage=usage)
	refmodel = 'iasp91'
	locsta = 'loc.sta'
	tfilename = 'dtdict.pkl'
	dfilename = 'dtderi.pkl'
	sfilename = 'sol.pkl'
	mode = 9
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
	parser.add_option('-n', '--newsol', action="store_true", dest='newsol',
		help='New solution instead of reading from file')
	parser.add_option('-D', '--dampcoef',  dest='dampcoef', type='float',
		help='Damping coefficient. Default is {:f}'.format(dampcoef))
	parser.add_option('-e', '--effevt', dest='effevt', type='int', nargs=2,
		help='Effects of event terms. Give event index range')
	parser.add_option('-T', '--sestats', action="store_true", dest='sestats',
		help='Stats of se terms')
	parser.add_option('-c', '--escale', action="store_true", dest='escale',
		help='Scale event terms')

	opts, files = parser.parse_args(sys.argv[1:])
	if files == []:
		files = ['P', 'S']
	if opts.plotsta not in ['num', 'lon', 'loc', '3d']:
		print('Wrong -S option for plotting station terms.')
		sys.exit()
	return opts, files



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
		# damp event terms
		edamp = [1, 0.1, .1, .1]
		edamp = [1, .5, .5, .2]
		for i in range(nevt):
			n = nsta+i*4
			for j in range(4):
				gdict[k] = {}
				gdict[k][n+j] = edamp[j]
				k += 1
				d.append(0)
			
		gdim = k, ny
		t1 = clock()
		#calTime(t1-t0, 'building matrices')
		writeGD(gdict, d, gdim, gfile, dfile)
	g, d = readGD(gfile, dfile, ny)	
	return g, d



def solveGD(opts, phase='S'):
	mode = opts.mode
	gfile = 'matrix{:d}-{:s}-g'.format(mode, phase.lower())
	dfile = 'matrix{:d}-{:s}-d'.format(mode, phase.lower())
	if opts.newsol:
		os.system('/bin/rm -f {:s} {:s}'.format(gfile, dfile))
	if mode == 9:
		buildGD = buildGD9
	if mode == 10:
		buildGD = buildGD10
	elif mode == 11:
		buildGD = buildGD11
	elif mode == 12:
		buildGD = buildGD12
	g, d = buildGD(gfile, dfile, phase)
	nx, ny = g.shape
	print('--> Solving G^TGm = G^Td by least squares...')
	#xsol = lsqr(g, d, damp=opts.dampcoef, show=True)
	xsol = lsqr(g, d, show=True)
	return xsol

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


def getN(opts):
	' get number of event and station terms (matrix dimension)'
	mode = opts.mode
	#if mode == 10:
	nr = 0
	ns = nsta
	ne = nsta + nevt*4
	ny = nsta + nevt*4*2
	print('Number of S/E/R terms: {:d} {:d} {:d} {:d}'.format(ns, ne, nr, ny))
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
	inds = range(4)
	for i in inds:
		xevs[i] = xe[i::4]
	if nr > 0:
		xr = xx[-nr:]
	else:
		xr = None
	return xs, xevs, xr


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
		#axevts[0].set_ylim(-6,12)
		#axevts[1].set_ylim(-20,20)
		#axevts[2].set_ylim(-20,20)
		#axevts[3].set_ylim(-20,20)

	if opts.plotnum:
		fignm = opts.sfilename.replace('.pkl', '{:d}.png'.format(opts.mode))
	else:
		fignm = opts.sfilename.replace('.pkl', '{:d}{:s}.png'.format(opts.mode, opts.plotsta))

	saveFigure(fignm, opts)



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

	notes[10] = 'nsta + nevt*4 (ot,la,lo,dp)' 

 	opts, phases = getOptions()
	phases = [ phase.upper()  for phase in phases]

	opts.nets = 'ta', 'xa', 'xr'
	opts.phases = 'P', 'S'
	# get evt and sta list
	opts.eqfile = 'ref.teqs'
	opts.stfile = 'ref.tsta'

	absdt = True	# absolute delay time
	#absdd = False	# relative dtdla, dtdlo, dtddp
	#absdd = True	# absolute dtdla, dtdlo, dtddp
	absdd = opts.absdd

	# global variables: stawest, staeast, dtdict, dddict..
	fwest, feast = 'loc.sta.west', 'loc.sta.east'
	stawest = readStation(fwest)
	staeast = readStation(feast)

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


	# get solution and plot
	if opts.newsol:
		os.system('rm -f *sol{:d}*'.format(opts.mode))
	sodict = readSol(opts, phases)
	if opts.plotfig:
		plotSol(opts, phases, sodict)


#######
	mode = opts.mode
	gfile = 'matrix{:d}-{:s}-g'.format(mode, phase.lower())
	dfile = 'matrix{:d}-{:s}-d'.format(mode, phase.lower())

