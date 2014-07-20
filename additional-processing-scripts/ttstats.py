#!/usr/bin/env python
"""
File: ttstats.py

Get mean/std statistics of MCCC delay times for both P and S.

xlou 03/21/2012
"""

from pylab import *
import matplotlib.transforms as transforms
import os
from ttcommon import readStation, saveStation
from ttdict import getParser, delKeys, getDict, delayStats
from ppcommon import plotdelaymap, saveFigure


def getParams():
	""" Parse arguments and options from command line. """
	parser = getParser()
	nstamin = 1
	parser.set_defaults(nstamin=nstamin)
	parser.add_option('-n', '--nstamin',  dest='nstamin', type='int',
		help='Minimun number of measurements for each station for delayStats.')
	parser.add_option('-D', '--meanstd', action="store_true", dest='meanstd',
		help='Get station mean and std delay times.')
	parser.add_option('-M', '--meanonly', action="store_true", dest='meanonly',
		help='Get station mean (but not std) delay times.')
	parser.add_option('-N', '--multinet', action="store_true", dest='multinet',
		help='Delay stats for multiple networks')
	parser.add_option('-H', '--histogram', action="store_true", dest='histogram',
		help='Plot histogram instead of map')
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0 and opts.ifilename is None:
		print parser.usage
		sys.exit()
	return opts, files

def delayStatsPlot(psdict, cmap, opts):
	phases = 'P Delay [s]', 'S Delay [s]'
	titles = 'Station Mean', 'Station STD'
	vinds = 2, 3
	np = len(phases)
	nv = len(vinds)
	fig = figure(figsize=(20,10))
	subplots_adjust(left=.02, right=1, bottom=.03, top=.95, wspace=.01, hspace=.05)
	for i in range(nv):
		for j in range(np):
			subplot(np, nv, i+nv*j+1)
			opts.vlims = opts.vlimsa[i][j]
			plotdelaymap(psdict[j], vinds[i], cmap, phases[j], opts)
	for i in range(nv):
		subplot(np, nv, i+1)
		title(titles[i])
	if opts.stitle is not None:
		suptitle(opts.stitle, fontsize=12)


def delayMeanPlot(psdict, cmap, opts):
	phases = 'Station Average P Delay [s]', 'Station Average S Delay [s]'
	vinds = 2,
	np = len(phases)
	nv = len(vinds)
	for i in range(nv):
		for j in range(np):
			subplot(np, nv, i+nv*j+1)
			opts.vlims = opts.vlimsa[i][j]
			plotdelaymap(psdict[j], vinds[i], cmap, phases[j], opts)


def main0(opts, ifiles, cmap):
	stadict = readStation(opts.locsta)
	dtdict = getDict(opts, ifiles)
	absdt = opts.absdt
	rmean = opts.rmean

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

	# save dt stats for each station
	if absdt:
		pfile = 'dt-abs-p'
		sfile = 'dt-abs-s'
		if rmean:
			pfile = 'dt-mabs-p'
			sfile = 'dt-mabs-s'
	else:
		pfile = 'dt-rel-p'
		sfile = 'dt-rel-s'
		if rmean:
			pfile = 'dt-mrel-p'
			sfile = 'dt-mrel-s'
	pfilem = pfile + '-avstd'
	sfilem = sfile + '-avstd'

	if not os.path.isfile(pfile) or not os.path.isfile(sfile):
		pdict, mtp, stp, rtp = delayStats(dtdict, stadict, 'P', absdt, rmean)
		sdict, mts, sts, rts = delayStats(dtdict, stadict, 'S', absdt, rmean)
		if pdict != {}:
			saveStation(pdict, pfile)
			os.system('echo {:7.3f} {:7.3f} {:7.3f} > {:s}'.format(mtp, stp, rtp, pfilem))
		if sdict != {}:
			saveStation(sdict, sfile)
			os.system('echo {:7.3f} {:7.3f} {:7.3f} > {:s}'.format(mts, sts, rts, sfilem))
	else:
		pdict = readStation(pfile)
		sdict = readStation(sfile)
		mtp, stp = loadtxt(pfilem)
		mts, sts = loadtxt(sfilem)

	# plot 
	psdict = pdict, sdict
	opts.axlims = [-126, -66, 25, 50]
	opts.vlimsa = [ [(-2, 2), (-6, 6)], [(None, None), (None, None)] ]
	opts.vlimsa = [ [(-1.5+mtp, 1.5+mtp), (-4.5+mts, 4.5+mts)], [(None, None), (None, None)] ]
	opts.alpha = 0.8
	opts.msize = 7 
	# for MOMA FLED
	#opts.axlims = [-113, -66, 25, 53]
	#opts.vlimsa = [ [(-1, 1), (-3, 3)], [(None, None), (None, None)] ] 
	#opts.vlimsa = [ [(-.5, .5), (-1.5, 1.5)], [(None, None), (None, None)] ] 

	opts.stitle = pfile[:-2]

	opts.marker = 'o'
	opts.physio = True
	opts.plotcbar = 'v'
	# plot ave only
	if absdt:
		ftitle = 'Absolute Delay Time'
	else:
		ftitle = 'Relative Delay Time'
	if opts.meanonly:
		fig = figure(figsize=(11,11))
		subplots_adjust(left=.05, right=1, bottom=.03, top=.95, wspace=.05, hspace=.05)
		delayMeanPlot(psdict, cmap, opts)
		subplot(211)
		text(-77, 31,  '$\mu_P   =%5.2f$ s' % mtp, size=16)
		text(-77, 29,  '$\sigma_P=%5.2f$ s' % stp, size=16)
		title(ftitle)
		subplot(212)
		text(-77, 31,  '$\mu_S   =%5.2f$ s' % mts, size=16)
		text(-77, 29,  '$\sigma_S=%5.2f$ s' % sts, size=16)

		fignm = 'map-ave-'+ opts.stitle + '.png'
		saveFigure(fignm, opts)

	# plot ave and std
	else:
		delayStatsPlot(psdict, cmap, opts)

		fignm = 'map-avestd'+ opts.stitle + '.png'
		saveFigure(fignm, opts)


def addDelay(nets, opts):
	ddicts = []
	dtdict = {}
	ifileback = opts.ifilename
	for net in nets:
		opts.ifilename = net + '-' + ifileback
		ddict = getDict(opts, ifiles)
		ddicts.append(ddict)
		for evid in ddict.keys():
			dtdict[evid] = ddict[evid]
	return dtdict, ddicts

def addStation(nets, opts):
	xdicts = []
	stadict = {}
	for net in nets:
		locsta = opts.locsta + '.' + net
		xdict = readStation(locsta)
		xdicts.append(xdict)
		for sta in xdict.keys():
			stadict[sta] = xdict[sta]
	return stadict, xdicts



if __name__ == '__main__':

	opts, ifiles = getParams()
	#ckey = 'RdBu_r'
	#ckey = 'rainbow'
	#ckey = 'Pastel1'
	ckey = opts.cptkey
	print('Build color palatte using key: '+ckey)
	cdict = cm.datad[ckey]
	#cmap = matplotlib.colors.LinearSegmentedColormap(ckey, cdict)
	cmap = get_cmap(ckey)


	# only one network:
	if not opts.multinet:
		main0(opts, ifiles, cmap)
		sys.exit()

	nets = 'ta', 'xa', 'xr'
	print('Get delay stats for multiple arrays: {:s} {:s} {:s}'.format(nets[0],nets[1], nets[2]))
	stadict, xdicts = addStation(nets, opts)

	absdt = opts.absdt
	rmean = opts.rmean

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

#	if opts.evdelete is not None:
#		for net in nets:
#			evdfile = opts.evdelete + '-' + net
#			if os.path.isfile(evdfile)
#				print('Exluding events in file: '+evdfile)
#				dtdict = delKeys(dtdict, evdfile)
#	if opts.evabsdelete is not None:
#		for net in nets:
#			evdfile = opts.evabsdelete + '-' + net
#			if os.path.isfile(evdfile)
#				print('Exluding events in file: '+evdfile)
#				dtdict = delKeys(dtdict, evdfile)
#	if opts.stdelete is not None:
#		for net in nets:
#			stdfile = opts.stdelete + '-' + net
#			if os.path.isfile(stdfile)
#				print('Exluding stations in file: '+stdfile)
#				stadict = delKeys(stadict, stdfile)

	# save dt stats for each station
	if absdt:
		pfile = 'dt-abs-p'
		sfile = 'dt-abs-s'
		if rmean:
			pfile = 'dt-mabs-p'
			sfile = 'dt-mabs-s'
	else:
		pfile = 'dt-rel-p'
		sfile = 'dt-rel-s'
		if rmean:
			pfile = 'dt-mrel-p'
			sfile = 'dt-mrel-s'
	pfilem = pfile + '-avstd'
	sfilem = sfile + '-avstd'

	if not os.path.isfile(pfile) or not os.path.isfile(sfile):
		dtdict, ddicts = addDelay(nets, opts)
		pdict, mtp, stp, rtp = delayStats(dtdict, stadict, 'P', absdt, rmean, opts.nstamin)
		sdict, mts, sts, rts = delayStats(dtdict, stadict, 'S', absdt, rmean, opts.nstamin)
	#	print len(stadict.keys()), len(pdict.keys()), len(sdict.keys())
	#	ss = 'TA.N46A'
	#	print ss, stadict[ss]
	#	print pdict[ss]
		saveStation(pdict, pfile)
		saveStation(sdict, sfile)
		os.system('echo {:.3f} {:.3f} {:.3f} > {:s}'.format(mtp, stp, rtp, pfilem))
		os.system('echo {:.3f} {:.3f} {:.3f} > {:s}'.format(mts, sts, rts, sfilem))
	else:
		pdict = readStation(pfile)
		sdict = readStation(sfile)
		mtp, stp = loadtxt(pfilem)
		mts, sts = loadtxt(sfilem)

	# plot 
	psdict = pdict, sdict
	opts.axlims = [-126, -66, 25, 50]
	#opts.vlimsa = [ [(-1.5, 1.5), (-4.5, 4.5)], [(None, None), (None, None)] ]
	opts.vlimsa = [ [(-1.5+mtp, 1.5+mtp), (-4.5+mts, 4.5+mts)], [(None, None), (None, None)] ]
	opts.alpha = 0.8
	opts.msize = 7 

	# for MOMA FLED
	#opts.axlims = [-113, -66, 25, 53]
	#opts.vlimsa = [ [(-1, 1), (-3, 3)], [(None, None), (None, None)] ] 
	#opts.vlimsa = [ [(-.5, .5), (-1.5, 1.5)], [(None, None), (None, None)] ] 

	opts.stitle = pfile[:-2]

	fwest = 'loc.sta.west'
	feast = 'loc.sta.east'
	#if opts.multinet:
	#	feast = 'loc.sta.eastx'

	opts.marker = 'o'
	opts.physio = True

	# plot ave only
	if absdt:
		ftitle = 'Absolute Delay Time'
	else:
		ftitle = 'Relative Delay Time'
	if opts.meanonly and opts.multinet:
		opts.axlims = [-125, -67, 25.5, 51.5]
		opts.vlimsa = [ [(-1.5+mtp, 1.5+mtp), (-4.5+mts, 4.5+mts)], [(None, None), (None, None)] ]
		opts.alpha = 0.8
		opts.msize = 5 
		opts.physio = True

		fig = figure(figsize=(10,11))
		#subplots_adjust(left=.04, right=.98, bottom=.01, top=.95, wspace=.05, hspace=.01)
		subplots_adjust(left=.04, right=1, bottom=.03, top=.96, wspace=.05, hspace=.04)

		markers = '^', 's', 'o'
		msizes = 7, 5, 5
		pcbars ='v', None, None 
		for xdict, marker, ms, pcbar in zip(xdicts, markers, msizes, pcbars):
			xpdict, xsdict = {}, {}
			for sta in xdict.keys():
				if sta in pdict and sta in sdict:
					xpdict[sta] = pdict[sta]
					xsdict[sta] = sdict[sta]
			xpsdict = xpdict, xsdict
			print xpdict[sta], xsdict[sta]
			opts.marker = marker
			opts.msize = ms
			opts.plotcbar = pcbar
			delayMeanPlot(xpsdict, cmap, opts)
		subplot(211)
		text(-77, 31,  '$\mu_P   =%5.2f$ s' % mtp, size=16)
		text(-77, 29,  '$\sigma_P=%5.2f$ s' % stp, size=16)
		title(ftitle)
		subplot(212)
		text(-77, 31,  '$\mu_S   =%5.2f$ s' % mts, size=16)
		text(-77, 29,  '$\sigma_S=%5.2f$ s' % sts, size=16)

		fignm = 'map-ave-'+ opts.stitle + '.png'
		saveFigure(fignm, opts)


	# plot histogram for WE sep
	elif opts.histogram and opts.multinet:

		
		stawest = readStation(fwest)
		staeast = readStation(feast)

		stadicts = [stawest, staeast]
		stdlists =[]
#			stad = stadicts[i]
		for stad in stadicts:
			stdp, stds = [], []
			for sta in stad.keys():
				if sta in pdict:
					stdp.append(pdict[sta][3])
				if sta in sdict:
					stds.append(sdict[sta][3])
		
			stdlists.append([stdp, stds])

		fig = figure(figsize=(6,8))
		ax0 = subplot(211)
		ax1 = subplot(212, sharex=ax0, sharey=ax0)
		axs = [ax0, ax1]
		subplots_adjust(left=.13, right=.97, bottom=.07, top=0.96, hspace=.1, wspace=.05)

		# bins
		if opts.absdt:
			smax = 6
			ds = 0.5
		else:
			smax = 3
			ds = 0.25
		pbin = linspace(0, smax, smax/ds*2+1)
		sbin = linspace(0, smax, smax/ds+1)
		tts = 'West', 'East'
		for i in range(2):
			stp, sts = stdlists[i]
			ax = axs[i]
			trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
			ax.hist(stp, pbin, histtype='step', color='b', label='P')
			ax.hist(sts, sbin, histtype='step', color='r', label='S')
			ax.text(0.5, 0.9, tts[i], transform=trans, va='center', ha='center', size=14)
			ax.text(0.8, 0.6, '$\mu_P = %.2f s$'%mean(stp), transform=trans, va='center', ha='left', size=14)
			ax.text(0.8, 0.5, '$\mu_S = %.2f s$'%mean(sts), transform=trans, va='center', ha='left', size=14)
			ax.legend()
			ax.set_ylabel('Histogram Counts')
		if opts.absdt:
			ax1.set_xlabel('Station-std Absolute Delay Time [s]')
			fignm = 'dtstd-hist-abs.png'
		else:
			ax1.set_xlabel('Station-std Relative Delay Time [s]')
			fignm = 'dtstd-hist-rel.png'
		saveFigure(fignm, opts)

