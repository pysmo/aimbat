#!/usr/bin/env python
"""
File: ttcheck.py

Check S/P delay ratio and distribution.

xlou 02/09/2012
"""

from pylab import *
import os, sys
import matplotlib.transforms as transforms
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from optparse import OptionParser
from ttcommon import readStation, saveStation
from ppcommon import plotcmodel, plotphysio, plotcoast, saveFigure
from ttdict import getDict, delKeys, lsq, delayMeans
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec

def getParams():
	""" Parse arguments and options from command line. 
	"""
	usage = "Usage: %prog [options] <xfiles>"
	parser = OptionParser(usage=usage)
	locsta = 'loc.sta'
	parser.set_defaults(locsta=locsta)
	parser.add_option('-l', '--locsta',  dest='locsta', type='str',
		help='File for station location.')
	parser.add_option('-i', '--ifilename',  dest='ifilename', type='str',
		help='Read delay times from input dict file and command line parsed xfiles are not used.')
	parser.add_option('-o', '--ofilename',  dest='ofilename', type='str',
		help='Read delay times from command line parsed xfiles and output to dict file.')
	parser.add_option('-m', '--meandelay', action="store_true", dest='meandelay',
		help='Plot mean delays of all events.')
	parser.add_option('-M', '--meanmean', action="store_true", dest='meanmean',
		help='Plot mean of event mean delays.')
	parser.add_option('-x', '--xlimit',  dest='xlimit', type='float', nargs=2, 
		help='Left and right x-axis limit to plot.')
	parser.add_option('-A', '--evabsdelete',  dest='evabsdelete', type='str',
		help='A file containing event ids to exclude for absolute delay times.')
	parser.add_option('-E', '--evdelete',  dest='evdelete', type='str',
		help='A file containing event ids to exclude.')
	parser.add_option('-S', '--stdelete',  dest='stdelete', type='str',
		help='A file containing station names to exclude.')
	parser.add_option('-g', '--savefig', type='str', dest='savefig',
		help='Save figure to file instead of showing.')
	parser.add_option('-k', '--blackwhite', action="store_true", dest='blackwhite',
		help='Plot in black&white')
	parser.add_option('-f', '--spfit',  dest='spfit', action="store_true",
		help='Fit a line for S/P delay pairs.')
	parser.add_option('-I', '--indexing',  dest='indexing', type='str',
		help='Indexing for subplot: a b c ')

	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0 and opts.ifilename is None:
		print usage
		sys.exit()
	return opts, files


def plotDelay(evdict, axlims=None):
	""" Plot P and S delays.
	"""
	dta, dtb, dtpair = [], [], []
	if pha in evdict and phb in evdict:
		pdict, pdelay = evdict[pha]
		sdict, sdelay = evdict[phb]
		for sta in stadict.keys():
			if sta in pdict and sta in sdict:
				dtpair.append([pdict[sta], sdict[sta] ])
			elif sta in pdict:
				dta.append(pdict[sta])
			elif sta in sdict:
				dtb.append(sdict[sta])
	elif pha in evdict:
		pdict, pdelay = evdict[pha]
		dta = [ pdict[sta]  for sta in pdict.keys() ]
	elif phb in evdict:
		sdict, sdelay = evdict[phb]
		dtb = [ sdict[sta]  for sta in sdict.keys() ]
	# plot mean delays
	if dtpair != []:
		plot(pdelay, 0, 'b^', ms=13, alpha=.7)
		plot(0, sdelay, 'r^', ms=13, alpha=.7)
		print('Event mean P and S delay time: {:.1f} {:.1f} [s]'.format(pdelay, sdelay))
		plot(pdelay, sdelay, 'k^', ms=13, alpha=.7, label='Mean P/S delay')
	elif dta != []:
		plot(pdelay, 0, 'b^', ms=13, alpha=.7)
		print('Event mean P delay time: {:.1f} [s]'.format(pdelay))
	else:
		plot(0, sdelay, 'r^', ms=13, alpha=.7)
		print('Event mean S delay time: {:.1f} [s]'.format(sdelay))
	# shift individual P or S delays
	shift = 0
	if dtpair != []:
		dtpair = array(dtpair)
		dtp = dtpair[:,0]
		dts = dtpair[:,1]
		plot(dtp, dts, 'g.', ms=10, alpha=.6, label='Pair of P and S delays')
	if dta != []:
		dta = array(dta) + shift
		bbb = ones(len(dta)) * shift
		plot(dta, bbb, 'b.', ms=10, alpha=.4, label='Individual P delays')
	if dtb != []:
		dtb = array(dtb) + shift
		aaa = ones(len(dtb)) * shift
		plot(aaa, dtb, 'r.', ms=10, alpha=.4, label='Individual S delays')
	grid()
	axvline(x=0, color='k', ls='--')
	axhline(y=0, color='k', ls='--')
	xlabel('P delay [s]')
	ylabel('S delay [s]')
	legend(loc=2, numpoints=1)
	rect = mpatches.Rectangle((-2, -6), 4, 12, color='k', alpha=0.2)
	gca().add_patch(rect)
	if axlims is not None:
		axis(axlims)
	else:
		axis('equal')


def plotDelayMap(xdict, phase, axlims=None, vlims=[None,None]):
	""" Plot delay times in map view 
	"""
	vals = array([ stadict[sta][:2] + [xdict[sta],] for sta in xdict.keys() ])
	lat = vals[:,0]
	lon = vals[:,1]
	dtp = vals[:,2]
	vmin, vmax= vlims
	scatter(lon, lat, c=dtp, vmin=vmin, vmax=vmax, marker='o', cmap=cmap, alpha=.8, s=7**2, )
	cbar = colorbar(orientation='h', pad=.07, aspect=30, shrink=0.95)
	cbar.set_label(phase + ' Delay [s]')
	plotphysio(False, True)
	plotcoast(True, True, True)
	if axlims is not None:
		axis(axlims)
	else:
		axis('equal')

	
def plotDelayAll(dtdict, axlims=None, axlimsmap=None, vlims=None):
	""" Plot delays for all events, one by one.
	"""
	for evid in sorted(dtdict.keys()):
		print('event: '+evid)
		evdict = dtdict[evid]
		fig = figure(figsize=(18,12))
		subplots_adjust(left=.05, right=.99, bottom=.05, top=.95, wspace=.05, hspace=.03)
		rcParams['legend.fontsize'] = 10
		gs = gridspec.GridSpec(2, 2, width_ratios=[2.2,3], height_ratios=[1,1])
		ax1 = plt.subplot(gs[0:3:2])
		# s/p ratio
		#subplot2grid((2,2), (0,0), rowspan=2)
		plotDelay(evdict, axlims)
		title(evid)
		# map
		if pha in evdict:
			ax2 = plt.subplot(gs[1])
			#subplot2grid((2,2), (0,1))
			pdict, pdelay = evdict[pha]
			plotDelayMap(pdict, pha, axlimsmap, vlims[0])
		if phb in evdict:
			ax3 = plt.subplot(gs[3])
			#subplot2grid((2,2), (1,1))
			sdict, sdelay = evdict[phb]
			plotDelayMap(sdict, phb, axlimsmap, vlims[1])
		fignm = evid+'.dta.png'
		saveFigure(fignm, opts)


def plotDelayMeans(dpair, xps, opts):
	""" Plot mean delays of all events
	"""
	dtp, dts = dpair[:,0], dpair[:,1] 
	xtp, xts = xps
	zxp, zxs = zeros(len(xtp)), zeros(len(xts))
	if opts.blackwhite:
		#colsyms = ['wo', 'w^', 'wv']
		syms = 'o^v'
		mfcs = ['None', 'None', 'None']
		mfcs = 'www'
		mecs = 'kkk' 
		alphas = [.5, .5, .5]
		alphas = [.8, .6, .6]
		mews = [1.8, 1, 1]
		mss = [9, 8, 8]
	else:
		#mecs = 'kkk'
		#mfcs = 'gbr'
		mfcs = ['None', 'None', 'None']
		mecs = 'gbr'
		syms = '^^^'
		syms = 'o^v'
		alphas = [.8, .6, .6]
		alphas = [.9, .7, .7]
		mews = [.5, .5, .5]
		mews = [2,1,1]
		mss = [10, 9, 9]

	if opts.countevts:
		dlab = 'Both P and S ({:d} events)'.format(len(dtp))
		plab = 'Only P ({:d} events)'.format(len(xtp))
		slab = 'Only S ({:d} events)'.format(len(xts))
	else:	
		dlab = 'Both P and S'
		plab = 'Only P'
		slab = 'Only S'
	xxs = [dtp, xtp, zxs]
	yys = [dts, zxp, xts]
	bbs = [dlab, plab, slab]
	for i in range(3)[::-1]:
		plot(xxs[i], yys[i], marker=syms[i], mfc=mfcs[i], mec=mecs[i], alpha=alphas[i], ms=mss[i], mew=mews[i], label=bbs[i], ls='None')
	grid()
	#if opts.blackwhite:
	if True:
		axhline(y=0, color=mecs[1], ls='--')
		axvline(x=0, color=mecs[2], ls='--')
	else:
		axhline(y=0, color=mfcs[1], ls='--')
		axvline(x=0, color=mfcs[2], ls='--')

	if opts.meanmean:
		mtp = mean(concatenate((dtp, xtp)))
		mts = mean(concatenate((dts, xts)))
		print('Mean of event mean P and S delays: {:.3f} {:.3f}'.format(mtp, mts))
		mlab='Mean ({:.1f} s, {:.1f} s)'.format(mtp,mts)
		if opts.blackwhite:
			plot(mtp, mts, 'ks', ms=11, label=mlab)
		else:
			plot(mtp, mts, 'ms', ms=11, label=mlab)
	npair = len(dpair)
	if npair > 3 and opts.spfit:
		a, b, sa, sb = lsq(dtp, dts, 2)
		pp = linspace(-3,3,11)
		plot(pp,pp*a+b,'r-',label='lsq fit: slope '+ r'$%4.2f \pm %4.2f $' % (a,sa))
	elif npair <= 3 and opts.spfit:
		print('Less than 3 delay pairs. Does not fit a line.')
	legend(loc=2, numpoints=1)
	if opts.title:
		title(opts.title)
	xlabel('Event-mean P Delay Time [s]')
	ylabel('Event-mean S Delay Time [s]')

	axis('equal')

	if opts.axlims is not None:
		axis(opts.axlims)
	#axis('equal')




if __name__ == '__main__':

	ckey = 'RdBu_r'
	cdict = cm.datad[ckey]
	cmap = matplotlib.colors.LinearSegmentedColormap(ckey, cdict)

	opts, ifiles = getParams()

	stadict = readStation(opts.locsta)
	pha = 'P'
	phb = 'S'

	dtdict = getDict(opts, ifiles)
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


	rcParams['legend.fontsize'] = 13
	rcParams['axes.labelsize'] = 'large'
	rcParams['xtick.major.size'] = 6
	rcParams['xtick.minor.size'] = 4
	rcParams['xtick.labelsize'] = 'large'
	rcParams['ytick.major.size'] = 6
	rcParams['ytick.minor.size'] = 4
	rcParams['ytick.labelsize'] = 'large'
	rcParams['axes.titlesize'] = 'x-large'
	opts.majorLocator = MultipleLocator(1)
	opts.minorLocator = MultipleLocator(.5)
	opts.majorFormatter = FormatStrFormatter('%d')

	opts.countevts = False
	if opts.meandelay:
		opts.axlims = None
#		opts.axlims = [-6, 8, -14, 8]
#		opts.axlims = [-8, 8, -14, 10]
#		opts.axlims = [-8, 8, -8, 12]
		opts.axlims = [-7, 7, -7, 9]
		opts.title = os.getcwd()
		opts.title = None

		figure(figsize=(6,8.5))
		subplots_adjust(bottom=.07,top=.95, left=.13, right=.98)
		axis('equal')
		if opts.savefig:
			ofile = 'dmeans'
		else:
			ofile = None
		dpair, xps = delayMeans(dtdict, ofile)
		plotDelayMeans(dpair, xps, opts)
		if opts.indexing is not None:
			ax = gca()
			tt = '(' + opts.indexing + ')'
			trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
			ax.text(-.05, 1.02, tt, transform=trans, va='center', ha='right', size=20, fontweight='bold')	
		else:
			ax = gca()
		xy = 2
		xx = range(opts.axlims[0], opts.axlims[1]+xy, xy)
		yy = range(opts.axlims[2], opts.axlims[3]+xy, xy)
		#ax.set_xticks(xx)
		#ax.set_yticks(yy)
		ax.xaxis.set_major_locator(opts.majorLocator)
		ax.xaxis.set_minor_locator(opts.minorLocator)
		ax.yaxis.set_major_locator(opts.majorLocator)
		ax.yaxis.set_minor_locator(opts.minorLocator)
		if opts.blackwhite:
			ofig = 'dmeansk.png'
		else:
			ofig = 'dmeansc.png'
		saveFigure(ofig, opts)
	
#		if opts.savefig:
#			savefig(ofig, format='png')
#		else:
#			show()

	else:
		axlims, axlimsmap = None, None
		vlims = [ (None, None), (None, None) ]
		axlimsmap = [-126, -66, 25, 50]
		axlims = [-11, 11, -15, 15]
		vlims = [(-2, 2), (-6,6)]
		# for moma and fled
#		axlimsmap = [-108, -66, 25, 50]	#moma
#		axlimsmap = [-113, -66, 25, 53]	#fled
#		axlims = [-6, 6, -8, 8]
#		vlims = [(-2, 2), (-6,6)]
#		vlims = [(-1, 1), (-3, 3)]
		plotDelayAll(dtdict, axlims, axlimsmap, vlims)



