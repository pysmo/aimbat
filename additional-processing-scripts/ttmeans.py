#!/usr/bin/env python
"""
Read event-mean delay times for P and S.

xlou 01/27/2013
"""

import os, sys, commands
from numpy import loadtxt
from pylab import *
from optparse import OptionParser
from ttcommon import readStation
from ppcommon import saveFigure


def getParams():
	""" Parse arguments and options. """
	usage = "Usage: %prog [options] <file(s)>"
	parser = OptionParser(usage=usage)
	ojinv = 'out.jinv'
	parser.set_defaults(ojinv=ojinv)
	parser.add_option('-o', '--ojinv',  dest='ojinv', type='str',
		help='Output file of jinv (input for this program).')
	parser.add_option('-g', '--savefig', dest='savefig', type='str', 
		help='Save figure instead of showing (png/pdf).')
	parser.add_option('-e', '--einv', action="store_true", dest='einv',
		help='Compare dmeans with event terms')
	parser.add_option('-j', '--jinv', action="store_true", dest='jinv',
		help='Compare jinv results')
	opts, files = parser.parse_args(sys.argv[1:])
	return opts, files


def getMeans(ofiles):
	eqfile = 'ref.teqs'
	edict  = readStation(eqfile)
	#
	nets = 'ta', 'xa', 'xr'
	dmdict = {}
	for net in nets:
		dfile = 'dmeans-' + net
		ddict = readStation(dfile)
		for evid in sorted(ddict):
			dmdict[evid] = ddict[evid]
	# output
	fmt = '{:7.2f} '*4 + '\n'
	mdicts = {}
	for i in range(2):
		ofile = ofiles[i]
		if not os.path.isfile(ofile):
			print('Save event mean delays to file : '+ ofile)
			with open(ofile, 'w') as f:
				for evid in sorted(dmdict):
					dm = dmdict[evid][i]
					if dm != 0.0:
						tt = [dm,] + list(edict[evid][6:9])
						f.write('{:s} '.format(evid) + fmt.format(*tt))
		mdicts[i] = readStation(ofile)
	return mdicts


def plotdmco(mdicts):
	"""
	Plot event-mean delays and event terms from esinv.
	# run at ~/work/na/sod/tamw60pkl/hdelays/eip
	"""
	cdir = 'ddrel-damp/'
	cofiles = cdir + 'evtco-sol9-p', cdir + 'evtco-sol9-s'
	cdicts = [ readStation(cofiles[i]) for i in range(2) ]
	fig = figure(figsize=(8,8))
	phases = 'P', 'S'
	cols = 'b', 'r'
	scales = 1, 1
	for i in range(2):
		evids = sorted(mdicts[i])
		col = cols[i]
		mm = array([ mdicts[i][evid][0]  for evid in evids ]) * scales[i]
		cc = array([ cdicts[i][evid][0]  for evid in evids ]) * scales[i]
		plot(mm, cc, color=col, marker='.', ls='None', label=phases[i])
		dd =  mm - cc
		mmm, mms, mmr = mean(mm), std(mm), sqrt(mean(mm**2))
		ccm, ccs, ccr = mean(cc), std(cc), sqrt(mean(cc**2))
		ddm, dds, ddr = mean(dd), std(dd), sqrt(mean(dd**2))
		#axvline(x=mmm, color=col, ls='--', lw=2)
		#axhline(y=ccm, color=col, ls='--', lw=2)
		print('Phase {:s} evmean ::  ave={:.2f}  std={:.2f}  rms={:.2f} s'.format(phases[i],mmm,mms,mmr))
		print('Phase {:s} evcorr ::  ave={:.2f}  std={:.2f}  rms={:.2f} s'.format(phases[i],ccm,ccs,ccr))
		print('Phase {:s} ev m-c ::  ave={:.2f}  std={:.2f}  rms={:.2f} s'.format(phases[i],ddm,dds,ddr))
	xlabel('Event-mean Delay [s]')
	ylabel('Event correction [s]')
	legend(loc=2)
	axis('equal')
	grid()
	axis([-11,11,-11,11])
	fignm = 'evdmco.png'
	return fignm

def plotjot():
	"""
	Compare abs/rel jinv results of event relocation
	# run at ~/work/na/inv/20121003/svel/test1
	"""
	idirs = 'bw3', 'bw3rel'
	edicts = [ readStation(idir + '/evtco-' + idir)  for idir in idirs ]

	evids = sorted(edicts[0])
	ota =  [ edicts[0][evid][0]  for evid in evids ]
	otb =  [ edicts[1][evid][0]  for evid in evids ]

	fig = figure(figsize=(8,8))
	plot(ota, otb, 'b.')
	xlabel(idirs[0])
	ylabel(idirs[1])
	axis('equal')
	grid()
	fignm = 'evot-{:s}-{:s}.png'.format(idirs[0], idirs[1])
	return fignm


def plotdmjcc():
	# compare dmeans, evtco of abs and rel
	idirs = 'ttabs', 'ttrel'
	edicts = [ readStation(idir + '/evtco-' + idir)  for idir in idirs ]
	mdict = readStation('ttabs/tt-means')
	evids = sorted(edicts[0])
	ota =  array([ edicts[0][evid][0]  for evid in evids ])
	otb =  array([ edicts[1][evid][0]  for evid in evids ])
	otm =  array([ mdict[evid][0]  for evid in evids ])

	fig = figure(figsize=(10,6))
	plot(otm, '-', label='evmean')
	plot(ota, '-', label='ttabs')
	plot(otb, '-', label='ttrel')
	#plot(ota+otb, '-', label='ttabs+ttrel')
	#plot(otm-ota, '-', label='mean-ttabs')
	plot(ota-otm, '-', label='ttabs-evmean')
#	plot(ota, otb, 'b.')
	xlabel('Event number')
	ylabel('Time [s]')
	legend()
	grid()
	fignm = 'evdmjcc.png'
	return fignm



if __name__ == '__main__':

	opts, ifiles = getParams()

	# run at ~/work/na/sod/tamw60pkl/hdelays/eip
	dmfiles = 'evdmean-p', 'evdmean-s'
	if opts.einv:
		mdicts = getMeans(dmfiles)
		fignm = plotdmco(mdicts)
		saveFigure(fignm, opts)

	# run at ~/work/na/inv/20121003/svel/test1
	if opts.jinv:
		fignm = plotjot()
		saveFigure(fignm, opts)

	# run at ~/work/na/inv/20121003/svel/test1

	fignm = plotdmjcc()
	saveFigure(fignm, opts)
	
