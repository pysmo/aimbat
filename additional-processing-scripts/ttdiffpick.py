#!/usr/bin/env python
"""
Time pick differences: t0, t1, t2, t3

xlou 08/30/2012
"""

import os, sys
from pylab import *
from optparse import OptionParser
from aimbat.ttconfig import PPConfig, QCConfig, CCConfig, MCConfig, getParser
from aimbat.qualsort import initQual, seleSeis
from aimbat.sacpickle import loadData

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

	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0:
		print parser.usage
		sys.exit()
	return opts, files


def getTimes(pfile, opts, pppara):
	gsac = loadData([pfile,], opts, pppara)
	initQual(gsac.saclist, opts.hdrsel, opts.qheaders)

	times = []
	for sacdh in gsac.saclist:
		if sacdh.selected:
			times.append(sacdh.thdrs[:4])
	return times


def plotdiff(times):
	times = array(times)
	t0 = times[:,0]
	t1 = times[:,1]
	t2 = times[:,2]
	t3 = times[:,3]
	tts = [t0, t1, t2, t3]
	nt = len(tts)

	figure(figsize=(14,10))
	subplots_adjust(left=0.07, right=0.96, bottom=0.07, top=0.92)
	cols = 'kmrcgyb'
	tpks =['T0', 'T1', 'T2', 'T3']
	subplot(211)
	for i in range(nt):
		plot(tts[i]-t0, color=cols[i], marker='.', label=tpks[i]+'-T0')
	legend()
	ylabel('Time pick difference [s]')
	subplot(212)
	ylabel('Time pick difference [s]')
	xlabel('Measurements')
	dt = t3-t2
	md = mean(dt)
	sd = std(dt)
	adt = abs(dt)
	amd = mean(adt)
	asd = std(adt)
	print md, sd, amd, asd

	tit = 'T3-T2: mean(dt)={:.4f} std(dt)={:.4f} [s]'.format(md, sd)
	tit += '   mean(abs(dt))={:.4f} std(abs(dt))={:.4f} [s]'.format(amd, asd)
	plot(dt, 'b.')
	title(tit)

def getPicks(ifiles):
	'Get time picks from *bh?.pkl'
	tdict = {}
	for pfile in ifiles:
		evid = pfile.split('/')[-1]
		print('Read file '+pfile)
		tt = getTimes(pfile, opts, pppara)
		tdict[evid] = tt
	writePickle(tdict, opts.ofilename)
	return tdict


#def addPicks(ifiles):
#	'Add timepicks from tpicks.pkl'
#	tdict = {}
#	for pfile in ifiles:
#		td = readPickle(pfile)
#		for ev in td.keys():
#			tdict[ev] = td[ev]
#	writePickle(tdict, opts.ofilename)
#	return tdict

if __name__ == '__main__' :
	opts, ifiles = getParams()
	pppara = PPConfig()
	qcpara = QCConfig()

	opts.hdrsel = qcpara.hdrsel
	opts.qheaders = qcpara.qheaders

	# get tpicks 
	if opts.ofilename:
		tdict = getPicks(ifiles)
	else:
		tdict = readPickle(ifiles[0])
	
	# plot time diffs
	if opts.plotdiff:	
		times = []
		for ev in tdict.keys():
			times += tdict[ev]
		plotdiff(times)
		subplot(211)
		title(ifiles[0])
		fignm = 'tpkdiff.png'
		if opts.savefig:
			savefig(fignm, format='png')
		else:
			show()

	# find min
	if opts.mindt is not None:
		evs = []
		mindt = opts.mindt
		for ev in sorted(tdict.keys()):
			times = tdict[ev]
			for t in times:
				d1 = t[1]-t[0]
				d2 = t[2]-t[0]
				d3 = t[3]-t[0]
				dd = t[3]-t[2] # use this one
				dt = dd
				if abs(dt) > mindt:
					print ev, dt
					if ev not in evs: evs.append(ev)
		#for ev in evs:
		#	print ev
	

