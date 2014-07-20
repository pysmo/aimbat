#!/usr/bin/env python
"""
File: ttpairs.py

Get P and S delay time pairs

xlou 03/21/2012
"""

from pylab import *
import os, sys
import matplotlib.patches as mpatches
import matplotlib.transforms as transforms
from matplotlib.ticker import NullFormatter, MultipleLocator, FormatStrFormatter
from ttdict import getParser, getDict, delayPairs, delKeys, lsq
from ttcommon import readStation, saveStation
from ppcommon import saveFigure
from pysmo.aimbat.plotutils import axLimit

def getParams():
	""" Parse arguments and options from command line. """
	parser = getParser()
	parser.add_option('-s', '--dtstation',  dest='dtstation', type='str',
		help='Read delay times for only this station.')
	parser.add_option('-n', '--dtnetwork',  dest='dtnetwork', type='str',
		help='Read delay times for a network.')
	parser.add_option('-p', '--pair', action="store_true", dest='pair',
		help='Delay pairs')
	parser.add_option('-x', '--plotxps', action="store_true", dest='plotxps',
		help='Plot single delays')
	parser.add_option('-f', '--spfit',  dest='spfit', action="store_true",
		help='Fit a line for S/P delay pairs.')
	parser.add_option('-H', '--hist', action="store_true", dest='hist',
		help='Plot histograms for west and east.')
	parser.add_option('-N', '--multinet', action="store_true", dest='multinet',
		help='Delay pairs for multiple networks')
	parser.add_option('-D', '--evstdelete', dest='evstdelete', type='str',
		help='A file containing both evid or ev.sta to delete for dtpairs.')
	parser.add_option('-M', '--staave', action="store_true", dest='staave',
		help='Plot station-average delay pairs ')
	parser.add_option('-P', '--physio', type='int', dest='physio',
		help='Plot delay pairs according to physio provinces (give 1 or 2).')
	parser.add_option('-O', '--ttpred', action="store_true", dest='ttpred',
		help='ttpred.py style of histograms on observed delay ')

	parser.add_option('-w', '--ewsep', action="store_true", dest='ewsep',
		help='ewsep')
	parser.add_option('-e', '--esep', action="store_true", dest='esep',
		help='esep')
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0 and opts.ifilename is None:
		print(parser.usage)
		sys.exit()
	return opts, files

def staaveDelayPairs(pdict, sdict, stadict):
	'Get delay pairs and single P/S delays for station-average delays'
	dpair = []
	xp, xs = [], []
	for sta in sorted(stadict.keys()):
		if sta in pdict and sta in sdict:
			tp = pdict[sta][2]
			ts = sdict[sta][2]
			dpair.append([tp, ts])
		elif sta in pdict:
			tp = pdict[sta][2]
			xp.append(tp)
		elif sta in sdict:
			ts = sdict[sta][2]
			xs.append(ts)
	dpair = array(dpair)
	xps = [ array(xp), array(xs) ]	
	return dpair, xps

def delayPairsPlot(dpair, xps, opts):
	""" Plot delay time pairs and possibly single P/S delays """
	dtp = dpair[:,0]
	dts = dpair[:,1]
	xp, xs = xps
	mtp = mean(dtp)
	mts = mean(dts)
	stp = std(dtp)
	sts = std(dts)
	print('** Mean and STD of P delay: {:8.3f} {:8.3f}'.format(mtp, stp))
	print('** Mean and STD of S delay: {:8.3f} {:8.3f}'.format(mts, sts))
	if opts.rmean:
		dtp -= mtp
		dts -= mts
		print('Remove mean delays')
	ax = gca()
	trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
	ax.text(0.7, 0.13, '$\sigma_P={:.2f}$ s'.format(stp), 
		transform=trans, va='center', ha='left', size=16)
	ax.text(0.7, 0.07, '$\sigma_S={:.2f}$ s'.format(sts), 
		transform=trans, va='center', ha='left', size=16)

	rect = mpatches.Rectangle((-2, -6), 4, 12, color='k', alpha=0.2)
	gca().add_patch(rect)
	if opts.plotxps:
		plot(zeros(len(xs)), xs, 'ro', ms=6, alpha=.3)
		plot(xp, zeros(len(xp)), 'bo', ms=6, alpha=.3)
	plot(dtp, dts, 'go', ms=7, alpha=.5)
	if opts.spfit:
		a, b, sa, sb = lsq(dtp, dts, 2)
		pp = linspace(-3,3,11)
		plot(pp, pp*a+b, 'r-', label='lsq fit: slope '+ r'$%4.2f \pm %4.2f $' % (a,sa))
		plot(pp, pp*3, 'k-', label='Slope 3')
	grid()
	axvline(x=0, ls='--')
	axhline(y=0, ls='--')
	axis('equal')
	#legend(loc=2)
	if opts.figtt is not None:
		title(opts.figtt)

def plotDelayPairs():
	"""
	# read delays for if a certain station/network is given
	# otherwise for all stations
	"""
	figure(figsize=(12,12))
	opts.figtt = None
	if osta is None and onet is None:
		dpair, xps = delayPairs(dtdict, stadict, absdt)
		delayPairsPlot(dpair, xps, opts)
		fignm = 'dtpair-' + ftag + '.png' 
	elif osta is not None:
		sdict = {}
		sdict[osta] = stadict[osta]
		opts.figtt = osta
		dpair, xps = delayPairs(dtdict, sdict, absdt)
		delayPairsPlot(dpair, xps, opts)
		fignm = 'stadt-' + osta + '.png'
	elif onet is not None:
		sdict = {}
		for sta in stadict.keys():
			if sta.split('.')[0] == onet:
				sdict[sta] = stadict[sta]
		opts.figtt = onet
		dpair, xps = delayPairs(dtdict, sdict, absdt)
		delayPairsPlot(dpair, xps, opts)
		fignm = 'stadt-' + onet + '.png'



def histAxes(fig, opts):
	'Created axes for histograms and S/P ratio'
	# width of p and s delay points
	wp, ws = 0.28, 0.75
	# histogram height
	hp, hs = 0.14, 0.14
	# space
	sp = 0.03
	# cornor points
	x0 = 0.01
	y0 = 0.05
	x1 = x0 + sp + hs
	y1 = y0 + sp + ws
	x2 = 1 - x1 - wp
	x3 = 1 - x0 - hp
	# west: hist s, s/p, hist p
	rhs0 = [x0, y0, hp, ws]
	rps0 = [x1, y0, wp, ws]
	rhp0 = [x1, y1, wp, hp]
	# east: hist s, s/p, hist p
	rhs1 = [x3, y0, hp, ws]
	rps1 = [x2, y0, wp, ws]
	rhp1 = [x2, y1, wp, hp]
	# axes:	
	#axps0 = fig.add_axes(rps0)
	axps0 = fig.add_axes(rps0, aspect='equal')
	axhp0 = fig.add_axes(rhp0, sharex=axps0)
	axhs0 = fig.add_axes(rhs0, sharey=axps0)
	#axps1 = fig.add_axes(rps1, sharex=axps0, sharey=axps0)
	axps1 = fig.add_axes(rps1, sharex=axps0, sharey=axps0, aspect='equal')
	axhp1 = fig.add_axes(rhp1, sharex=axps0)
	axhs1 = fig.add_axes(rhs1, sharey=axps0)
	axps = [axps0, axps1]
	axhp = [axhp0, axhp1]
	axhs = [axhs0, axhs1]
	# legend for physio:
	if opts.physio:
		axl0 = fig.add_axes([x0, y1, hs, hp+.02])
		axl1 = fig.add_axes([x3, y1, hs, hp+.02])
		axll = axl0, axl1
	else:
		axll = None, None
	axs = axps, axhp, axhs, axll

	return axs


def delayPairsHist(dpairs, xpss, axs, opts):
	'Plot delay time pairs and histograms for West and East'
	axps, axhp, axhs, axll = axs
	nm = opts.normhist
	# color and marker size/width for pairs and histograms
	pmarker = opts.pmarker
	pmew = opts.pmew
	pms = opts.pms
	pcol = opts.pcol
	hpcol = opts.hpcol
	hscol = opts.hscol
	np = len(dpairs)
	# plot delay pairs
	dtp, dts = [], []
	for i in range(np):
		dpair = dpairs[i]
		if dpair is None: 
			dtp.append(None)
			dts.append(None)
			continue
		tp = dpair[:,0]
		ts = dpair[:,1]
		xp, xs = xpss[i]
		if not opts.plotxps:
			ctp = tp
			cts = ts
		else:
			ctp = concatenate((tp, xp))
			cts = concatenate((ts, xs))
		mtp = mean(ctp)
		mts = mean(cts)
		stp = std(ctp)
		sts = std(cts)
		if opts.rmean:
			tp -= mtp
			ts -= mts
			xp -= mtp
			xs -= mts
			ctp -= mtp
			cts -= mts
			print('Remove mean P and S delay {:8.3f} {:8.3f} s'.format(mtp,mts))
		dtp.append(ctp)
		dts.append(cts)
		ax = axps[i]
		#ax.axhline(y=0, ls='--', color='k', lw=1.5)
		#ax.axvline(x=0, ls='--', color='k', lw=1.5)
		if opts.plotpairs:
			if opts.physio:  # no face color 
				ax.plot(tp, ts, color='None', marker=pmarker, ls='None', ms=pms, mew=pmew, mec=pcol, alpha=opts.alpha)
			else:
				ax.plot(tp, ts, color=pcol, marker=pmarker, ls='None', ms=pms, mew=pmew)
			if opts.plotxps:
				ax.plot(zeros(len(xs)), xs, 'ro', ms=5, alpha=.3)
				ax.plot(xp, zeros(len(xp)), 'bo', ms=5, alpha=.3)
		#print('P: ave={:f} std={:f} '.format(mtp,stp), opts.figtts[i])
		#print('S: ave={:f} std={:f} '.format(mts,sts), opts.figtts[i])
		#if not opts.physio or opts.physio == 2:
		if opts.textavstd:
			trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
			ax.text(0.6, 0.18, '$\mu_P={:.1f}$ s'.format(mtp), 
				transform=trans, va='center', ha='left', size=20)
			ax.text(0.6, 0.14, '$\mu_S={:.1f}$ s'.format(mts), 
				transform=trans, va='center', ha='left', size=20)
			ax.text(0.6, 0.09, '$\sigma_P={:.1f}$ s'.format(stp), 
				transform=trans, va='center', ha='left', size=20)
			ax.text(0.6, 0.05, '$\sigma_S={:.1f}$ s'.format(sts), 
				transform=trans, va='center', ha='left', size=20)
		# dash line for mean P/S delays
		axhp[i].axvline(x=mtp, color=pcol, ls='--', lw=2)
		axhs[i].axhline(y=mts, color=pcol, ls='--', lw=2)
		if len(dpair) > 3 and opts.spfit:
			a, b, sa, sb = lsq(tp, ts, 2)
			pp = linspace(-3,3,11)
			ax.plot(pp, pp*a+b, color=pcol, ls='-', label='lsq fit: slope '+ r'$%4.2f \pm %4.2f $' % (a,sa))

	# plot histograms, hist bins and axis limit
	if opts.axlims is None:
		#ax.axis('equal')
		xxlim = ax.get_xlim()
		yylim = ax.get_ylim()
	else:
		xxlim = opts.axlims[:2]
		yylim = opts.axlims[2:]
		axps[i].axis(opts.axlims)
	### bin width: 0.25 s for P wave and 0.5 s for S wave.
	binwp, binws = opts.binwidths
	binp = linspace(xxlim[0], xxlim[1], (xxlim[1]-xxlim[0])/binwp+1)
	bins = linspace(yylim[0], yylim[1], (yylim[1]-yylim[0])/binws+1)
	if opts.physio:
		fcs = 'None', 'None'
		ec = pcol
		htype = 'step'
		alpha = 1
		if opts.textavstd:
			fcs = 'k', 'k'
			htype = 'bar'
			alpha = .25
	else:
		fcs = hpcol, hscol
		ec = 'k'
		htype = 'bar'
		alpha = 1
	for i in range(np):
		if dtp[i] is not None:
			hp = axhp[i].hist(dtp[i], binp, histtype=htype, fc=fcs[0], ec=ec, normed=nm, lw=2, alpha=alpha)
			hs = axhs[i].hist(dts[i], bins, histtype=htype, fc=fcs[1], ec=ec, normed=nm, lw=2, alpha=alpha,orientation='horizontal')

def setAxes(axs, opts):
	nullfmt = NullFormatter() # no labels
	axps, axhp, axhs, axll = axs
	for i in range(2):
		axhp[i].set_title(opts.figtts[i])
		axhp[i].yaxis.set_major_formatter(nullfmt)
		axhs[i].xaxis.set_major_formatter(nullfmt)
		axhp[i].set_ylabel('P Histogram')
		axhs[i].set_xlabel('S Histogram')
		axhp[i].grid()
		axhs[i].grid()
		axps[i].grid()
	if opts.absdt:
		axps[0].set_xlabel('Absolute P Delay Time [s]')
		axps[1].set_xlabel('Absolute P Delay Time [s]')
		axps[1].set_ylabel('Absolute S Delay Time [s]')
	else:
		axps[0].set_ylabel('Relative P Delay Time [s]')
		axps[1].set_ylabel('Relative P Delay Time [s]')
		axps[1].set_ylabel('Relative S Delay Time [s]')
	axhs[0].set_xlim(axhs[0].get_xlim()[::-1])
	axps[0].yaxis.set_label_position('right')
	axhs[0].xaxis.set_label_position('top')
	axhs[1].xaxis.set_label_position('top')
	axps[0].yaxis.set_ticks_position('right')
	axhs[0].yaxis.set_ticks_position('right')
	axps[0].set_xticks(opts.xticks)
	axps[0].set_yticks(opts.yticks)
	# make legend
	if opts.physio:
		axll = axs[3]
		weprovs = wprovs, eprovs
		for j in range(2):
			ax = axll[j]
			provs = weprovs[j]
			n = len(provs)
			for i in range(n):
				ax.plot(0.04, -i, color='None', marker=opts.pmarker, mec=pidict[provs[i]][2], 
					ms=opts.pms, mew=opts.pmew, ls='None', alpha=1)
					#ms=opts.pms, mew=opts.pmew, ls='None', alpha=opts.alpha)
				ax.text(0.08, -i, pidict[provs[i]][1], va='center', ha='left', size=14)
				ax.axis([0,1,0.5-n,0.5])
			ax.yaxis.set_major_formatter(nullfmt)
			ax.xaxis.set_major_formatter(nullfmt)
			ax.set_xticks([])
			ax.set_yticks([])

def delEvsta(dtdict, evstdelete):
	print ('Delete ev a/o evsta from dtdict using file: '+evstdelete)
	dfile = open(evstdelete)
	lines = dfile.readlines()
	dfile.close()
	for line in lines:
		sline = line.split()
		if sline != [] and line[0] != '#':
			ev, sta = sline[1:3]
			if ev in dtdict.keys():
				if sta == '*':
					del dtdict[ev]
					print('Delete event: {:s}'.format(ev))
				else:
					del dtdict[ev]['P'][0][sta]	
					del dtdict[ev]['S'][0][sta]	
					print('Delete evsta: {:s} {:s}'.format(ev, sta))


############################## only one panel of delayPairHist (not W-E) ########################
def histAxes1(fig, weststyle=False):
	'Created axes for histograms and S/P ratio. For only 1 set (east style)'
	# width of p and s delay points
	wp, ws = 0.54, 0.74
	# histogram height
	hp, hs = 0.14, 0.28
	# space
	sp = 0.06
	# corner points
	y0 = 0.05
	x2 = 0.09
	x3 = x2 + sp + wp
	y1 = y0 + .03 + ws
	# east: hist s, s/p, hist p
	rhs1 = [x3, y0, hs, ws]
	rps1 = [x2, y0, wp, ws]
	rhp1 = [x2, y1, wp, hp]
	if opts.physio == 2:
		rpp1 = [x3, y1, hs, hp+.02]
	else:
		rpp1 = [x3, y1, hs, hp]
	# west: hist s, s/p, hist p
	x0 = 0.03
	x1 = x0 + sp + hs
	rhs0 = [x0, y0, hs, ws]
	rps0 = [x1, y0, wp, ws]
	rhp0 = [x1, y1, wp, hp]
	if opts.physio == 2:
		rpp0 = [x0, y1, hs, hp+.02]
	else:
		rpp0 = [x0, y1, hs, hp]
	if weststyle:
		axps = fig.add_axes(rps0, aspect='equal')
		axhp = fig.add_axes(rhp0, sharex=axps)
		axhs = fig.add_axes(rhs0, sharey=axps) 
		axll = fig.add_axes(rpp0)
	else:
		axps = fig.add_axes(rps1, aspect='equal')
		axhp = fig.add_axes(rhp1, sharex=axps)
		axhs = fig.add_axes(rhs1, sharey=axps) 
		axll = fig.add_axes(rpp1)
	axs = axps, axhp, axhs, axll
	return axs


def delayPairsHist1(dpair, xps, axs, opts):
	'Plot delay time pairs and histograms for only W or E'
	axps, axhp, axhs, axll = axs
	nm = opts.normhist
	# color and marker size/width for pairs and histograms
	pmarker = opts.pmarker
	pmew = opts.pmew
	pms = opts.pms
	pcol = opts.pcol
	hpcol = opts.hpcol
	hscol = opts.hscol
	# plot delay pairs
	tp = dpair[:,0]
	ts = dpair[:,1]
	xp, xs = xps
	if not opts.plotxps:
		ctp = tp
		cts = ts
	else:
		ctp = concatenate((tp, xp))
		cts = concatenate((ts, xs))
	mtp = mean(ctp)
	mts = mean(cts)
	stp = std(ctp)
	sts = std(cts)
	rtp = sqrt(mean(ctp**2))
	rts = sqrt(mean(cts**2))
	if rmean:
		tp -= mtp
		ts -= mts
		xp -= mtp
		xs -= mts
		ctp -= mtp
		cts -= mts
		print('Remove mean P and S delay {:8.3f} {:8.3f} s'.format(mtp,mts))
	ax = axps
	#ax.axhline(y=0, ls='--', color='k', lw=2)
	#ax.axvline(x=0, ls='--', color='k', lw=2)
	if opts.physio:  # no face color 
		ax.plot(tp, ts, color='None', marker=pmarker, ls='None', ms=pms, mew=pmew, mec=pcol, alpha=opts.alpha)
	else:
		ax.plot(tp, ts, color=pcol, marker=pmarker, ls='None', ms=pms, mew=pmew)
	if opts.plotxps:
		ax.plot(zeros(len(xs)), xs, 'ro', ms=5, alpha=.3)
		ax.plot(xp, zeros(len(xp)), 'bo', ms=5, alpha=.3)
	print('P: ave/std/rms= {:7.3f} {:7.3f} {:7.3f}'.format(mtp, stp, rtp))
	print('S: ave/std/rms= {:7.3f} {:7.3f} {:7.3f}'.format(mts, sts, rts))
	if not opts.physio:
		trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
		ax.text(0.6, 0.18, '$\mu_P={:.1f}$ s'.format(mtp), 
			transform=trans, va='center', ha='left', size=20)
		ax.text(0.6, 0.14, '$\mu_S={:.1f}$ s'.format(mts), 
			transform=trans, va='center', ha='left', size=20)
		ax.text(0.6, 0.09, '$\sigma_P={:.1f}$ s'.format(stp), 
			transform=trans, va='center', ha='left', size=20)
		ax.text(0.6, 0.05, '$\sigma_S={:.1f}$ s'.format(sts), 
			transform=trans, va='center', ha='left', size=20)
	else:
		transp = transforms.blended_transform_factory(axhp.transAxes, axhp.transAxes)
		transs = transforms.blended_transform_factory(axhs.transAxes, axhs.transAxes)
		if weststyle:
			axhp.text(0.05, 0.86-opts.count*0.2, '$\sigma_P={:.2f}$ s'.format(stp), 
				transform=transp, va='center', ha='left', size=20, color=pcol)
			axhs.text(0.10, 0.96-opts.count*0.04, '$\sigma_S={:.2f}$ s'.format(sts), 
				transform=transs, va='center', ha='left', size=20, color=pcol)
		else:
			axhp.text(0.95, 0.86-opts.count*0.2, '$\sigma_P={:.2f}$ s'.format(stp), 
				transform=transp, va='center', ha='right', size=20, color=pcol)
			axhs.text(0.90, 0.96-opts.count*0.04, '$\sigma_S={:.2f}$ s'.format(sts), 
				transform=transs, va='center', ha='right', size=20, color=pcol)

	# dash line for mean P/S delays
	axhp.axvline(x=mtp, color=pcol, ls='--', lw=3)
	axhp.axvline(x=mtp-stp, color=pcol, ls=':', lw=2)
	axhp.axvline(x=mtp+stp, color=pcol, ls=':', lw=2)
	axhs.axhline(y=mts, color=pcol, ls='--', lw=3)
	axhs.axhline(y=mts-sts, color=pcol, ls=':', lw=2)
	axhs.axhline(y=mts+sts, color=pcol, ls=':', lw=2)
	if len(dpair) > 3 and opts.spfit:
		a, b, sa, sb = lsq(tp, ts, 2)
		pp = linspace(-3,3,11)
		ax.plot(pp, pp*a+b, color=pcol, ls='-', label='lsq fit: slope '+ r'$%4.2f \pm %4.2f $' % (a,sa))
	# plot histograms, hist bins and axis limit
	if opts.axlims is None:
		#ax.axis('equal')
		xxlim = ax.get_xlim()
		yylim = ax.get_ylim()
	else:
		xxlim = opts.axlims[:2]
		yylim = opts.axlims[2:]
		axps.axis(opts.axlims)
	binwp, binws = opts.binwidths
	binp = linspace(xxlim[0], xxlim[1], (xxlim[1]-xxlim[0])/binwp+1)
	bins = linspace(yylim[0], yylim[1], (yylim[1]-yylim[0])/binws+1)
	if opts.physio:
		fcs = 'None', 'None'
		ec = pcol
		htype = 'step'
	else:
		fcs = hpcol, hscol
		ec = 'k'
		htype = 'bar'
	hp = axhp.hist(ctp, binp, histtype=htype, fc=fcs[0], ec=ec, normed=nm, lw=2)
	hs = axhs.hist(cts, bins, histtype=htype, fc=fcs[1], ec=ec, normed=nm, lw=2, orientation='horizontal')
	atps = (mtp, stp, rtp), (mts, sts, rts)
	return atps

def setAxes1(axs, opts, provs, weststyle=False):
	axps, axhp, axhs, axll = axs
	axhp.set_title(opts.figtt)
	axhp.yaxis.set_major_formatter(nullfmt)
	axhs.xaxis.set_major_formatter(nullfmt)
	axhp.set_ylabel('P Histogram')
	axhs.set_xlabel('S Histogram')
	#axhp.grid()
	#axhs.grid()
	axps.grid()
	#print axhp.get_ylim()
	#print axhs.get_xlim()
	if opts.absdt:
		axps.set_xlabel('Absolute P Delay Time [s]')
		axps.set_ylabel('Absolute S Delay Time [s]')
	else:
		axps.set_xlabel('Relative P Delay Time [s]')
		axps.set_ylabel('Relative S Delay Time [s]')
	axps.set_xticks(opts.xticks)
	axps.set_yticks(opts.yticks)
	axhs.xaxis.set_label_position('top')
	if weststyle:
		axps.yaxis.set_label_position('right')
		axps.yaxis.set_ticks_position('right')
		axhs.yaxis.set_ticks_position('right')
		axhs.set_xlim(axhs.get_xlim()[::-1])
	# make legend
	if opts.physio:
		ax = axll
		n = len(provs)
		for i in range(n):
			ax.plot(0.04, -i, color='None', marker=opts.pmarker, mec=pidict[provs[i]][2], 
				ms=opts.pms, mew=opts.pmew, ls='None', alpha=1)
				#ms=opts.pms, mew=opts.pmew, ls='None', alpha=opts.alpha)
			ax.text(0.08, -i, pidict[provs[i]][1], va='center', ha='left', size=14)
			ax.axis([0,1,0.5-n,0.5])
		ax.yaxis.set_major_formatter(nullfmt)
		ax.xaxis.set_major_formatter(nullfmt)
		ax.set_xticks([])
		ax.set_yticks([])
	# label fig number
	if opts.lab is not None:
		lab = '(' + opts.lab + ')'
		if weststyle:
			trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
			ax.text(-0.06, 1.03, lab, transform=trans, va='bottom', ha='left', size=20, fontweight='bold')
		else: 
			trans = transforms.blended_transform_factory(axhp.transAxes, axhp.transAxes)
			axhp.text(-0.13, 1.03, lab, transform=trans, va='bottom', ha='left', size=20, fontweight='bold')

##################################### main plotting programs ###################################
def plotDelayPairHistEWstaall():
	'delay pairs and hist for W and E: all measurements'
	wpair, wps = delayPairs(dtdict, stawest, absdt)
	epair, eps = delayPairs(dtdict, staeast, absdt)
	dpairs = wpair, epair
	xpss = wps, eps
	if opts.rmean:
		opts.axlims = [-4, 4, -12, 12]
	else:
		opts.axlims = [-7, 7, -12, 16]
	#opts.axlims = None
	dx = 1
	opts.xticks = range(-6,  6+dx, dx)
	opts.yticks = range(-12, 16+dx, dx)
	# for event-corrected
	if opts.ifilename == 'erdtdict.pkl':
		opts.axlims = [-5, 5, -8, 12]
		opts.xticks = range(-5,  5+dx, dx)
		opts.yticks = range(-8, 12+dx, dx)
	# bin widths for P, S
	opts.binwidths = 0.25, 0.5
	delayPairsHist(dpairs, xpss, axs, opts)
	if opts.plotxps:
		fignm = 'dtpxps-hist-staall-' + ftag + '.png' 
	else:
		fignm = 'dtpair-hist-staall-' + ftag + '.png' 
	return fignm

def plotDelayPairHistEWstaave():
	'delay pairs and hist for W and E: sta-ave'
	if absdt:
		tag = 'abs'
	else:
		tag = 'rel'
	pfile = 'dt-{:s}-p'.format(tag)
	sfile = 'dt-{:s}-s'.format(tag)
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
	dx = 1
	opts.xticks = range(-3, 3+dx, dx)
	opts.yticks = range(-6, 8+dx, dx)
	# bin widths for P, S
	opts.binwidths = 0.25, 0.5
	delayPairsHist(dpairs, xpss, axs, opts)
	if opts.plotxps:
		fignm = 'dtpxps-hist-staave-' + tag + '.png' 
	else:
		fignm = 'dtpair-hist-staave-' + tag + '.png' 
	return fignm


def plotDelayPairHistPhysioEWstaave():
	'delay pairs and hist for W and E for each physio province: sta-ave'
	provs = wprovs + eprovs
	if opts.rmean:
		opts.axlims = [-4, 4, -12, 12]
	else:
		opts.axlims = [-3.5, 3.5, -6, 8]
	dx = 1
	opts.xticks = range(-3, 3+dx, dx)
	opts.yticks = range(-6, 8+dx, dx)
	# bin widths for P, S
	opts.binwidths = 0.125, 0.25
	if opts.ifilename == 'erdtdict.pkl':
		opts.axlims = [-3.25, 3.25, -4.5, 8.5]
		opts.xticks = range(-3,  3+dx, dx)
		opts.yticks = range(-4, 8+dx, dx)
	opts.pmarker = 'o'
	opts.pms = 4
	opts.pmew = 2
	opts.alpha = 0.7
	if absdt:
		tag = 'abs'
	else:
		tag = 'rel'
	pfile = 'dt-{:s}-p'.format(tag)
	sfile = 'dt-{:s}-s'.format(tag)
	pdict = readStation(pfile)
	sdict = readStation(sfile)
	for i in range(len(provs)):
		prov = provs[i]
		pcol = pidict[prov][2]
		stad = readStation(stadir+prov)
		if opts.stdelete is not None:
			print('Exluding stations in file: '+opts.stdelete)
			stad = delKeys(stad, opts.stdelete)
		pair, xps =staaveDelayPairs(pdict, sdict, stad)
		if i < len(wprovs):
			dpairs = pair, None
			xpss = xps, None
		else:
			dpairs = None, pair
			xpss = None, xps
		opts.pcol = pcol
		opts.hpcol = pcol
		opts.hscol = pcol
		delayPairsHist(dpairs, xpss, axs, opts)
	if opts.plotxps:
		fignm = 'dtpxps-physio-staave-' + tag + '.png' 
	else:
		fignm = 'dtpair-physio-staave-' + tag + '.png' 
	return fignm

def plotDelayPairHistPhysioEWstaall():
	'delay pairs and hist for W and E for each physio province: all measurements'
	provs = wprovs + eprovs
	if opts.rmean:
		opts.axlims = [-4, 4, -12, 12]
	else:
		opts.axlims = [-7, 7, -12, 16]
	dx = 1
	opts.xticks = range(-6,  6+dx, dx)
	opts.yticks = range(-12, 16+dx, dx)
	# for event-corrected
	if opts.ifilename == 'erdtdict.pkl':
		opts.axlims = [-5, 5, -8, 12]
		opts.xticks = range(-5,  5+dx, dx)
		opts.yticks = range(-8, 12+dx, dx)
	# bin widths for P, S
	opts.binwidths = 0.25, 0.5
	opts.pmarker = 'o'
	opts.pms = 4     # 3
	opts.pmew = 2    # 1
	opts.alpha = 0.8 # 0.7
	awpairs, aepairs = [], []
	#awxpss,  aexpss  = [], []
	for ax in axs[0]: # zero lines
		ax.axhline(y=0, ls='--', color='k', lw=1.5)
		ax.axvline(x=0, ls='--', color='k', lw=1.5)
	for i in range(len(provs)):
		prov = provs[i]
		pcol = pidict[prov][2]
		stad = readStation(stadir+prov)
		if opts.stdelete is not None:
			print('Exluding stations in file: '+opts.stdelete)
			stad = delKeys(stad, opts.stdelete)
		pair, xps = delayPairs(dtdict, stad, absdt)
		if i < len(wprovs):
			dpairs = pair, None
			xpss = xps, None
			if awpairs == []:
				awpairs = pair
			else:
				awpairs = concatenate((awpairs, pair))
		else:
			dpairs = None, pair
			xpss = None, xps
			if aepairs == []:
				aepairs = pair
			else:
				aepairs = concatenate((aepairs, pair))
		opts.pcol = pcol
		opts.hpcol = pcol
		opts.hscol = pcol
		delayPairsHist(dpairs, xpss, axs, opts)
	# all
	opts.pcol = 'k'
	opts.hpcol = 'k'
	opts.hscol = 'k'
	apairs = awpairs, aepairs
	axpss = (None, None), (None, None)
	opts.textavstd = True
	opts.plotpairs = False
	delayPairsHist(apairs, axpss, axs, opts)

	if opts.plotxps:
		fignm = 'dtpxps-physio-staall-' + ftag + '.png' 
	else:
		fignm = 'dtpair-physio-staall-' + ftag + '.png' 
	return fignm


def plotDelayPairHistPhysioStaave():
	'for each physio province on one panel: sta-ave'
	x0, x1, y0, y1 = opts.axlims
	dx = 1
	opts.xticks = range(int(x0), int(x1)+dx, dx)
	opts.yticks = range(int(y0), int(y1)+dx, dx)
	opts.pmarker = 'o'
	opts.pms = 4
	opts.pmew = 2
	opts.alpha = 0.9
	# bin widths for P, S
	opts.binwidths = 0.125, 0.25
	if absdt:
		tag = 'abs'
	else:
		tag = 'rel'
	pfile = 'dt-{:s}-p'.format(tag)
	sfile = 'dt-{:s}-s'.format(tag)
	pdict = readStation(pfile)
	sdict = readStation(sfile)
	for i in range(len(provs)):
		prov = provs[i]
		pcol = pidict[prov][2]
		stad = readStation(stadir+prov)
		if opts.stdelete is not None:
			print('Exluding stations in file: '+opts.stdelete)
			stad = delKeys(stad, opts.stdelete)
		pair, xps =staaveDelayPairs(pdict, sdict, stad)
		opts.pcol = pcol
		opts.hpcol = pcol
		opts.hscol = pcol
		opts.count = i # counting number of provs
		delayPairsHist1(pair, xps, axs, opts)
	if opts.plotxps:
		fignm = 'dtpxps-physio-staave-' + tag + '.png' 
	else:
		fignm = 'dtpair-physio-staave-' + tag + '.png' 
	return fignm

def plotDelayPairHistPhysioStaall():
	'for each physio province on one panel: all measurements'
	x0, x1, y0, y1 = opts.axlims
	dx = 1
	opts.xticks = range(int(x0), int(x1)+dx, dx)
	opts.yticks = range(int(y0), int(y1)+dx, dx)
	opts.pmarker = 'o'
	opts.pms = 5 #2
	opts.pmew = 2 #1
	opts.alpha = 0.7 #0.7
	# bin widths for P, S
	opts.binwidths = 0.25, 0.5
	ax = axs[0]
	ax.axhline(y=0, ls='--', color='k', lw=2)
	ax.axvline(x=0, ls='--', color='k', lw=2)
	atp, ats = [], []
	for i in range(len(provs)):
		prov = provs[i]
		pcol = pidict[prov][2]
		stad = readStation(stadir+prov)
		if opts.stdelete is not None:
			print('Exluding stations in file: '+opts.stdelete)
			stad = delKeys(stad, opts.stdelete)
		pair, xps = delayPairs(dtdict, stad, absdt)
		opts.pcol = pcol
		opts.hpcol = pcol
		opts.hscol = pcol
		opts.count = i # counting number of provs
		tp, ts = delayPairsHist1(pair, xps, axs, opts)
		atp.append(tp)
		ats.append(ts)

	if opts.plotxps:
		fignm = 'dtpxps-physio-staall-' + ftag + '.png' 
	else:
		fignm = 'dtpair-physio-staall-' + ftag + '.png' 
	return fignm, atp, ats




def histPred(phase, wpair, epair, binwidth):
	'Plot delay hist in ttpred.py style for different depths'
	if phase == 'P':
		ip = 0
	else:
		ip = 1
	dtw = list(wpair[:,ip]) #+ list(wps[ip])
	dte = list(epair[:,ip]) #+ list(eps[ip])
	dta = dtw, dte
	fig = figure(figsize=(8, 6))
	subplots_adjust(left=.1, right=.96, bottom=.09, top=0.95, hspace=.11, wspace=.16)
	ax = fig.add_subplot(111)
#	rcParams['legend.fontsize'] = 13
	if phase == 'P':
		binwidth *= 0.5
	#ainds = range(len(dinds))
	bins1 = linspace(-10, 10, 20/binwidth+1)	
	bins2 = linspace(-20, 20, 40/binwidth/2+1)	
	bins = bins2
	cols = 'rb'
	ewlegs = 'West', 'East'
	ewys = 0.97, 0.87
	trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
	for k in range(2): # E/W
		dt = dta[k]
		ew = ewlegs[k]
		col = cols[k]
		ax.hist(dt, bins, color=col, alpha=.9, histtype='step', label=ew, lw=2)
		mdt, sdt = mean(dt), std(dt)
		x0, x1 = mdt-sdt, mdt+sdt
		ax.axvline(x=mdt, color=col, ls='--', lw=2)
		ax.axvline(x=mdt-sdt, color=col, ls=':', lw=2)
		ax.axvline(x=mdt+sdt, color=col, ls=':', lw=2)
		ax.text(0.97, ewys[k], r'$\sigma_{:s}$={:.2f} s'.format(ew[0], sdt), 
			transform=trans, ha='right', va='top', size=14)
#	ax.text(0.02, 0.70, depths[dtag], transform=trans, ha='left',va='center',size=14)
#	# label model using dir basename
	ax.text(0.02, 0.77, 'Observed {:s}'.format(phase), transform=trans, ha='left',va='center',size=14)
	#ax.set_title(depths[dtag])
	ax.legend(loc=2)
	alim = opts.axlims[0]
	if phase == 'P':
		alim = array(alim)*0.5
	ax.set_xlim(alim)
	yy = ax.get_ylim()
	yy = axLimit(yy, 0.05)
	ax.set_ylim(yy)
	ax.axhline(y=0, color='k', ls=':')
	ax.xaxis.set_major_locator(opts.majorLocator)
	ax.xaxis.set_minor_locator(opts.minorLocator)
	ax.set_ylabel('Histogram')
	ax.set_xlabel('Observed {:s} S Delay Time [s]'.format(opts.atag))
	fignm = 'odt-ewhist-{:s}.png'.format(phase.lower())
	return fignm



if __name__ == '__main__':

	opts, ifiles = getParams()

	# get dtdict for single or multiple networks
	# only when plotting all individual measurements and not sta-ave
	if not opts.staave:
		if not opts.multinet:
			stadict = readStation(opts.locsta)
			dtdict = getDict(opts, ifiles)
		else:
			nets = 'ta', 'xa', 'xr'
			ifileback = opts.ifilename
			xdicts = []
			ddicts = []
			dtdict = {}
			stadict = {}
			for net in nets:
				locsta = opts.locsta + '.' + net
				opts.ifilename = net + '-' + ifileback
				xdict = readStation(locsta)
				ddict = getDict(opts, ifiles)
				xdicts.append(xdict)
				ddicts.append(ddict)
				for evid in ddict.keys():
					dtdict[evid] = ddict[evid]
				for sta in xdict.keys():
					stadict[sta] = xdict[sta]
		# delete event/station given in files 
		if opts.evdelete is not None:
			print('Exluding events in file: '+opts.evdelete)
			dtdict = delKeys(dtdict, opts.evdelete)
		if opts.evabsdelete is not None:
			print('Exluding events in file: '+opts.evabsdelete)
			dtdict = delKeys(dtdict, opts.evabsdelete)
		if opts.stdelete is not None:
			print('Exluding stations in file: '+opts.stdelete)
			stadict = delKeys(stadict, opts.stdelete)
		evstdelete = opts.evstdelete
		if evstdelete is not None:
			delEvsta(dtdict, evstdelete)

	absdt = opts.absdt
	rmean = opts.rmean

	nullfmt = NullFormatter() # no labels
	rcParams['legend.fontsize'] = 10
	rcParams['axes.labelsize'] = 'large'
	rcParams['xtick.major.size'] = 6
	rcParams['xtick.minor.size'] = 4
	rcParams['xtick.labelsize'] = 'large'
	rcParams['ytick.major.size'] = 6
	rcParams['ytick.minor.size'] = 4
	rcParams['ytick.labelsize'] = 'large'
	rcParams['axes.titlesize'] = 'x-large'
	osta = opts.dtstation
	onet = opts.dtnetwork

	if opts.rmean:
		ftag = 'm'
	else:
		ftag = ''
	if opts.absdt:
		ftag += 'abs'
		opts.atag = 'Absolute'
	else:
		ftag += 'rel'
		opts.atag = 'Relative'
	#if opts.evdelete or opts.evabsdelete or opts.stdelete or opts.evstdelete:
	#	ftag += '-selected'

	fwest = 'loc.sta.west'
	feast = 'loc.sta.east'
	opts.figtts = 'West', 'East'	
	opts.figtts = 'RMW', 'RME'
	if opts.esep:
		fwest = 'loc.sta.eastwest'
		feast = 'loc.sta.easteast'
		opts.figtts = 'EastWest', 'EastEast'	
		opts.figtts = 'RMEwest', 'RMEeast'	

	opts.plotpairs = True
	opts.textavstd = True
	### delay pairs
	if opts.pair:
		plotDelayPairs()

	### delay pairs and W/E histograms
	opts.normhist = False
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


	### dtpairs for physio provinces
	# physio inds, names, and plotting colors 
	pidict = {}
	# divisions
	pidict['super'] = [ range(1,2),   'Superior Upland',         'Cyan', ]
	pidict['coast'] = [ range(3,4),   'Coastal Plain',           'Orange', ]
	pidict['appal'] = [ range(4,11),  'Appalachian Highl.',   'Red',] #    'Sienna' 
	pidict['intpl'] = [ range(11,14), 'Interior Plains',         'Blue', ]
	pidict['inthl'] = [ range(14,16), 'Interior Highl.',      'Orchid', ]
	pidict['rocky'] = [ range(16,20), 'Rocky Mountain System',   'Brown', ]
	pidict['intmt'] = [ range(20,23), 'InterMontane Plateaus',   'YellowGreen', ]
	pidict['pacmt'] = [ range(23,26), 'Pacific Mountain System', 'DarkGreen', ]
	# provinces
	#intpl:
	pidict['ilp'] = [ [11,], 'Interior Low Plateaus', 'LightBlue', ]
	pidict['cel'] = [ [12,], 'Central Lowland',       'DarkCyan', ]
	pidict['grp'] = [ [13,], 'Great Plains',          'Blue', ]
	#intmt:
	pidict['cbp'] = [ [20,], 'Columbia Plateau',      'YellowGreen', ]
	pidict['cop'] = [ [21,], 'Colorado Plateau',      'Salmon', ]
	pidict['bar'] = [ [22,], 'Basin and Range',       'Olive', ]
	#rocky:	
	pidict['srm'] = [ [16,], 'Southern Rocky Mts.', 'Plum', ]
	pidict['wyb'] = [ [17,], 'Wyoming Basin',            'Peru', ]
	pidict['mrm'] = [ [18,], 'Middle Rocky Mts.',   'DarkOrchid', ]
	pidict['nrm'] = [ [19,], 'Northern Rocky Mts.', 'Brown', ]
	#pacmt:
	pidict['csm'] = [ [23,], 'Cascade-Sierra Mts.', 'DarkGreen', ]
	pidict['pbp'] = [ [24,], 'Pacific Border Prov.',  'LightGreen', ]

#	pidict['super'] = [ range(1,2),   'Superior Upland',         'Cyan', ]
#	pidict['coast'] = [ range(3,4),   'Coastal Plain',           'Orange', ]
#	pidict['appal'] = [ range(4,11),  'Appalachian Highlands',   'Red',] #    'Sienna' 
#	pidict['intpl'] = [ range(11,14), 'Interior Plains',         'Blue', ]
#	pidict['inthl'] = [ range(14,16), 'Interior Highlands',      'Orchid', ]
#	pidict['rocky'] = [ range(16,20), 'Rocky Mountain System',   'Brown', ]
#	pidict['intmt'] = [ range(20,23), 'InterMontane Plateaus',   'YellowGreen', ]
#	pidict['pacmt'] = [ range(23,26), 'Pacific Mountain System', 'DarkGreen', ]
#	# provinces
#	#intpl:
#	pidict['ilp'] = [ [11,], 'Interior Low Plateaus', 'LightBlue', ]
#	pidict['cel'] = [ [12,], 'Central Lowland',       'DarkCyan', ]
#	pidict['grp'] = [ [13,], 'Great Plains',          'Blue', ]
#	#intmt:
#	pidict['cbp'] = [ [20,], 'Columbia Plateau',      'YellowGreen', ]
#	pidict['cop'] = [ [21,], 'Colorado Plateau',      'Salmon', ]
#	pidict['bar'] = [ [22,], 'Basin and Range',       'Olive', ]
#	#rocky:	
#	pidict['srm'] = [ [16,], 'Southern Rocky Mountains', 'Plum', ]
#	pidict['wyb'] = [ [17,], 'Wyoming Basin',            'Peru', ]
#	pidict['mrm'] = [ [18,], 'Middle Rocky Mountains',   'DarkOrchid', ]
#	pidict['nrm'] = [ [19,], 'Northern Rocky Mountains', 'Brown', ]
#	#pacmt:
#	pidict['csm'] = [ [23,], 'Cascade-Sierra Mountains', 'DarkGreen', ]
#	pidict['pbp'] = [ [24,], 'Pacific Border Province',  'LightGreen', ]
#

	stadir = os.environ['HOME'] + '/work/na/sod/tamw60pkl/evsta/loc.sta-'
	stafile = 'loc.sta'

	if opts.physio == 1:
		wprovs = 'pacmt', 'intmt', 'rocky'
		eprovs = 'super', 'intpl', 'inthl', 'appal', 'coast'
	elif opts.physio == 2:
		wprovs = 'pbp', 'csm', 'cbp', 'cop', 'bar', 'nrm', 'mrm', 'wyb', 'srm'
		eprovs = 'super', 'grp', 'cel', 'ilp', 'inthl', 'appal', 'coast', 
	elif opts.physio == 3:
		pvdict = {}
		pvdict['a'] = 'pbp', 'csm',
		pvdict['b'] = 'cbp', 'cop', 'bar',
		pvdict['c'] = 'nrm', 'mrm', 'wyb', 'srm',
 		pvdict['d'] = 'grp', 'cel', 'ilp',
		pvdict['e'] = 'super', 'inthl',  
		pvdict['f'] = 'appal', 'coast',


	opts.normhist = False
	#opts.normhist = True
	opts.lab = None
	if opts.physio:
		opts.textavstd = False
		opts.plotpairs = True
		if opts.physio <= 2:
			fig = figure(figsize=(16, 12))
			axs = histAxes(fig, opts)
			# all measurements and sta-ave
			if opts.staave:
				fignm = plotDelayPairHistPhysioEWstaave()
			else:
				fignm = plotDelayPairHistPhysioEWstaall()
			fignm = fignm.replace('physio', 'physio{:d}'.format(opts.physio))
			setAxes(axs, opts)
		elif opts.physio == 3:
			labs = 'abcdef'
			#labs = 'abcabc'
			pvs = sorted(pvdict.keys())
			aatp, aats = [], []
			for i in range(len(pvs)):
				pv = pvs[i]
				provs = pvdict[pv]
				if i < 3:
					opts.figtt = 'West'
					opts.figtt = 'RMW'
					weststyle = True
				else:
					opts.figtt = 'East'
					opts.figtt = 'RME'
					weststyle = False
				opts.lab = labs[i]
				#opts.lab = None
				fig = figure(figsize=(8, 12))
				axs = histAxes1(fig, weststyle)
				# all measurements and sta-ave
				if opts.staave:
					opts.axlims = [-3.5, 3.5, -6, 8]
					if i < 3:
						opts.axlims = [-2, 2, -2.1, 6.1]
					else:	
						opts.axlims = [-2, 2, -5.1, 3.1]
					# for event-corrected
					if opts.ifilename == 'erdtdict.pkl':
						if i < 3:
							opts.axlims = [-1.5, 2.5, -2, 6]
						else:	
							opts.axlims = [-2.5, 1.5, -4.5, 3.5]
					fignm = plotDelayPairHistPhysioStaave()
				else:
					opts.axlims = [-7, 7, -12, 16]
					if i < 3:
						opts.axlims = [-5, 5, -6.1, 14.1]
					else:	
						opts.axlims = [-5, 5, -10.1, 10.1]
					# for event-corrected
					if opts.ifilename == 'erdtdict.pkl':
						if i < 3:
							opts.axlims = [-3, 4, -4, 10]
						else:	
							opts.axlims = [-4, 3, -8, 6]
					fignm, atp, ats = plotDelayPairHistPhysioStaall()
					
					for tp in atp: aatp.append(tp)
					for ts in ats: aats.append(ts)

				
				fignm = fignm.replace('physio', 'physio{:d}{:s}'.format(opts.physio, pv))
				setAxes1(axs, opts, provs, weststyle)

				#if opts.savefig:
				#	print('** Save figure: '+fignm)
				#	savefig(fignm, format=fignm.split('.')[-1], dpi=200)
				saveFigure(fignm, opts)
			if not opts.savefig:
				show()
			# save ave/std/rms to file
			pfile = 'gprov-p-avstd'
			sfile = 'gprov-s-avstd'
			if not os.path.isfile(pfile) or not os.path.isfile(sfile):
				provs = []
				for i in range(len(pvs)):
					pv = pvs[i]
					provs += pvdict[pv]
				pf = open(pfile, 'w')
				sf = open(sfile, 'w')
				for i in range(len(provs)):
					pf.write('{:10s}'.format(provs[i]) + '{:7.3f} {:7.3f} {:7.3f} \n'.format(*aatp[i]))
					sf.write('{:10s}'.format(provs[i]) + '{:7.3f} {:7.3f} {:7.3f} \n'.format(*aats[i]))
				pf.close()
				sf.close()

#################
	# hist style in ttpred.py
	if opts.ttpred:
		stawest = readStation(fwest)
		staeast = readStation(feast)
		if opts.stdelete is not None:
			print('Exluding stations in file: '+opts.stdelete)
			stawest = delKeys(stawest, opts.stdelete)
			staeast = delKeys(staeast, opts.stdelete)
	
		opts.axlims = [(-5, 7), ]
		opts.axlims = [(-10, 14), ]
		if opts.ifilename == 'erdtdict.pkl':
			opts.axlims = [(-8, 10), ]
			 
		opts.majorLocator = MultipleLocator(1)
		opts.minorLocator = MultipleLocator(.5)
		opts.majorFormatter = FormatStrFormatter('%d')
		wpair, wps = delayPairs(dtdict, stawest, absdt)
		epair, eps = delayPairs(dtdict, staeast, absdt)
		binwidth = 0.5
	
		for phase in 'P', 'S':
			fignm = histPred(phase, wpair, epair, binwidth)
			saveFigure(fignm, opts)
		sys.exit()



###############################################
	####### change file name 
	fmt = 'png'
	if not opts.blackwhite and not opts.physio:
		fignm = fignm.replace('.png', '-col.'+fmt)
	else:
		fignm = fignm.replace('.png', '.'+fmt)
	if opts.physio != 3:
		if opts.savefig: 
			#print('** Save figure: '+fignm)
			#savefig(fignm, format=fignm.split('.')[-1], dpi=200)
			saveFigure(fignm, opts)
		else:
			show()	


