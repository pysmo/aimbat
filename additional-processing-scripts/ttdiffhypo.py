#!/usr/bin/env python
"""
Delay time difference caused by using hypocenters and origins from different catalogs.

xlou 09/04/2012
"""

from pylab import *
from ttcommon import readStation, saveStation, readPickle, writePickle
from ttdict import getParser, delKeys, getDict, delayStats 

def getParams():
	""" Parse arguments and options from command line. """
	parser = getParser()
	opts, files = parser.parse_args(sys.argv[1:])
	return opts, files


def getDiff(dd0, dd1):
	'Get tt difference'
	olists = [], []
	for ev in sorted(dd1.keys()):
		evd0 = dd0[ev]
		evd1 = dd1[ev]
		for phase, olist in zip(phases, olists):
			if phase in evd1:
				d0, t0 = evd0[phase]
				d1, t1 = evd1[phase]
				evt0 = array([ d0[sta] for sta in sorted(d0.keys()) ]) + t0
				evt1 = array([ d1[sta] for sta in sorted(d1.keys()) ]) + t1
				olist += list(evt1-evt0)
	return olists


def plotDiff(ttdir):
	ddicts = []
	for cdir in cdirs:
		dfile = cdir + '/' + ttdir + '/' + dtfile
		dd = readPickle(dfile)
		ddicts.append(dd)
	dta = getDiff(ddicts[0], ddicts[1])
	dtb = getDiff(ddicts[0], ddicts[2])
	dtc = getDiff(ddicts[1], ddicts[2])

	dts = dta, dtb, dtc
	legs = 'ISC-PDE', 'EHB-PDE', 'EHB-ISC'
	nc = len(dts)

	figure(figsize=(20,10))
	subplots_adjust(left=0.04, right=0.98, bottom=0.05, top=.92)
	for i in range(np):
		subplot(np, 1, i+1)
		for j in range(nc):
			dt = dts[j][i]
			lab = '{:s}: mean={:f} std={:f}'.format(legs[j], mean(dt), std(dt))
			plot(dt, marker='.', ms=4, lw=.3, label=lab)
		legend()
		title(phases[i]+ ' Delay Difference')
		ylabel(phases[i] + ' Delay Difference [s]')
	suptitle(ttdir)

	fignm = 'tdiff-' + ttdir.split('-')[1] + '.'  + opts.figfmt
	if opts.savefig:
		savefig(fignm, format=opts.figfmt)

if __name__ == '__main__':

	opts, ifiles = getParams()

	ttdir = 'tcorr-toposedimoho'

	ttdirs = 'tcorr-ellip', 'tcorr-topo', 'tcorr-toposedi', 'tcorr-toposedimoho'

	cdirs = 'pde', 'isc', 'ehb'
	dtfile = 'dtdict.pkl'
	phases = 'P', 'S'
	np = len(phases)

	for ttdir in ttdirs:
		plotDiff(ttdir)

	if not opts.savefig:
		show()
