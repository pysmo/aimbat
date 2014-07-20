#!/usr/bin/env python
"""
Distribution of delay times:  raw, crust-corrected, event-corrected 

xlou 02/02/2013
"""

import os, sys, commands
from numpy import loadtxt
from pylab import *
from optparse import OptionParser
from ttcommon import readPickle, writePickle, readStation
from ppcommon import saveFigure


def getParams():
	""" Parse arguments and options. """
	usage = "Usage: %prog [options] <file(s)>"
	parser = OptionParser(usage=usage)
	ojinv = 'out.jinv'
	parser.set_defaults(ojinv=ojinv)
	parser.add_option('-a', '--adddelay',  dest='adddelay', action="store_true",
		help='Add dtdict from three nets to one dict.')
	parser.add_option('-d', '--distribution',  dest='distribution', action="store_true",
		help='Get distribution.')
	parser.add_option('-g', '--savefig', dest='savefig', type='str', 
		help='Save figure instead of showing (png/pdf).')
	parser.add_option('-e', '--einv', action="store_true", dest='einv',
		help='Compare dmeans with event terms')
	parser.add_option('-j', '--jinv', action="store_true", dest='jinv',
		help='Compare jinv results')
	opts, files = parser.parse_args(sys.argv[1:])
	return opts, files


#def getMeans(ofiles):
#	eqfile = 'ref.teqs'
#	edict  = readStation(eqfile)
#	#
#	nets = 'ta', 'xa', 'xr'
#	dmdict = {}
#	for net in nets:
#		dfile = 'dmeans-' + net
#		ddict = readStation(dfile)
#		for evid in sorted(ddict):
#			dmdict[evid] = ddict[evid]
#	# output
#	fmt = '{:7.2f} '*4 + '\n'
#	mdicts = {}
#	for i in range(2):
#		ofile = ofiles[i]
#		if not os.path.isfile(ofile):
#			print('Save event mean delays to file : '+ ofile)
#			with open(ofile, 'w') as f:
#				for evid in sorted(dmdict):
#					dm = dmdict[evid][i]
#					if dm != 0.0:
#						tt = [dm,] + list(edict[evid][6:9])
#						f.write('{:s} '.format(evid) + fmt.format(*tt))
#		mdicts[i] = readStation(ofile)
#	return mdicts
#
#
#def plotdmco(mdicts):
#	"""
#	Plot event-mean delays and event terms from esinv.
#	# run at ~/work/na/sod/tamw60pkl/hdelays/eip
#	"""
#	cdir = 'ddrel-damp/'
#	cofiles = cdir + 'evtco-sol9-p', cdir + 'evtco-sol9-s'
#	cdicts = [ readStation(cofiles[i]) for i in range(2) ]
#	fig = figure(figsize=(8,8))
#	phases = 'P', 'S'
#	cols = 'b', 'r'
#	scales = 1, 1
#	for i in range(2):
#		evids = sorted(mdicts[i])
#		col = cols[i]
#		mm = array([ mdicts[i][evid][0]  for evid in evids ]) * scales[i]
#		cc = array([ cdicts[i][evid][0]  for evid in evids ]) * scales[i]
#		plot(mm, cc, color=col, marker='.', ls='None', label=phases[i])
#		dd =  mm - cc
#		mmm, mms, mmr = mean(mm), std(mm), sqrt(mean(mm**2))
#		ccm, ccs, ccr = mean(cc), std(cc), sqrt(mean(cc**2))
#		ddm, dds, ddr = mean(dd), std(dd), sqrt(mean(dd**2))
#		#axvline(x=mmm, color=col, ls='--', lw=2)
#		#axhline(y=ccm, color=col, ls='--', lw=2)
#		print('Phase {:s} evmean ::  ave={:.2f}  std={:.2f}  rms={:.2f} s'.format(phases[i],mmm,mms,mmr))
#		print('Phase {:s} evcorr ::  ave={:.2f}  std={:.2f}  rms={:.2f} s'.format(phases[i],ccm,ccs,ccr))
#		print('Phase {:s} ev m-c ::  ave={:.2f}  std={:.2f}  rms={:.2f} s'.format(phases[i],ddm,dds,ddr))
#	xlabel('Event-mean Delay [s]')
#	ylabel('Event correction [s]')
#	legend(loc=2)
#	axis('equal')
#	grid()
#	axis([-11,11,-11,11])
#	fignm = 'evdmco.png'
#	return fignm
#
#def plotjot():
#	"""
#	Compare abs/rel jinv results of event relocation
#	# run at ~/work/na/inv/20121003/svel/test1
#	"""
#	idirs = 'bw3', 'bw3rel'
#	edicts = [ readStation(idir + '/evtco-' + idir)  for idir in idirs ]
#
#	evids = sorted(edicts[0])
#	ota =  [ edicts[0][evid][0]  for evid in evids ]
#	otb =  [ edicts[1][evid][0]  for evid in evids ]
#
#	fig = figure(figsize=(8,8))
#	plot(ota, otb, 'b.')
#	xlabel(idirs[0])
#	ylabel(idirs[1])
#	axis('equal')
#	grid()
#	fignm = 'evot-{:s}-{:s}.png'.format(idirs[0], idirs[1])
#	return fignm
#
#
#def plotdmjcc():
#	# compare dmeans, evtco of abs and rel
#	idirs = 'ttabs', 'ttrel'
#	edicts = [ readStation(idir + '/evtco-' + idir)  for idir in idirs ]
#	mdict = readStation('ttabs/tt-means')
#	evids = sorted(edicts[0])
#	ota =  array([ edicts[0][evid][0]  for evid in evids ])
#	otb =  array([ edicts[1][evid][0]  for evid in evids ])
#	otm =  array([ mdict[evid][0]  for evid in evids ])
#
#	fig = figure(figsize=(10,6))
#	plot(otm, '-', label='evmean')
#	plot(ota, '-', label='ttabs')
#	plot(otb, '-', label='ttrel')
#	#plot(ota+otb, '-', label='ttabs+ttrel')
#	#plot(otm-ota, '-', label='mean-ttabs')
#	plot(ota-otm, '-', label='ttabs-evmean')
##	plot(ota, otb, 'b.')
#	xlabel('Event number')
#	ylabel('Time [s]')
#	legend()
#	grid()
#	fignm = 'evdmjcc.png'
#	return fignm
#

def addDelay(nets, ifilename):
	dtdict = {}
	for net in nets:
		ddict = readPickle(net + '-' + ifilename)
		for evid in sorted(ddict):
			dtdict[evid] = ddict[evid]
	return dtdict

def getDictDT(nets, ifilename):
	if os.path.isfile(ifilename):
		dtdict = readPickle(ifilename)
	else:
		dtdict = addDelay(nets, ifilename)
		writePickle(dtdict, ifilename)
	return dtdict 


def getDelay(ddicts, phase, ofilename):
	'Get delays for abs raw, abs crust-corrected, abs c+e corrected, rel crust-corrected'
	delays = []
	fmt = '{:s} {:<9s} ' + '{:7.2f} '*4 + '\n'
	evts = sorted(ddicts[0])
	ofile = open(ofilename, 'w')
	for ev in evts:
		if phase in ddicts[0][ev]:
			print('get delays from event {:s} phase {:s} '.format(ev, phase))
			rdict, rdelay = ddicts[0][ev][phase]
			cdict, cdelay = ddicts[1][ev][phase]
			edict, edelay = ddicts[2][ev][phase]
			for sta in sorted(rdict):
				ar = rdelay + rdict[sta]
				ac = cdelay + cdict[sta]
				ae = edelay + edict[sta]
				rc = cdict[sta]
				ofile.write(fmt.format(ev, sta, ar, ac, ae, rc))

def getDistri():
	'Get delays for abs raw, abs crust-corrected, abs c+e corrected, rel crust-corrected'
	draw = '../../eip-ellip/dtdict.pkl'  # raw delay
	dcc = '../dtdict.pkl'    # crust-corrected delay
	dec = 'erdtdict.pkl'     # event- and crust-corrected

	dfiles = draw, dcc, dec
	ddicts = [ readPickle(dfile) for dfile in dfiles ]

	for phase in 'P', 'S':
		ofilename = 'dtdistri-{:s}'.format(phase.lower())
		if not os.path.isfile(ofilename):
			getDelay(ddicts, phase, ofilename)



def plotHist1(delays):
	'histrogram of 4 types of delays'
	if phase == 'P':
		binwidth /= 2
	bins = linspace(-20, 20, 40/binwidth+1)

	labs = 'absraw', 'abscc', 'absec', 'relcc'
	cols = 'r', 'g', 'b', 'c'

	figure(figsize=(12,6))
	for i in range(nd):
		col = cols[i]
		dt = delays[i]
		mdt = mean(dt)
		sdt = std(dt)
		rdt = sqrt(mean(dt**2))
		print('Phase {:s} :  ave = {:5.1f}  std={:5.1f}  rms={:5.1f} s'.format(phase, mdt, sdt, rdt))
		hist(delays[i], histtype='step', label=labs[i], lw=2, color=col)
		axvline(x=mdt, color=col, ls='--', lw=3)
		axvline(x=mdt-sdt, color=col, ls=':', lw=2)
		axvline(x=mdt+sdt, color=col, ls=':', lw=2)
	legend()
	show()
	

def plotHist2(phase, binwidth):

	dfile = 'dtdistri-{:s}'.format(phase.lower())
	vals = loadtxt(dfile, usecols=(2,3,4,5))

	nd = len(vals[0])
	delays  = [ vals[:,i]  for i in range(nd) ]

	if phase == 'P':
		binwidth /= 2
	bins = linspace(-20, 20, 40/binwidth+1)

	labs = 'absraw', 'abscc', 'absec', 'relcc'
	cols = 'r', 'g', 'b', 'c'

	fig = figure(figsize=(10,10))

	ax0 = fig.add_subplot(211)
	ax1 = fig.add_subplot(212, sharex=ax0)
	ax = ax0
	for i in range(nd):
		col = cols[i]
		dt = delays[i]
		mdt = mean(dt)
		sdt = std(dt)
		rdt = sqrt(mean(dt**2))
		print('Phase {:s} {:<12s} :  ave = {:5.1f}  std = {:5.1f}  rms = {:5.1f} s'.format(phase, labs[i], mdt, sdt, rdt))
		ax.hist(dt, bins, histtype='step', label=labs[i], lw=2, color=col)
		ax.axvline(x=mdt, color=col, ls='--', lw=3)
		ax.axvline(x=mdt-sdt, color=col, ls=':', lw=2)
		ax.axvline(x=mdt+sdt, color=col, ls=':', lw=2)
	ax.legend(loc=2)

	cols = 'm', 'y'
	cc = delays[0] - delays[1]
	ec = delays[1] - delays[2]
	dts = cc, ec
	labs = 'crust-corr', 'event-ccor'
	ax = ax1
	for i in range(len(dts)):
		col = cols[i]
		dt = dts[i]
		mdt = mean(dt)
		sdt = std(dt)
		rdt = sqrt(mean(dt**2))
		print('Phase {:s} {:<12s} :  ave = {:5.1f}  std = {:5.1f}  rms = {:5.1f} s'.format(phase, labs[i], mdt, sdt, rdt))
		ax.hist(dt, bins, histtype='step', label=labs[i], lw=2, color=col)
		ax.axvline(x=mdt, color=col, ls='--', lw=3)
		ax.axvline(x=mdt-sdt, color=col, ls=':', lw=2)
		ax.axvline(x=mdt+sdt, color=col, ls=':', lw=2)
	ax.legend(loc=2)
	ax.set_xlim(-15,15)

	fignm = dfile + '.png'
	return fignm


if __name__ == '__main__':

	opts, ifiles = getParams()

	nets = 'ta', 'xa', 'xr'
	if opts.adddelay:
		ifilename = 'dtdict.pkl'
		getDictDT(nets, ifilename)

	# distribution
	# run at ~/work/na/sod/tamw60pkl/hdelays/eip/ddrel-damp
	if opts.distribution:
		getDistri()

	phase = 'S'
	binwidth = .5
	opts.xlims = [-15, 15]
		
	for phase in 'P', 'S':
		fignm = plotHist2(phase, binwidth)
		saveFigure(fignm, opts)

