#!/usr/bin/env python
"""
File: ttdict.py

This script/module deals with MCCC delay times which are saved in python dict.

Dict strcture:
	dtdict[evid] = evdict
		evdict['event'] = event
		evdict[phase] = xdict, xdelay
			xdict is a dict of relative delay times.
			xdelay is the average absolute delay time.

Three ways to get delay time dict:
	If "-i ifilename" is given:
		Read delay times from input dict file and command line parsed xfiles are not used.
	If "-o ofilename" is given:
		Read delay times from command line parsed xfiles and output to dict file.
	If neither "-i ifilename" and "-o ofilename" are given:
		Read delay times from command line parsed xfiles but not output to dict file.


Run ttstats.py for delay statistics
Run ttpairs.py for delay pairs

xlou 12/22/2011
"""

from numpy import *
from scipy import optimize
import os, sys
from optparse import OptionParser
from ttcommon import readMLines, parseMLines, readPickle, writePickle
from ttcommon import readStation, saveStation
from ppcommon import plotphysio, plotcoast

def getParser():
	""" Create a parser """
	usage = "Usage: %prog [options] <xfiles>"
	parser = OptionParser(usage=usage)
	locsta = 'loc.sta'
	cptkey = 'RdBu_r'
	figfmt = 'png'
	dpi = 200
	#ofilename = 'dtdict.pkl'
	#parser.set_defaults(ofilename=ofilename)
	parser.set_defaults(locsta=locsta)
	parser.set_defaults(cptkey=cptkey)
	parser.set_defaults(figfmt=figfmt)
#	parser.set_defaults(dpi=dpi)
	parser.add_option('-a', '--absdt', action="store_true", dest='absdt',
		help='Get absolute delay times. Default is relative.')
	parser.add_option('-m', '--rmean', action="store_true", dest='rmean',
		help='Remove mean delay times.')
	parser.add_option('-i', '--ifilename',  dest='ifilename', type='str',
		help='Read delay times from input dict file and command line parsed xfiles are not used.')
	parser.add_option('-o', '--ofilename',  dest='ofilename', type='str',
		help='Read delay times from command line parsed xfiles and output to dict file.')
	parser.add_option('-l', '--locsta',  dest='locsta', type='str',
		help='File for station location.')
	parser.add_option('-A', '--evabsdelete',  dest='evabsdelete', type='str',
		help='A file containing event ids to exclude for absolute delay times.')
	parser.add_option('-E', '--evdelete',  dest='evdelete', type='str',
		help='A file containing event ids to exclude.')
	parser.add_option('-S', '--stdelete',  dest='stdelete', type='str',
		help='A file containing station names to exclude.')
	parser.add_option('-C', '--cptkey',  dest='cptkey', type='str',
		help='Color palatte key. Default is {:s}'.format(cptkey))
	parser.add_option('-g', '--savefig', type='str', dest='savefig',
		help='Save figure to file instead of showing.')
	parser.add_option('-G', '--figfmt',type='str', dest='figfmt',
		help='Figure format for savefig. Default is {:s}'.format(figfmt))
#	parser.add_option('-D', '--dpi',type='int', dest='dpi',
#		help='Figure dpi. Default is {:d}'.format(dpi))
	parser.add_option('-k', '--blackwhite', action="store_true", dest='blackwhite',
		help='Plot in black&white')
	return parser

def getParams():
	""" Parse arguments and options from command line. """
	parser = getParser()
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0 and opts.ifilename is None:
		print parser.usage
		sys.exit()
	return opts, files

def delKeys(ddict, dfile):
	'Delete ddict keys given in dfile' 
	df = open(dfile)
	dlines = df.readlines()
	df.close()
	for line in dlines:
		if line[0] != '#':
			sline = line.split()
			if sline != []:
				key = sline[0]
				if key in ddict:
					del ddict[key]
					print('  delete key: '+key)
	return ddict

def getDict(opts, ifiles):
	""" Get dtdict """
	if opts.ifilename:
		dtdict = readPickle(opts.ifilename)
	elif opts.ofilename:
		dtdict = getDelays(ifiles)
		writePickle(dtdict, opts.ofilename)
	else:
		dtdict = getDelays(ifiles)
	return dtdict

def readXFile(xfile):
	""" Get delay times from a xfile.
	"""
	print('Reading xfile: ' + xfile)
	headlines, mccclines, taillines = readMLines(xfile)
	phase, event, stations, ttimes, sacnames = parseMLines(mccclines, taillines)	
	nsta = len(stations)
	mccctt_mean = float(taillines[0].split()[1])
	theott_mean = float(taillines[0].split()[3])
	xdelay = mccctt_mean - theott_mean
	xdict = {}
	for i in range(nsta):
		sta = stations[i]
		rdelay, stda, cc = ttimes[i][7], ttimes[i][1], ttimes[i][2]
		xdict[sta] = rdelay
	evid = xfile.split('/')[-1][:17]
	return evid, event, phase, xdict, xdelay
				
def getDelays(ifiles):
	""" Get delay times from multiple xfiles into a dict.
	"""
	dtdict = {}
	for ifile in ifiles:
		evid, event, phase, xdict, xdelay = readXFile(ifile)
		if evid in dtdict:
			evdict = dtdict[evid]
		else:
			evdict = {}
			dtdict[evid] = evdict
		evdict['event'] = event
		evdict[phase] = xdict, xdelay
	return dtdict

def delayStats(dtdict, stadict, phase='S', absdt=False, rmean=False, ndtmin=1):
	""" Calculate stats of delay times.
		Also save number of measurements
	"""
	statdict = {}
	for evid in dtdict.keys():
		evdict = dtdict[evid]
		if phase in evdict:
			xdict, xdelay = evdict[phase]
			for sta in xdict.keys():
				dt = xdict[sta]
				if absdt:
					dt += xdelay
				if sta in statdict:
					statdict[sta].append(dt)
				else:
					statdict[sta] = [dt,]
	alldt = []
	for sta in statdict.keys():
		alldt += statdict[sta]
	alldt = array(alldt)
	mdt = mean(alldt)
	sdt = std(alldt)
	rdt = sqrt(mean(alldt**2))
	print('** Mean, STD, and RMS of {:s} delay: {:8.3f} {:8.3f} {:8.3f}'.format(phase, mdt, sdt, rdt))
	print('**   {:6d} measurements from {:6d} events'.format(len(alldt), len(dtdict.keys())))
	# in case not all stations are used:
	newdict = {}
	for sta in statdict.keys():
		dts = statdict[sta]
		if rmean:
			dts -= mdt
		if sta in stadict:
			ndt = len(dts)
			if ndt >= ndtmin:
				newdict[sta] = stadict[sta][:2] + [mean(dts), std(dts), ndt]
			else:
				print('Discard station {:s} for {:d} < {:d} measurements'.format(sta, ndt, ndtmin))
	return newdict, mdt, sdt, rdt 

					

def lsq(fx, fy, dnorm=2):
	""" Find ratio of S and P delays by least-squares fitting of a straight line y=a*x+b.
		Minimize the distance of a point (x0,y0) to the line: 
		L2-norm: d2 = abs(a*x0+b-y0)/sqrt(1+a**2)
		L1-norm: d1 = abs(y0-a*x0-b) + abs(x0-y0/a+b/a)
		L1-norm with weights: d1 = abs(y0-a*x0-b) + 3*abs(x0-y0/a+b/a)
	"""
	### Define target fit function and error function to minimize.
	fitfunc = lambda p,x: p[0]*x+p[1]
	if dnorm == 2:
		# distance of L2-norm:
		errfunc = lambda p,x,y: abs(fitfunc(p,x)-y)/sqrt(p[0]**2+1)
	elif dnorm == 1:
		# distance of L1-norm:
		errfunc = lambda p,x,y: abs(fitfunc(p,x)-y) + abs(x-y/p[0]+p[1]/p[0])
	elif dnorm == 13:
		# distance of L1-norm, but weight of |dx| is 3 times of |dy|
		errfunc = lambda p,x,y: abs(fitfunc(p,x)-y) + 3*abs(x-y/p[0]+p[1]/p[0])
	else:
		print('Unkonwn norm of distance! Exit..')
		sys.exit()
	### Initial values and lsq results
	pinit = [3,0]
	out = optimize.leastsq(errfunc, pinit[:], args=(fx,fy), full_output=1)
	pfinal = out[0]
	covar = out[1]
	### slope of the fitting line and std
	a = pfinal[0]
	b = pfinal[1]
	sa = sqrt(covar[0][0])
	sb = sqrt(covar[1][1])
	print('lsq fit: slope '+ r'$ {:4.2f} \pm {:4.2f} $'.format(a,sa))
	return a, b, sa, sb


def delayPairs(dtdict, stadict, absdt=False):
	""" Get delay time pairs and single P/S delays	"""
	pha = 'P'
	phb = 'S'
	dpair = []
	xp, xs = [], []
	nevs = [0, 0, 0]
	for evid in sorted(dtdict.keys()):
		evdict = dtdict[evid]
		if pha in evdict and phb in evdict:
			nevs[0] += 1
			pdict, pdelay = evdict[pha]
			sdict, sdelay = evdict[phb]
			if not absdt:	# change event mean delay to 0 for relative arrivvals
				pdelay = 0
				sdelay = 0
			for sta in sorted(stadict.keys()):
				if sta in pdict and sta in sdict:
					tp = pdict[sta] + pdelay
					ts = sdict[sta] + sdelay
					dpair.append([tp, ts])
					#if tp < -2.3 and ts > -7:
					#	print('Delay-pair-outlier: {:s} {:<9s} {:6.1f} {:6.1f} '.format(evid, sta, tp, ts))
				elif sta in pdict:
					tp = pdict[sta] + pdelay
					xp.append(tp)
				elif sta in sdict:
					ts = sdict[sta] + sdelay
					xs.append(ts)
		elif pha in evdict:
			nevs[1] += 1
			pdict, pdelay = evdict[pha]
			if not absdt: pdelay = 0
			for sta in stadict.keys():
				if sta in pdict:
					xp.append(pdict[sta]+pdelay)
		else:
			nevs[2] += 1
			sdict, sdelay = evdict[phb]
			if not absdt: sdelay = 0
			for sta in stadict.keys():
				if sta in sdict:
					xs.append(sdict[sta]+sdelay)
	dpair = array(dpair)
	xps = [ array(xp), array(xs) ]
	print('Getting station delay times for each event... ')
	print('  P/S delay pairs: {:6d} from {:6d} events'.format(len(dpair), nevs[0]))
	print('  Single P delays: {:6d} from {:6d} events'.format(len(xp),    nevs[1]))
	print('  Single S delays: {:6d} from {:6d} events'.format(len(xs),    nevs[2]))
	return dpair, xps


def delayMeans(dtdict, ofilename=None):
	'Get event mean delays'
	pha, phb = 'P', 'S'
	dpair = []
	xp, xs = [], []
	nevs = [0, 0, 0]
	if ofilename is not None:
		ofile = open(ofilename, 'w')
	for evid in dtdict.keys():
		evdict = dtdict[evid]
		if pha in evdict and phb in evdict:	
			pdict, pdelay = evdict[pha]
			sdict, sdelay = evdict[phb]
			dpair.append([pdelay, sdelay])
			nevs[0] += 1
		elif pha in evdict:
			pdict, pdelay = evdict[pha]
			sdelay = 0
			xp.append(pdelay)
			nevs[1] += 1
		else:
			sdict, sdelay = evdict[phb]
			pdelay = 0
			xs.append(sdelay)
			nevs[2] += 1
		if ofilename is not None:
			ofile.write('{:s} {:8.3f} {:8.3f} \n'.format(evid, pdelay, sdelay))
		else:
			print('{:s}: {:8.3f} {:8.3f} '.format(evid, pdelay, sdelay))
	if ofilename is not None: ofile.close()
	dpair = array(dpair)
	xps = [ array(xp), array(xs) ]
	print('Getting event mean delay times for all {:d} events... '.format(len(dtdict.keys())))
	print('  P/S delay pairs: {:6d} events'.format(nevs[0]))
	print('  Single P delays: {:6d} events'.format(nevs[1]))
	print('  Single S delays: {:6d} events'.format(nevs[2]))
	return dpair, xps


def saveFigure(fignm, opts):
	'Save figure to file or plot to screen. Use ppcommon.saveFigure instead.'
	from matplotlib.pyplot import savefig, show
	fmt = opts.figfmt
	if not opts.savefig:
		show()
	else:
		#if opts.figfmt == 'png':
		#	savefig(fignm, format=opts.figfmt, dpi=opts.dpi)
		#else:
		#	fignm = fignm.replace('png', opts.figfmt) 
		#	savefig(fignm, format=opts.figfmt)
		fignm = fignm.replace('png', opts.figfmt) 
		savefig(fignm, format=opts.figfmt)
		print('Save figure to : '+ fignm)



if __name__ == '__main__':

	opts, ifiles = getParams()
	dtdict = getDict(opts, ifiles)

