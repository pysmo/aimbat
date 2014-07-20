#!/usr/bin/env python
"""
Plot crustal corrections

xlou 01/08/2013

"""

from pylab import *
import os, sys
from matplotlib.font_manager import FontProperties
from ttcommon import readStation, saveStation
from ppcommon import saveFigure
from ttdict import getParser, getDict, delayPairs, delKeys, lsq
from ttpairs import getParams, staaveDelayPairs, delayPairsHist, setAxes, histAxes


def readCFileDeprecated(ccfile):
	'read ccorr file'
	iccdict = readStation(ccfile)
	ccdict = {}
	ccdict['P'] = {}
	ccdict['S'] = {}
	for sta in sorted(iccdict):
		ccdict['P'][sta], ccdict['S'][sta] = iccdict[sta][-2:]
	return ccdict

def readDfileDeprecated(dtfiles):
	'read delay time ave/std file'
	dtdict = {}
	for dtfile in dtfiles:
		idtdict = readStation(dtfile)
		phase = dtfile.split('-')[-1].upper()
		dtd = {}
		for sta in sorted(idtdict):
			dtd[sta] = idtdict[sta][2]
		dtdict[phase] = dtd
	return dtdict


def readCFile(ccfile):
	'read P,S ccorr file'
	iccdict = readStation(ccfile)
	ccdict = {}
	for sta in sorted(iccdict):
		ccdict[sta] = iccdict[sta][3:5]
	return ccdict

def readDfile(dtfiles):
	'read P, S delay time ave/std file'
	ddicts = [ readStation(dtfile)  for dtfile in dtfiles ]
	# find common stations
	sa, sb = [ sorted(ddict)  for ddict in ddicts ]
	astas = list(set(sa).intersection(sb))
	dtdict = {}
	for sta in astas:
		dtdict[sta] = [ ddicts[0][sta][2], ddicts[1][sta][2] ]
	return dtdict

def getTimes():
	'Read P/S crustal correction and station-ave delay times'
	ccdict = readCFile(ccfile)
	dtdict = readDfile(dtfiles)
	# less station measured than given
	astas = sorted(dtdict)
	vals = array([ ccdict[sta] for sta in astas ])
	ccp, ccs = [ vals[:,i] for i in range(2) ]
	vals = array([ dtdict[sta] for sta in astas ])
	dtp, dts = [ vals[:,i] for i in range(2) ]
	return ccp, ccs, dtp, dts

def plotTimes():
	'Plot P/S crustal correction and sta-ave delay time '
	ccp, ccs, dtp, dts = getTimes()
	figure(figsize=(10, 10))
	subplots_adjust(left=.07, right=.98, bottom=.07, top=.97, wspace=.16)
	ax0 = subplot(121)
	ax1 = subplot(122, sharex=ax0, sharey=ax0)
	axs = ax0, ax1
	# P/S pair
	aa = .5
	ax = ax0
	ax.plot(ccp, ccs, 'g.', alpha=aa, label='Crustal Correction')
	ax.plot(dtp, dts, 'm.', alpha=aa, label='Sta-ave Delay Time')
	ax.set_xlabel('P [s]')
	ax.set_ylabel('S [s]')
	ax.grid()
	ax.legend(loc=2)
	# cc vs dt
	ax = ax1
	ax.plot(ccp, dtp, 'b.', alpha=aa, label='P')
	ax.plot(ccs, dts, 'r.', alpha=aa, label='S')	
	ax.set_xlabel('Crustal Correction [s]')
	ax.set_ylabel('Sta-ave Delay Time [s]')
	ax.grid()
	ax.legend(loc=2)
	#ax.axis('equal')
	xx = range(-3, 4, 1)
	yy = range(-6, 11, 1)
	ax.set_xticks(xx)
	ax.set_yticks(yy)
	ax.set_xlim(-3.5, 3.5)

	# stats
	rtp = sqrt(mean(ccp**2))
	rts = sqrt(mean(ccs**2))
	mtp = mean(ccp)	
	mts = mean(ccs)	
	stp = std(ccp)
	sts = std(ccs)
	print('** Mean, STD, and RMS of crustal P correction: {:8.3f} {:8.3f} {:8.3f}'.format(mtp, stp, rtp))	
	print('** Mean, STD, and RMS of crustal S correction: {:8.3f} {:8.3f} {:8.3f}'.format(mts, sts, rts))	
	rtp = sqrt(mean(dtp**2))
	rts = sqrt(mean(dts**2))
	mtp = mean(dtp)	
	mts = mean(dts)	
	stp = std(dtp)
	sts = std(dts)
	print('** Mean, STD, and RMS of sta-ave P delay time: {:8.3f} {:8.3f} {:8.3f}'.format(mtp, stp, rtp))	
	print('** Mean, STD, and RMS of sta-ave S delay time: {:8.3f} {:8.3f} {:8.3f}'.format(mts, sts, rts))	

	ccp /= l2norm(ccp)
	ccs /= l2norm(ccs)
	dtp /= l2norm(dtp)
	dts /= l2norm(dts)
	cc = ccp, ccs
	dd = dtp, dts
	sc = 'ccp', 'ccs'
	sd = 'dtp', 'dts'
	tt = cc, dd
	ss = sc, sd
	cols = 'gm'
	for i in range(2):
		coh = coherence(tt[i][0], tt[i][1])
		ccc = correlation(tt[i][0], tt[i][1])
		sco = 'coh({:s},{:s}) = {:4.2f}'.format(ss[i][0], ss[i][1], coh)
		scc = 'ccc({:s},{:s}) = {:4.2f}'.format(ss[i][0], ss[i][1], ccc)
		out = '{:s}, {:s}'.format(sco, scc)
		print(out)
		#text(0.02, 0.9-i*0.05, out, transform=ax0.transAxes, fontproperties=fontp,
		#	ha='left', va='center', size=12, color=cols[i])
	cols = 'br'
	for i in range(2):
		coh = coherence(cc[i], dd[i])
		ccc = correlation(cc[i], dd[i])
		sco = 'coh({:s},{:s}) = {:4.2f}'.format(sc[i], sd[i], coh)
		scc = 'ccc({:s},{:s}) = {:4.2f}'.format(sc[i], sd[i], ccc)
		out = '{:s}, {:s}'.format(sco, scc)
		print(out)
		#text(0.02, 0.9-i*0.05, out, transform=ax1.transAxes, fontproperties=fontp,
		#	ha='left', va='center', size=12, color=cols[i])
	fignm = 'sta-ccdt.png'

	return fignm

def correlation(datai, datas):
	return corrcoef(datai, datas)[0,1]

####### from aimbat
def coherence(datai, datas):
	""" 
	Calculate time domain coherence.
	Coherence is 1 - sin of the angle made by two vectors: di and ds.
	Di is data vector, and ds is the unit vector of array stack.
	res(di) = di - (di . ds) ds 
	coh(di) = 1 - res(di) / ||di||
	"""
	return 1 - l2norm(datai - dot(datai, datas)*datas)/l2norm(datai)


####### modified from ttpairs
def plotDelayPairHistEWstaave():
	'delay pairs and hist for W and E: sta-ave'
	#if absdt:
	#	tag = 'abs'
	#else:
	#	tag = 'rel'
	tag = 'ccc'
	pfile = 'sta-{:s}-p'.format(tag)
	sfile = 'sta-{:s}-s'.format(tag)
	pdict = readStation(pfile)
	sdict = readStation(sfile)
	wpair, wps = staaveDelayPairs(pdict, sdict, stawest)
	epair, eps = staaveDelayPairs(pdict, sdict, staeast)
	dpairs = wpair, epair
	xpss = wps, eps
	if opts.rmean:
		opts.axlims = [-4, 4, -12, 12]
	else:
		opts.axlims = [-3.5, 3.5, -6, 8]
		opts.axlims = [-1, 2, -2, 4]
	dx = 1
	opts.xticks = range(-1, 2+dx, dx)
	opts.yticks = range(-2, 4+dx, dx)
	# bin widths for P, S
	opts.binwidths = 0.125, 0.25
	delayPairsHist(dpairs, xpss, axs, opts)
	fignm = 'sta-' + tag + '-hist.png' 
	return fignm


if __name__ == '__main__':

	opts, ifiles = getParams()

	nullfmt = NullFormatter() # no labels
	rcParams['legend.fontsize'] = 11
	fontp = FontProperties()
	fontp.set_family('monospace')

	# plot pair of crust correction and delay time
	ccfile = 'sta-ccc-iasp91-xta'
	dtdir = 'eip-ellip'
	dtf = dtdir + '/' + 'dt-abs-'
	phases = 'P', 'S'
	dtfiles = [ dtf + phase.lower()  for phase in phases ]
	#for dtfile in dtfiles:
	#	vals = loadtxt(dtfile, usecols=(2,4))
	#	tsum = sum(vals[:,0] * vals[:,1])
	if opts.pair:
		fignm = plotTimes()
		saveFigure(fignm, opts)


	fwest = 'loc.sta.west'
	feast = 'loc.sta.east'
	opts.figtts = 'West', 'East'	
	if opts.esep:
		fwest = 'loc.sta.eastwest'
		feast = 'loc.sta.easteast'
		opts.figtts = 'EastWest', 'EastEast'	

	absdt = opts.absdt
	rmean = opts.rmean


	### delay pairs and W/E histograms

	'delay pairs and W/E histograms'
	opts.normhist = False
	opts.staave = True
	if opts.hist and not opts.physio:
		stawest = readStation(fwest)
		staeast = readStation(feast)
		if opts.stdelete is not None:
			print('Exluding stations in file: '+opts.stdelete)
			stawest = delKeys(stawest, opts.stdelete)
			staeast = delKeys(staeast, opts.stdelete)
		opts.pmarker = 'o'
		opts.pms = 7
		if opts.blackwhite:
			opts.pcol = 'w'
			opts.hpcol = 'w'
			opts.hscol = 'w'
			opts.pmew = 1.5
		else:
			opts.pcol = 'g'
			opts.hpcol = 'b'
			opts.hscol = 'r'
			opts.pmew = 1
		fig = figure(figsize=(16, 12))
		axs = histAxes(fig, opts)
		# all measurements and sta-ave
		if not opts.staave:
			fignm = plotDelayPairHistEWstaall()
		else:
			fignm = plotDelayPairHistEWstaave()
		if opts.esep:
			fignm = fignm.replace('hist', 'hist-esep')
		else:
			fignm = fignm.replace('hist', 'hist-wsep')
		setAxes(axs, opts)
		# more axes
		axps, axhp, axhs, axll = axs
		axps[0].set_xlabel('Crustal Correction for P [s]')
		axps[1].set_xlabel('Crustal Correction for P [s]')
		axps[1].set_ylabel('Crustal Correction for S [s]')

		saveFigure(fignm, opts)

