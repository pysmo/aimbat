#!/usr/bin/env python
"""
Compare dtdist (ttvdist.py) from 
  sta-ave
  sta-ave-evcorr
  sta-terms

run at : ~/work/na/sod/tamw60pkl/hdelays/eip/ddrel-damp

xlou 01/26/2013
"""

from pylab import *
import os, sys
from optparse import OptionParser
import matplotlib.transforms as transforms

from ttcommon import readStation
from ppcommon import saveFigure
from ttvdist import plottopo, plotmap
from ttdict import getParser

def getParams():
	""" Create a parser """
	parser = getParser()
	opts, files = parser.parse_args(sys.argv[1:])
	return opts, files


def readSD(ddicts, sdfile):
	sddict = readStation(sdfile)
	##sort by first item value
	sitems = sorted(sddict.items(), key=lambda x: x[1][0])
	dds = []
	sdlist = []
	nd = len(ddicts)
	for item in sitems:
		sta, dist = item[0], item[1][0]
		dts = [ dd[sta][2] for dd in ddicts ]
		dds.append( [dist,] + dts )
		sdlist.append([sta, dist])
	dds = array(dds)
	dists = dds[:,0]
	delays = [ dds[:,i+1]  for i in range(nd) ]
	return sdlist, dists, delays

def getdelay(phase):
	' get delays of three kind'
	dfile0 = bdir1 + 'dt-abs-{:s}'.format(phase.lower())
	dfile1 = bdir2 + 'stadt-sol{:d}-{:s}'.format(mode, phase.lower())
	dfile2 = bdir2 + 'dt-abs-{:s}'.format(phase.lower())
	dfiles = dfile0, dfile1, dfile2
	dtags = 'Sta-ave', 'Sta-terms', 'Sta-ave-evcorr', 
	for dfile, dtag in zip(dfiles, dtags):
		print('{:16s} : {:s}'.format(dtag, dfile))
	ddicts = [ readStation(dfile)  for dfile in dfiles ]
	return ddicts, dtags

def plotdelay(ddicts, dtags, sdfile): 
	sdlist, dists, delays = readSD(ddicts, sdfile)
	#cols = 'r', 'b', 'g'
	cols = 'DarkOrange', 'DarkCyan', 'DarkGreen'
	nd = len(dtags)
	if opts.xlimdef is None:
		opts.xlim = -100, sdlist[-1][1] + 100
	else:
		opts.xlim = None
	if not opts.pmap:
		fig = figure(figsize=(7, 5))
		axd = fig.add_axes([0.1, 0.1, 0.85, 0.7])
		axt = fig.add_axes([0.1, 0.9, 0.85, 0.065], sharex=axd)
	else:
		fig = figure(figsize=(9, 9))
		axd = fig.add_axes([0.1, 0.06, 0.82, 0.4])
		axt = fig.add_axes([0.1, 0.52, 0.82, 0.05], sharex=axd)
		axm = fig.add_axes([0.1, 0.58, 0.82, 0.4])
	plottopo(sdfile, axt)
	if opts.pmap:
		plotmap(stadict, sdlist, opts)
	ax = axd
	for i in range(nd):
		ax.plot(dists, delays[i], marker='.', ls='-', color=cols[i], label=dtags[i])
	# zero line
	ax.axhline(y=0, ls='-', color='k', lw=3)
	# axis
	if phase == 'P':
		ni = 0
	elif phase == 'S':
		ni = 1
	if opts.ylims[ni] is not None:
		ax.set_ylim(opts.ylims[ni])
	ax.set_xlim(opts.xlim)
	ax.xaxis.set_major_locator(opts.xmajorLocator)
	ax.xaxis.set_minor_locator(opts.xminorLocator)
	ax.yaxis.set_major_locator(opts.ymajorLocator)
	ax.yaxis.set_minor_locator(opts.yminorLocator)
	# legend
	ax.legend(bbox_to_anchor=(0.5, 1.01), loc=8, borderaxespad=0., ncol=3,
		shadow=True, fancybox=True, handlelength=3, numpoints=1)
	# label stations
	trans = transforms.blended_transform_factory(ax.transData, ax.transAxes)
	for sd in sdlist[0], sdlist[-1]:
		sta, dist = sd
		ax.plot(dist, .97, 'k^', ms=12, transform=trans)
		ax.text(dist, 1.03, sta, transform=trans, va='bottom', ha='center', size=11)	
	axd.set_ylabel(phase + ' Delay Time [s]')
	axd.set_xlabel('Distance [km]')	

	fignm = odir + 'ddcomp-{:s}-{:s}.png'.format(phase.lower(), sdfile.split('/')[-1])
	saveFigure(fignm, opts)



if __name__ == '__main__':

	opts, sdfiles = getParams()

	phase = 'S'
	odir = './stalines/'


	bdir1 = os.environ['HOME'] + '/work/na/sod/tamw60pkl/hdelays/eip/'
	bdir2 = bdir1 + 'ddrel-damp/'
	mode = 9

	ddicts, dtags = getdelay(phase)

	stadict = readStation(opts.locsta)

	opts.xlimdef = None
	opts.xmajorLocator = MultipleLocator(500)
	opts.xminorLocator = MultipleLocator(100)
	opts.ymajorLocator = MultipleLocator(1)
	opts.yminorLocator = MultipleLocator(.5)
	opts.majorFormatter = FormatStrFormatter('%d')
	rcParams['legend.fontsize'] = 10 

	opts.pmap = True

	for sdfile in sdfiles:
		opts.omercproj = True # use ObliqueMercator for TA.36 XA XR
		net = sdfile.split('/')[-1][:2]
		if net == 'xa':
			opts.ylims = [(-3,3), (-8,4)]
			opts.scol = 'b'
		elif net =='xr':
			opts.ylims = [(-3,3), (-8,4)]
			opts.scol = 'g'
		if net == 'ta':
			opts.ylims = [(-3,3), (-6,6)]
			opts.scol = 'r'
			if len(sdfile.split('/')[-1]) == 5:
				opts.ylims = [(-4,2), (-8,4)]
			else:
				opts.omercproj = False
		plotdelay(ddicts, dtags, sdfile)

