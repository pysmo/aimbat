#!/usr/bin/env python
"""
Differences in event-mean delay times caused by catalog change in earthquake hypocenters.

xlou 09/05/2012
"""



from pylab import *
import os, sys
from optparse import OptionParser



def getParams():
	""" Parse arguments and options from command line. 
	"""
	usage = "Usage: %prog [options] <xfiles>"
	parser = OptionParser(usage=usage)
	parser.add_option('-n', '--network',  dest='network', type='str',
		help='Network code')
	parser.add_option('-c', '--catalogs',  dest='catalogs', type='str', nargs=2, 
		help='Give two catalogs of hypocenters.')
	parser.add_option('-g', '--savefig', action="store_true", dest='savefig',
		help='Save figure to file instead of showing.')
	opts, files = parser.parse_args(sys.argv[1:])
	return opts, files


def getMeans(dfilenm):
	'Get event mean delays from dmeans files'
	dfile = open(dfilenm, 'r')
	lines = dfile.readlines()
	dfile.close()

	dtp, dts = [], []
	xtp, xts = [], []

	dtpairs = {}
	dtsigp = {}
	dtsigs = {}
	for line in lines:
		ev, tp, ts = line.split()
		if tp == '0.000':
			dtsigs[ev] = float(ts)
		elif ts == '0.000':
			dtsigp[ev] = float(tp)
		else:
			dtpairs[ev] = [float(tp), float(ts)]
	dtsings = dtsigp, dtsigs
	return dtpairs, dtsings



if __name__ == '__main__':

	opts, ifiles = getParams()

	opts.axlims = [-6, 8, -12, 10]
	opts.axlims = [-8, 8, -16, 10]
	#opts.axlims = [-9, 9, -15, 15]

	#dfilea = 'def/dmeans-ta'
	#dfileb = 'ehb/dmeans-ta'
	net = opts.network
	cata, catb = opts.catalogs
	dfilea = cata + '/dmeans-' + net
	dfileb = catb + '/dmeans-' + net
	opts.title = 'Event-mean delay change for {:s}: {:s}-->{:s}'.format(net, cata, catb)
	opts.ofig = 'dmchange-{:s}-{:s}-{:s}.png'.format(net, cata, catb)

	tpsa, xpsa = getMeans(dfilea)
	tpsb, xpsb = getMeans(dfileb)

	evs = tpsb.keys()
	tps = array([ tpsa[ev] + tpsb[ev]  for ev in evs ])

	fig = figure(figsize=(9,13))
	subplots_adjust(bottom=.06,top=.95, left=.13, right=.98)
	#axis('equal')

	ax = fig.add_subplot(111)

	for ps in tps:
		x0, y0, x1, y1 = ps
		dx = x1 - x0
		dy = y1 - y0
		if abs(dx) > 0. and abs(dy) > 0.:
			arrow(x0, y0, dx, dy, head_width=0.2, color=rand(3), ls='dotted')

	xy = 2
	if opts.axlims is not None:
		xx = range(opts.axlims[0], opts.axlims[1]+xy, xy)
		yy = range(opts.axlims[2], opts.axlims[3]+xy, xy)
		ax.set_xticks(xx)
		ax.set_yticks(yy)

	axhline(y=0, color='k')
	axvline(x=0, color='k')
	xlabel('Event Mean P Delay Time [s]')
	ylabel('Event Mean S Delay Time [s]')
	title(opts.title)
	grid()

	if opts.savefig:
		savefig(opts.ofig, format='png')
	else:
		show()	
