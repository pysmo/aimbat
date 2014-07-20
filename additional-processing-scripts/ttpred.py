#!/usr/bin/env python

from pylab import *
import os
import matplotlib.transforms as transforms
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
#from ttcommon import readPickle, writePickle
from pysmo.aimbat.sacpickle import readPickle, writePickle
from pysmo.aimbat.plotutils import axLimit
from ttcommon import readStation, saveStation
from ttdict import getParser, delayStats
from ttstats import addDelay
from ppcommon import saveFigure

def getParams():
	""" Create a parser """
	parser = getParser()
	refmodel = 'iasp91'
	nstamin = 1
	phase = 's'
	parser.set_defaults(nstamin=nstamin)
	parser.set_defaults(refmodel=refmodel)
	parser.set_defaults(phase=phase)
	parser.add_option('-n', '--nstamin',  dest='nstamin', type='int',
		help='Minimun number of measurements for each station for delayStats.')
	parser.add_option('-r', '--refmodel',  dest='refmodel', type='str',
		help='Reference model (iasp91/mc35/xc35). Default is {:s}'.format(refmodel))
	parser.add_option('-s', '--stats',  dest='stats', action="store_true",
		help='Calculate delay stats.')
#	parser.add_option('-p', '--pwave',  dest='pwave', action="store_true",
#		help='Predicted P delay times instead of S.')
	parser.add_option('-p', '--phase',  dest='phase', type='str',
		help='Phase. Default is {:s}'.format(phase))
	parser.add_option('-t', '--arrtime',  dest='arrtime', action="store_true",
		help='Get arrival time instead of delay time.')
	parser.add_option('-H', '--histogram', action="store_true", dest='histogram',
		help='Plot histogram instead of map')
	parser.add_option('-I', '--indexing',  dest='indexing', type='str',
		help='Indexing for subplot: a b c ')
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0 and opts.ifilename is None:
		print parser.usage
		sys.exit()
	return opts, files

def readFile(ifilenm, arrtime=False):
	print('Read predicted arrival/delay times from file : '+ifilenm)
	refmodel = opts.refmodel
	if refmodel == 'iasp91':
		mid = 3
	elif refmodel == 'mc35':
		mid = 1
	elif refmodel == 'xc35':
		mid = 2
	ifile = open(ifilenm)
	lines = ifile.readlines()
	ifile.close()
	dtdict = {}
	for line in lines:
		sline = line.split()
		rayid, evid, sta, raynum, phase = sline[:5]
		times = [ float(v) for v in sline[7:] ]
		if arrtime:
			dt = times[mid]
		else:
			dt = times[0] - times[mid]
		#print evid, sta, phase, dt
		if evid in dtdict:
			evdict = dtdict[evid]
		else:
			evdict = {}
			dtdict[evid] = evdict
		if phase in evdict:
			xdict, xdelay = evdict[phase]
		else:
			xdict = {}
			xdelay = 0
			evdict[phase] = xdict, xdelay
		xdict[sta] = dt
	# calculate event mean delay
	for evid in dtdict.keys():
		evdict = dtdict[evid]
		xdict, xdelay = evdict[phase]
		xdelay = mean(xdict.values())
		for sta in xdict.keys():
			xdict[sta] -= xdelay
		evdict[phase] = xdict, xdelay
	return dtdict

def getDicts(opts):
	'Get dtdicts'
	dtdicts = {}
	if opts.ofilename:
		for tfile in ifiles:
			dtag = tfile.split('/')[-1].split('.')[-1]
			dtdicts[dtag] = readFile(tfile, opts.arrtime)
		writePickle(dtdicts, opts.ofilename)
		print('Write to file :'+ opts.ofilename)
	else:
		print('Read file: '+opts.ifilename)
		dtdicts = readPickle(opts.ifilename)
	return dtdicts

def getStats(dtdicts, stadict, opts):
	'Get delay stats'
	rmean = False
	absdt = opts.absdt
	phase = opts.phase
	ftag = 'pdt-'
	if absdt:
		ftag += 'abs'
	else:
		ftag += 'rel'
	ftag += '-{:s}-'.format(phase.lower())
	mtag = '-avstd'
	dtags = sorted(dtdicts)	# dtags: d0-d5 da
	for dtag in dtags:
		dtdict = dtdicts[dtag]
		sfile = ftag + dtag
		print(sfile)
		sfilem = sfile + mtag
		sdict, mts, sts, rts = delayStats(dtdict, stadict, phase, absdt, rmean, opts.nstamin)
		saveStation(sdict, sfile)
		os.system('echo {:9.3f} {:9.3f} {:9.3f} > {:s}'.format(mts, sts, rts, sfilem))


def getHist(dtdicts, stadicts, opts):
	'Get delays for E/W histograms '
	rmean = False
	absdt = opts.absdt
	dtags = sorted(dtdicts)	# dtags: d0-d5 da
	stawest, staeast = stadicts
	ewdicts = {}
	for dtag in dtags:
		dtdict = dtdicts[dtag]
		dtlists = [], []
		for evid in dtdict.keys():
			xdict, xdelay = dtdict[evid][phase]
			if not absdt: xdelay = 0
			for sta in xdict.keys():
				if sta in stawest:
					dtlists[0].append(xdict[sta] + xdelay)
				elif sta in staeast:
					dtlists[1].append(xdict[sta] + xdelay)
		ewdicts[dtag] = dtlists
	return ewdicts

def plotHist22(ewdicts, depths):
	'Plot E/W histograms in 2 columns'
	figure(figsize=(10, 14))
	subplots_adjust(left=.1, right=.98, bottom=.05, top=0.96)
	bins = opts.bins
	dtags = sorted(dtdicts.keys())
	nd = len(dtags)
	axs = []
	for i in range(nd):
		wax = subplot(nd, 2, 2*i+1)
		eax = subplot(nd, 2, 2*i+2, sharex=wax, sharey=wax)
		axs.append([wax, eax])	
	for i in range(nd):
		dtag = dtags[i]
		wdt, edt = ewdicts[dtag]
		axw, axe = axs[i]
		wtrans = transforms.blended_transform_factory(axw.transAxes, axw.transAxes)
		etrans = transforms.blended_transform_factory(axe.transAxes, axe.transAxes)
		axw.hist(wdt, bins, color='k', alpha=.5)
		axe.hist(edt, bins, color='k', alpha=.5)
		axw.text(0.05, 0.80, depths[dtag], transform=wtrans, va='center', ha='left', size=12)
		axe.text(0.05, 0.80, depths[dtag], transform=etrans, va='center', ha='left', size=12)
		axw.text(0.80, 0.86, r'$\mu$={:.1f} s'.format(mean(wdt)), transform=wtrans, va='center', size=12)
		axe.text(0.80, 0.86, r'$\mu$={:.1f} s'.format(mean(edt)), transform=etrans, va='center', size=12)
		axw.text(0.80, 0.70, r'$\sigma$={:.1f} s'.format(std(wdt)), transform=wtrans, va='center', size=12)
		axe.text(0.80, 0.70, r'$\sigma$={:.1f} s'.format(std(edt)), transform=etrans, va='center', size=12)
		axw.set_ylabel('Histogram')
	axw.set_xlabel('Predicted S delay times [s]')
	axe.set_xlabel('Predicted S delay times [s]')
	axs[0][0].set_title('West')
	axs[0][1].set_title('East')

	if opts.absdt:
		fignm = 'pdt-hist2-abs.png'
	else:
		fignm = 'pdt-hist2-rel.png'
	saveFigure(fignm, opts)

def plotHist23(ewdicts, depths):
	'Plot E/W histograms in subplots 2x3'
	figure(figsize=(14, 8))
	subplots_adjust(left=.03, right=.99, bottom=.09, top=0.97, hspace=.11, wspace=.03)
	rcParams['legend.fontsize'] = 13
	#bins = opts.bins
	dtags = sorted(depths)
	binwidth = opts.binwidth
	if model == 'NA04' or model == 'NA07':
		dinds = [1, 2, 3, 4, 5, 0]
		dinds = [2, 3, 4, 5, 0]
		dinds = [0, 2, 3, 4, 5]
		#binwidth = 0.25
	else:
		dinds = [7, 2, 3, 4, 5, 6]
		#binwidth = 0.25
	if phase == 'P':
		binwidth *= 0.5
	ainds = range(len(dinds))
	bins1 = linspace(-10, 10, 20/binwidth+1)	
	bins2 = linspace(-10, 10, 20/binwidth/2+1)	

	axs = []
	nx, ny = 2, 3
	for i in range(nx):
		for j in range(ny):
			axs.append(subplot(nx, ny, i*ny+j+1))
	cols = 'rb'
	ewlegs = 'West', 'East'
	ewys = 0.97, 0.87
	#for i in range(nd-1): # dtags
	#for i in range(nd-1)[::-1]: # dtags
	for i in ainds[::-1]:
		dtag = dtags[dinds[i]]
		if dtag == 'd0' or dtag == 'd7':
			bins = bins2
		else:
			bins = bins1
		ax = axs[i]
		trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
		for k in range(2): # E/W
			dt = ewdicts[dtag][k]
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
		ax.text(0.02, 0.70, depths[dtag], transform=trans, ha='left',va='center',size=14)
		# label model using dir basename
		ax.text(0.02, 0.77, model,        transform=trans, ha='left',va='center',size=14)
		#ax.set_title(depths[dtag])
		ax.legend(loc=2)
		alim = opts.axlims[i]
		if phase == 'P':
			alim = array(alim)*0.5
		ax.set_xlim(alim)
		yy = ax.get_ylim()
		yy = axLimit(yy, 0.05)
		ax.set_ylim(yy)
		ax.axhline(y=0, color='k', ls=':')
		ax.xaxis.set_major_locator(opts.majorLocator)
		ax.xaxis.set_minor_locator(opts.minorLocator)
	for i in range(nx):
		axs[i*ny].set_ylabel('Histogram')
	for j in range(ny):
		axs[ny+j].set_xlabel('Predicted {:s} S Delay [s]'.format(opts.atag))
		axs[j].set_yticks([])
		axs[ny+j].set_yticks([])

	if len(dinds) < 6:
		axs[-1].set_visible(False)
		axs[-2].set_xlim(opts.axlims[-1])
	fignm = 'pdt-hist-{:s}.png'.format(opts.ftag)
	saveFigure(fignm, opts)



def plotHist16(ewdicts, depths):
	'Plot E/W histograms in subplots 1x6'
	figure(figsize=(22, 4))
	#subplots_adjust(left=.04, right=.99, bottom=.15, top=0.9, hspace=.11, wspace=.16)
	subplots_adjust(left=.025, right=.99, bottom=.15, top=0.9, hspace=.11, wspace=.03) # for no yticklabels
	rcParams['legend.fontsize'] = 13
	#bins = opts.bins
	dtags = sorted(depths)
	binwidth = opts.binwidth
	if model == 'NA04' or model == 'NA07' or model == 'ND2008' :
		dinds = [2, 3, 4, 5, 0]
		dinds = [0, 2, 3, 4, 5]
		#binwidth = 0.25
	else:
		dinds = [2, 3, 4, 5, 6, 7]
		dinds = [7, 2, 3, 4, 5, 6]
		#binwidth = 0.25
	if phase == 'P':
		binwidth *= 0.5
	ainds = range(len(dinds))
	bins1 = linspace(-10, 10, 20/binwidth+1)	
	bins2 = linspace(-10, 10, 20/binwidth/2+1)	

	axs = []
	nx, ny = 1, 6
	for i in range(nx):
		for j in range(ny):
			axs.append(subplot(nx, ny, i*ny+j+1))
	cols = 'rb'
	ewlegs = 'West', 'East'
	ewlegs = 'RMW', 'RME'
	ewys = 0.97, 0.87
	#for i in range(nd-1): # dtags
	#for i in range(nd-1)[::-1]: # dtags
	for i in ainds[::-1]:
		dtag = dtags[dinds[i]]
		if dtag == 'd0' or dtag == 'd7':
			bins = bins2
		else:
			bins = bins1
		ax = axs[i]
		trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
		for k in range(2): # E/W
			dt = ewdicts[dtag][k]
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
		ax.text(0.02, 0.66, depths[dtag], transform=trans, ha='left',va='center',size=14)
		# label model using dir basename
		ax.text(0.02, 0.74, model,        transform=trans, ha='left',va='center',size=14)
		#ax.set_title(depths[dtag])
		#ax.set_title('{:s} : {:s}'.format(model, depths[dtag]))
		ax.legend(loc=2)
		alim = opts.axlims[i]
		if phase == 'P':
			alim = array(alim)*0.5
		ax.set_xlim(alim)
		yy = ax.get_ylim()
		yy = axLimit(yy, 0.05)
		ax.set_ylim(yy)
		ax.axhline(y=0, color='k', ls=':')
		ax.xaxis.set_major_locator(opts.majorLocator)
		ax.xaxis.set_minor_locator(opts.minorLocator)
	for i in range(nx):
		axs[i*ny].set_ylabel('Histogram')
	for j in ainds:
		axs[j].set_xlabel('Predicted {:s} S Delay [s]'.format(opts.atag))
		#axs[j].ticklabel_format(style='sci', scilimits=(0,0), axis='y')
		axs[j].set_yticks([])
	if len(dinds) < 6:
		axs[-1].set_visible(False)
		axs[-2].set_xlim(opts.axlims[-1])
	# index
	if opts.indexing is not None:
		tag = '({:s})'.format(opts.indexing)
		axs[0].text(-0.02, 1.01, tag, transform=axs[0].transAxes,  
			va='bottom', ha='right', size=20, fontweight='bold')

	fignm = 'pdt-hist-{:s}.png'.format(opts.ftag)
	saveFigure(fignm, opts)




if __name__ == '__main__':

	opts, ifiles = getParams()

#	if opts.pwave:
#		phase = 'P'
#	else:
#		phase = 'S'

#	phase = opts.phase
#	phase = phase.upper()

	model = os.path.basename(os.getcwd()).upper()
	if model[:3] == 'WUS':
		model = model.replace('WUS', 'wUS')
	elif model[-3:] == 'ANB':
		model = model.replace('ANB', 'ANb')
	elif model[:6] == 'GYPSUM':
		model = model.replace('GYPSUM', 'GyPSuM')

	if opts.phase is None:
		if model.split('-')[-1] == 'P' or model.split('-')[0] == 'P' :
			opts.phase = 'P'
		else:
			opts.phase = 'S'
	opts.phase = opts.phase.upper()

	rcParams['legend.fontsize'] = 10
	rcParams['axes.labelsize'] = 'large'
	rcParams['xtick.major.size'] = 6
	rcParams['xtick.minor.size'] = 4
	rcParams['xtick.labelsize'] = 'large'
	rcParams['ytick.major.size'] = 6
	rcParams['ytick.minor.size'] = 4
	rcParams['ytick.labelsize'] = 'large'
	rcParams['axes.titlesize'] = 'x-large'

	# dtags
	depths = {}
	depths['d0'] = 'Moho-660 km'
	depths['d1'] = '0-Moho'
	depths['d2'] = 'Moho-80 km'
	depths['d3'] = '80-240 km'
	depths['d4'] = '240-410 km'
	depths['d5'] = '410-660 km'
	depths['d6'] = '660-1400 km'
	depths['d7'] = 'Moho-1400 km'
	depths['da'] = 'All' #'0-660 km'

	# get delay stats
	if opts.stats:
		dtdicts = getDicts(opts)
		if os.path.isfile(opts.locsta+'-true'):
			stadict = readStation(opts.locsta+'-true')
		else:
			stadict = readStation(opts.locsta)
		getStats(dtdicts, stadict, opts)

	# get and plot histograms
	fwest = 'loc.sta.west'
	feast = 'loc.sta.east'
	if opts.absdt:
		opts.ftag = 'abs'
		opts.atag = 'Absolute'
		opts.bins = linspace(-8,8,81)
		opts.binwidth = 0.25
		opts.axlims = [ (-2.5,3.5) for i in range(6) ]
		opts.axlims[0] = (-4,8)
		opts.axlims[0] = (-5,7)
	else:
		opts.ftag = 'rel'
		opts.atag = 'Relative'
		opts.bins = linspace(-4,4,41)
		#opts.axlims = [ (-2,2) for i in range(6) ]
		opts.axlims = [ (-4,4) for i in range(6) ]
		#opts.axlims[0] = (-4,4)
		#opts.axlims[3] = (-4,4)
	opts.majorLocator = MultipleLocator(1)
	opts.minorLocator = MultipleLocator(.5)
	opts.majorFormatter = FormatStrFormatter('%d')

	hfile = 'ewhist-{:s}.pkl'.format(opts.ftag)
	if opts.histogram:
		if not os.path.isfile(hfile):
			dtdicts = getDicts(opts)
			if os.path.isfile(opts.locsta+'-true'):
				staall = readStation(opts.locsta+'-true')
			else:
				staall = readStation(opts.locsta)
			stawest = readStation(fwest)
			staeast = readStation(feast)
			# select stations
			for staew in stawest, staeast:
				for sta in sorted(staew):
					if not sta in staall:
						del staew[sta]
			stadicts = [stawest, staeast]
			ewdicts = getHist(dtdicts, stadicts, opts)
			writePickle(ewdicts, hfile)
		else:
			print('Read file: '+hfile)
			ewdicts = readPickle(hfile)
		#plotHist23(ewdicts, depths)
		plotHist16(ewdicts, depths)


