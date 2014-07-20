#!/usr/bin/env python
"""

Calculate ray parameter/take-off angle/incidence angle/distance using TauP/ttimes.
Bin delay times by incidence angles.

ttimes (f2py) is much faster than TauP (java).

xlou 10/10/2012
"""

from pylab import *
from commands import getoutput
from os import linesep, system
import os, sys
import matplotlib.transforms as transforms
from matplotlib.ticker import MultipleLocator, FormatStrFormatter

from pysmo.aimbat.sacpickle import readPickle, writePickle
from pysmo.aimbat.plotutils import axLimit
from ttcommon import readMLines, parseMLines, readStation, saveStation, getVel0, getVel
from ppcommon import saveFigure
from ttdict import getParser
from getime import getime
from deltaz import deltaz

def getParams():
	""" Create a parser """
	parser = getParser()
	refmodel = 'iasp91'
	nbin = 2
	parser.set_defaults(nbin=nbin)
	parser.set_defaults(refmodel=refmodel)
	parser.add_option('-n', '--nbin',  dest='nbin', type='int',
		help='Number of incidence-angle bins. Default is {:d}.'.format(nbin))
	parser.add_option('-r', '--refmodel',  dest='refmodel', type='str',
		help='Reference model (iasp91/mc35/xc35). Default is {:s}'.format(refmodel))
	parser.add_option('-s', '--stats',  dest='stats', action="store_true",
		help='Calculate delay stats.')
	parser.add_option('-T', '--taup',  dest='taup', action="store_true",
		help='Use TauP instead of ttimes to calculate incidence angles.')
	parser.add_option('-H', '--histogram', action="store_true", dest='histogram',
		help='Plot histogram instead of map')

	parser.add_option('-N', '--multinet', action="store_true", dest='multinet',
		help='Multiple networks')
	parser.add_option('-I', '--incstats', action="store_true", dest='incstats',
		help='Incidence angles statistics.')

	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0 and opts.ifilename is None:
		print parser.usage
		sys.exit()
	return opts, files


def getModel(opts):
	'Get reference model and velocities'
	modnam = opts.refmodel
	moddir = '/opt/local/seismo/data/models/'
	opts.model = moddir + modnam
	mtvel = opts.model + '.tvel'
	vp, vs = getVel0(mtvel)
	opts.vel0 = [vp, vs]
	print('--> Surface P and S velocities from {:s}: {:.2f} {:.2f} km/s'.format(modnam, vp, vs))
	vals = loadtxt(mtvel, skiprows=2)
	deps = vals[:,0]
	velp = vals[:,1]
	vels = vals[:,2]
	opts.dpvpvs = deps, velp, vels


def taup_time(mod, phase, edep, elat, elon, slat, slon):
	'Calculate travel time, ray parameter, takeoff angle, incidence angle, and distance.'
	cmd = 'taup_time -mod {:s} -ph {:s} -h {:f} -evt {:f} {:f} -sta {:f} {:f}'
	cmd = cmd.format(mod, phase, edep, elat, elon, slat, slon)
	out = getoutput(cmd).split(linesep)[5].split()
	time, rayp, toa, inc, dis = [ float(d) for d in out[3:8] ]
	return time, rayp, toa, inc, dis

def getDelayDict(opts):
	'Get dtdict'	
	if not opts.multinet:
		dtdict = readPickle(opts.ifilename)
		print('Read delay time dict from '+opts.ifilename)
	else:
		nets = opts.nets
		print('Read delay time dicts for nets: {:s} {:s} {:s}'.format(nets[0], nets[1], nets[2]))
		dtdict = {}
		for net in nets:
			ddict = readPickle(net+'-'+opts.ifilename)
			for evid in ddict.keys():
				dtdict[evid] = ddict[evid]
	return dtdict

def getIncTauP(dtdict, stadict, opts):
	'Calculate incidence angles using TauP'
	mod = opts.refmodel
	evids = sorted(dtdict.keys())
	for evid in evids:
		print('Calculate incidence angles for event : '+evid)
		evdict = dtdict[evid]
		elat, elon, edep, = evdict['event']['hypo'][:3]
		for phase in phases:
			if phase in evdict:
				xdict, xdelay = evdict[phase]
				for sta in xdict.keys():
					slat, slon = stadict[sta][:2]
					time, rayp, toa, inc, dis = taup_time(mod, phase, edep, elat, elon, slat, slon)
					# replace delay time with more info from taup
					xdict[sta] = [xdict[sta], rayp, toa, inc, dis]
	writePickle(dtdict, opts.ofilename)
	return dtdict

def ttimes(mod, phase, vel0, vel1, slat, slon, elat, elon, edep):
	'Calculate travel time, ray parameter, takeoff angle, incidence angle, and distance.'
	r2d = 180/pi
	radius = 6371.
	if phase == 'P':
		iph = 0
	elif phase == 'S':
		iph = 1
	else:
		print('Phase: {0:s}. Not P or S. Skip for now..'.format(phase))
		sys.exit()
	v0 = vel0[iph]
	v1 = vel1[iph]
	time, elcr, dtdd = getime(mod, phase, slat, slon, elat, elon, edep, 0, 0, 1)
	delt, azim = deltaz(slat, slon, elat, elon, True)
	inc = arcsin(dtdd*r2d*v0/radius)*r2d
	toa = arcsin(dtdd*r2d*v1/(radius-edep))*r2d
	return dtdd, toa, inc, delt

def getIncTTimes(dtdict, stadict, opts):
	'Calculate incidence angles using ttimes/getime.so'
	dpvpvs = opts.dpvpvs
	vel0 = opts.vel0
	model = opts.model
	evids = sorted(dtdict.keys())
	for evid in evids:
		print('Calculate incidence angles for event : '+evid)
		evdict = dtdict[evid]
		elat, elon, edep, = evdict['event']['hypo'][:3]
		vel1 = getVel(dpvpvs, edep)
		for phase in phases:
			if phase in evdict:
				xdict, xdelay = evdict[phase]
				for sta in xdict.keys():
					slat, slon = stadict[sta][:2]
					dtdd, toa, inc, delta = ttimes(model, phase, vel0, vel1, slat, slon, elat, elon, edep)
					# replace delay time with more info from taup
					xdict[sta] = [xdict[sta], dtdd, toa, inc, delta]
	writePickle(dtdict, opts.ofilename)
	return dtdict


def getIncDict(opts):
	'Calculate incidence/take-off angles and save to dict'
	if opts.ofilename:
		stadict = readStation(opts.locsta)
		dtdict = getDelayDict(opts)
		getModel(opts)
		if opts.taup:
			dtidict = getIncTauP(dtdict, stadict, opts)
		else:
			dtidict = getIncTTimes(dtdict, stadict, opts)
	else:
		print('Read file: '+opts.ifilename)
		dtidict = readPickle(opts.ifilename)
	return dtidict

def incBins(nbin=2):
	'Create bins'
	if nbin == 4:
		incs = linspace(13,25,nbin+1)
		legs = ['13-16deg','16-19deg','19-22deg','22-25deg']
	elif nbin == 6:
		incs = linspace(13,25,nbin+1)
		legs = ['13-15deg','15-17deg','17-19deg','19-21deg','21-23deg','23-25deg']
	elif nbin == 7:
		incs = linspace(12,26,nbin+1)
		legs = ['12-14deg','14-16deg','16-18deg','18-20deg','20-22deg','22-24deg','24-26deg']
	elif nbin == 10:
		incs = linspace(14,24,nbin+1)
		legs = ['14-15deg','15-16deg','16-17deg','17-18deg','18-19deg','19-20deg','20-21deg','21-22deg','22-23deg','23-24deg']
	elif nbin == 1:
		incs = linspace(14,24,nbin+1)
		legs = ['14-24deg']
	elif nbin == 2:
		#incs = linspace(14,24,nbin+1)
		#legs = ['14-19deg','19-24deg']
		incs = linspace(14,34,nbin+1)
		legs = ['14-24deg','24-34deg']
	elif nbin == 3:
		incs = linspace(13,25,nbin+1)
		legs = ['13-17deg','17-21deg','21-25deg']
	else:
		print 'unknown nbin ', nbin
		sys.exit()
	return incs, legs

def incStats(dtidict):
	print('Calculate incidence angles stats')
	incs = {}
	for phase in phases: 
		incs[phase] = []
	evids = sorted(dtidict.keys())
	for evid in evids:
		print('read evid : ' + evid)
		for phase in phases:
			if phase in dtidict[evid]:
				xdict, xdelay = dtidict[evid][phase]
				for sta in xdict.keys():
					inc = xdict[sta][2]
					incs[phase].append(inc)
	figure()
	for phase in phases:
		ii = incs[phase]
		print('{:s} : median/mean/std/min/max : {:.1f} {:.1f} {:.1f} {:.1f} '.format(phase, median(ii), mean(ii), std(ii), min(ii), max(ii) ))
		hist(ii, histtype='step', label=phase)
	legend()
	show()


def incBinDelay(dtidict, stadicts, opts):
	'Bin delay times according to incidence angles for both E/W stations and P/S waves'
	absdt = opts.absdt
	incs = opts.incs
	nbin = opts.nbin
	stawest, staeast = stadicts
	ewdicts = {}
	for phase in phases:
		ewdicts[phase] = [ ([],[])  for i in range(nbin) ]
	evids = sorted(dtidict.keys())
	for evid in evids:
		print('read evid : ' + evid)
		for phase in phases:
			if phase in dtidict[evid]:
				xdict, xdelay = dtidict[evid][phase]
				if not absdt: xdelay = 0
				for sta in xdict.keys():
					dt = xdict[sta][0] + xdelay
					inc = xdict[sta][2]
					for i in range(nbin):
						if inc >= incs[i] and inc < incs[i+1]:
							print('found inc {:.1f} between ({:.1f} {:.1f}) of {:d}-th bin'.format(inc, incs[i], incs[i+1], i))
							break
					if sta in stawest:
						ewdicts[phase][i][0].append(dt)
					else:
						ewdicts[phase][i][1].append(dt)
	return ewdicts


def plotHist2(ewdicts, opts):
	'Plot E/W histograms in two columns.'
	nbin = opts.nbin
	cols = 'rgbkcy'
	figure(figsize=(10, 10))
	subplots_adjust(left=.1, right=.98, bottom=.05, top=0.96)
	bins = opts.bins
	legs = opts.legs
	axs = []
	for i in range(2):
		wax = subplot(2, 2, 2*i+1)
		eax = subplot(2, 2, 2*i+2, sharex=wax, sharey=wax)
		axs.append([wax, eax])
	for i in range(2):
		phase = phases[i]
		axw, axe = axs[i]
		wtrans = transforms.blended_transform_factory(axw.transAxes, axw.transAxes)
		etrans = transforms.blended_transform_factory(axe.transAxes, axe.transAxes)
		for j in range(nbin):
			wdt, edt = ewdicts[phase][j]
			col = cols[j]
			if wdt != []:
				axw.hist(wdt, bins, color=col, alpha=.5, histtype='stepfilled', label=legs[j])
			if edt != []:
				axe.hist(edt, bins, color=col, alpha=.5, histtype='stepfilled', label=legs[j])
		axw.legend()
		axe.legend()
	axs[0][0].set_title('West')
	axs[0][1].set_title('East')
	axs[0][0].set_ylabel('P Histogram')
	axs[1][0].set_ylabel('S Histogram')

	if opts.absdt:
		fignm = 'dtinc-hist2-abs-nbin{:d}.png'.format(nbin)
	else:
		fignm = 'dtinc-hist2-rel-ninb{:d}.png'.format(nbin)
	fignm = fignm.replace('png', opts.figfmt)
	saveFigure(fignm, opts)

def plotHist1(ewdicts, opts):
	'Plot E/W histograms in one column (P left S right).'
	nbin = opts.nbin
	cols = 'rbg'
	figure(figsize=opts.figsize)
	subplots_adjust(left=.08, right=.98, bottom=.05, top=0.96, wspace=.12)
	rcParams['legend.fontsize'] = 13
	tbins = opts.tbins
	legs = opts.legs
	ewlegs = 'West', 'East'
	ewys = 0.97, 0.88
	axs = []
	for i in range(nbin):
		axa = subplot(nbin, 2, 2*i+1)
		axb = subplot(nbin, 2, 2*i+2)
		axs.append([axa, axb])
	for i in range(nbin): # inc bins
		for j in range(2): # phase
			ax = axs[i][j]
			trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
			phase = phases[j]
			for k in range(2): # W/E
				dt = ewdicts[phase][i][k]
				ew = ewlegs[k]
				print('Incidence angle {:s} at {:s}: {:7d} {:s} delays.'.format(legs[i], ew, len(dt), phase))
				col = cols[k]
				if dt != []:
					ax.hist(dt, tbins[j], color=col, alpha=.9, histtype='step', label=ew, lw=2)
					mdt, sdt = mean(dt), std(dt)
					x0, x1 = mdt-sdt, mdt+sdt
					ax.axvline(x=mdt, color=col, ls='--', lw=2)
					ax.axvline(x=mdt-sdt, color=col, ls=':', lw=1)
					ax.axvline(x=mdt+sdt, color=col, ls=':', lw=1)
					ax.text(0.95, ewys[k], r'$\sigma_{:s}$={:.2f} s'.format(ew[0], sdt), 
						transform=trans, ha='right', va='top', size=14)
			ax.xaxis.set_major_locator(opts.majorLocators[j])
			ax.xaxis.set_minor_locator(opts.minorLocators[j])
			ax.xaxis.set_major_formatter(opts.majorFormatter)
			#ax.set_xticks(opts.ticks[j])
			ax.set_xlim(opts.axlims[j])
			yy = ax.get_ylim()
			yy = axLimit(yy, 0.03)
			ax.set_ylim(yy)
			ax.axhline(y=0, color='k', ls=':')
			leg = 'Incidence angle: {:s}'.format(legs[i][:-3]) + r'$^\circ$'
			ax.set_title(leg)
			ax.legend(loc=2)
		axs[i][0].set_ylabel('Histogram')
	axs[nbin-1][0].set_xlabel('P {:s} Delay Time [s]'.format(opts.atag))
	axs[nbin-1][1].set_xlabel('S {:s} Delay Time [s]'.format(opts.atag))

	fignm = 'dtinc-hist-nbin{:d}-{:s}.png'.format(nbin, opts.ftag)
	saveFigure(fignm, opts)


if __name__ == '__main__':

	opts, ifiles = getParams()

	phases = 'P', 'S'
	opts.nets = 'ta', 'xa', 'xr'

	# bin delay times and plot in histograms
	nbin = opts.nbin
	opts.incs, opts.legs = incBins(nbin)
	fwest = 'loc.sta.west'
	feast = 'loc.sta.east'
	opts.majorFormatter = FormatStrFormatter('%d')

	# 1-column
	if opts.absdt:
		hfile = 'ewinc-abs-nbin{:d}.pkl'.format(nbin)
		opts.ftag = 'abs'
		opts.atag = 'Absolute'
		pmin, pmax = -4, 4
		smin, smax = -10, 14
		opts.axlims = [(pmin, pmax), (smin, smax)]
		opts.tbins = [linspace(pmin,pmax,21), linspace(smin,smax,21)]
		#opts.ticks = [linspace(pmin,pmax,17), linspace(smin,smax,25)]
		opts.majorLocators = MultipleLocator(1), MultipleLocator(3)
		opts.minorLocators = MultipleLocator(.5), MultipleLocator(1)
	else:
		hfile = 'ewinc-rel-nbin{:d}.pkl'.format(nbin)
		opts.ftag = 'rel'
		opts.atag = 'Relative'
		pmin, pmax = -2.5, 2.5
		smin, smax = -7.5, 7.5
		opts.axlims = [(pmin, pmax), (smin, smax)]
		opts.tbins = [linspace(pmin,pmax,21), linspace(smin,smax,21)]
		#opts.ticks = [linspace(pmin,pmax,11), linspace(smin,smax,11)]
		opts.majorLocators = MultipleLocator(1), MultipleLocator(3)
		opts.minorLocators = MultipleLocator(.5), MultipleLocator(1)
	if nbin == 2:
		opts.figsize = (12, 10)
	#os.system('rm -rf '+hfile)
	if opts.incstats:
		dtidict = getIncDict(opts)
		incStats(dtidict)

	opts.figsize = (12, 12)
	if opts.histogram:
		if not os.path.isfile(hfile):
			dtidict = getIncDict(opts)	# calculate incidences
			stawest = readStation(fwest)
			staeast = readStation(feast)
			stadicts = [stawest, staeast]
			ewdicts = incBinDelay(dtidict, stadicts, opts)
			writePickle(ewdicts, hfile)
		else:
			print('Read file: '+hfile)
			ewdicts = readPickle(hfile)

		# 2-column
		#opts.bins = linspace(-8,8,81)
		#plotHist2(ewdicts, opts)
		plotHist1(ewdicts, opts)


