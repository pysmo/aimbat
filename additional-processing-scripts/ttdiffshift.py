#!/usr/bin/env python
"""
Time pick differences: using different shifts in MCCC.

xlou 09/19/2012
"""

import os, sys
from pylab import *
from optparse import OptionParser
from ttcommon import readMLines, parseMLines, readPickle, writePickle
from pysmo.aimbat.qualsort import initQual, seleSeis
from pysmo.aimbat.sacpickle import loadData

#from pysmo.aimbat.sacpickle import readPickle, writePickle


try:
	import cPickle as pickle
except:
	import pickle

def getParams():
	""" Parse arguments and options. """
	usage = "Usage: %prog [options] <pklfile(s)>"
	parser = OptionParser(usage=usage)
	parser.add_option('-S', '--srate',  dest='srate', type='float',
		help='Sampling rate. Default is None, use the original rate.')
	parser.add_option('-g', '--savefig', action="store_true", dest='savefig',
		help='Save figure instead of showing.')
	parser.add_option('-e', '--event', action="store_true", dest='event',
		help='Plot event by event.')
	parser.add_option('-p', '--plotdiff', action="store_true", dest='plotdiff',
		help='plot time pick diff')
	parser.add_option('-m', '--mindt',  dest='mindt', type='float',
		help='Min dt to print out evid')
	parser.add_option('-o', '--ofilename',  dest='ofilename', type='str',
		help='Output filename.')
	parser.add_option('-t', '--tpickfile',  dest='tpickfile', type='str',
		help='Filename of time pick pickle files.')
	parser.add_option('-H', '--histogram', action="store_true", dest='histogram',
		help='Plot histogram instead of map')  
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0 and and opts.ifilename is None:
		print parser.usage
		sys.exit()
	return opts, files


def readMCFile(mcfile):
	'Get arrival times from mcfile'
	print('Reading mcfile: ' + mcfile)
	headlines, mccclines, taillines = readMLines(mcfile)
	phase, event, stations, ttimes, sacnames = parseMLines(mccclines, taillines)	
	nsta = len(stations)
	mccctt_mean = float(taillines[0].split()[1])
	mctime = ttimes[:,0] + mccctt_mean
	evid = mcfile.split('/')[-1][:17]
	return mctime, evid, phase

def getMCDict(mcfiles):
	'Read multiple mcfiles into one dict'
	mcdict = {'P': {}, 'S': {}}
	for mcfile in mcfiles:
		mctime, evid, phase = readMCFile(mcfile)
		mcdict[phase][evid] = mctime
	return mcdict

def getPKDict(ttdict):
	'Get tpicks (t2) into pkdict for both P and S '
	pkdict = {'P': {}, 'S': {}}
	for pkl in ttdict.keys():
		if pkl.split('.')[-2] == 'bhz':
			phase = 'P'
		else:
			phase = 'S'
		evid = pkl.split('/')[-1][:17]
		pkdict[phase][evid] = list(array(ttdict[pkl])[:,2])
	return pkdict

def dict2list(mcdicts):
	'Read dicts of arrival times to lists of arrays'
	pevids = sorted(mcdicts[0]['P'].keys())
	sevids = sorted(mcdicts[0]['S'].keys())
	ptimes, stimes = [], []
	for mcdict in mcdicts:
		pdict, sdict = mcdict['P'], mcdict['S']
		plist, slist = [], []
		for evid in pevids:
			plist += list(pdict[evid])
		for evid in sevids:
			slist += list(sdict[evid])
		ptimes.append(array(plist))
		stimes.append(array(slist))
	return ptimes, stimes

def getPlotDiff(mcdicts, mcshifts, pkdict):
	'Get and plot t3-t2 for 4 shifts'
	ptimes, stimes = dict2list(mcdicts)
	nshift = len(ptimes)
	if pkdict is None:
		tp0, ts0 = ptimes[0], stimes[0]
	else:
		tp, ts = dict2list([pkdict,])
		tp0, ts0 = tp[0], ts[0]
	# plot
	bins = linspace(-0.1, 0.1, 41)
	ymax = 25000
	bins = linspace(-0.05, 0.05, 41)
	ymax = 14000
	figure(figsize=(12, 14))
	subplots_adjust(left=0.09, right=0.96, bottom=0.03, top=0.96)
	for i in range(nshift):
		dtp = ptimes[i] - tp0
		dts = stimes[i] - ts0
		mtp = mean(abs(dtp))
		mts = mean(abs(dts))
		pleg = mcshifts[i] + ' P mean(abs(dt))={:.4f} s'.format(mtp)
		sleg = mcshifts[i] + ' S mean(abs(dt))={:.4f} s'.format(mts)
		print(pleg, sleg)
		dt = dtp, dts
		mt = mtp, mts
		leg = pleg, sleg
		for j in range(2):
			subplot(nshift, 2, i*2+1+j)
			if not opts.histogram:
				plot(dt[j], '.')
			else:
				hist(dt[j], bins)
				axvline(x=-mt[j], color='r')
				axvline(x=mt[j], color='r')
				xlim([bins[0], bins[-1]])
				ylim([-400, ymax])
			ylabel('T3-T2 [s]')
			title(leg[j])

	if opts.savefig:
		if opts.histogram:
			savefig('ttime-diff-hist.png', format='png')
		else:
			savefig('ttime-diff.png', format='png')
	else:
		show()


if __name__ == '__main__' :
	opts, ifiles = getParams()

	# get mcdict(s) from mcfiles, pick dict from tpicks.pkl
	if opts.ofilename:
		if opts.tpickfile is None:
			mcdict = getMCDict(ifiles)
			writePickle(mcdict, opts.ofilename)
		else:
			ttdict = readPickle(opts.tpickfile)
			pkdict = getPKDict(ttdict)
			writePickle(pkdict, opts.ofilename)

	# get and plot t3-t2 for shifts
	pkfile = 'pkdict.pkl'
	if opts.plotdiff:
		mcdicts = [ readPickle(pfile) for pfile in ifiles ]
		mcshifts = [ pfile.split('-')[1].split('.')[0] for pfile in ifiles ]
		pkdict = readPickle(pkfile)
		getPlotDiff(mcdicts, mcshifts, pkdict)


	# print events with large (t3-t2)
	mindt = opts.mindt
	if mindt is not None:
		mcdict = readPickle(ifiles[0])
		pkdict = readPickle(pkfile)
		for phase in 'P', 'S':
			print ('# Event with abs(t3-t2) > {:.3f} s for {:s}'.format(mindt, phase)) 
			evids = sorted(pkdict[phase].keys())
			for evid in evids:
				dt = mcdict[phase][evid] - pkdict[phase][evid]
				for t in abs(dt):
					if t > mindt: 
						print ('{:s} {:8.3f}'.format(evid, t))
