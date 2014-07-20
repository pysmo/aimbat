#!/usr/bin/env python
"""
residual sphere (az, delta)

xlou 02/06/2013

"""

import os, sys, commands
from pylab import *
from optparse import OptionParser
from ttcommon import readStation, readPickle, writePickle, getVel0, getVel

from ppcommon import saveFigure
from getime import getime
from deltaz import deltaz


def getParams():
	""" Parse arguments and options. """
	usage = "Usage: %prog [options] <sta(s)>"
	parser = OptionParser(usage=usage)
	ojinv = 'out.jinv'
	parser.set_defaults(ojinv=ojinv)
	parser.add_option('-g', '--savefig', dest='savefig', type='str', 
		help='Save figure instead of showing (png/pdf).')
	parser.add_option('-a', '--staall', action="store_true", dest='staall',
		help='All measurements')
	parser.add_option('-m', '--staave', action="store_true", dest='staave',
		help='Station average')
#	parser.add_option('-c', '--correction', dest='correction',
#		help='Correction of delays: raw/cc/ec')

	opts, files = parser.parse_args(sys.argv[1:])
	return opts, files


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
	return dtdd, toa, inc, delt, azim

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


def getIncTTimes(edtdict, odtdict, stadict, opts):
	'Calculate incidence angles using ttimes/getime.so'
	ssdict = {}
	for sta in stas:
		ssdict[sta] = {}
		for phase in phases:
			ssdict[sta][phase] = []
	dpvpvs = opts.dpvpvs
	vel0 = opts.vel0
	model = opts.model
	evids = sorted(edtdict)
	for evid in evids:
		print('Calculate incidence angles for event : '+evid)
		evdict = edtdict[evid]
		elat, elon, edep, = odtdict[evid]['event']['hypo'][:3]
		vel1 = getVel(dpvpvs, edep)
		for phase in phases:
			if phase in evdict:
				xdict, xdelay = evdict[phase]
				if not absdt: xdelay = 0
				for sta in stas:
					if sta in xdict:
						slat, slon = stadict[sta][:2]
						dtdd, toa, inc, delta, azim = ttimes(model, phase, vel0, vel1, slat, slon, elat, elon, edep)
						dt = xdict[sta] + xdelay
						ss = [dt, dtdd, toa, inc, delta, azim]
						ssdict[sta][phase].append(ss)
	fmt = '{:6.2f} {:6.2f} {:6.1f} {:6.1f} {:6.1f} {:6.1f} \n'
	for sta in stas:
		for phase in phases:
			ofile = 'stares-{:s}-{:s}'.format(sta.split('.')[1].lower(), phase.lower())
			with open(ofile, 'w') as f:
				f.write('# dt    dtdd    toa   inc    delta azimuth\n')
				for ss in ssdict[sta][phase]:
					f.write(fmt.format(*ss))


def getInc():
	locsta = 'loc.sta.all'
	stadict = readStation(locsta)
	odtdict = readPickle('../dtdict.pkl')
	edtdict = readPickle('erdtdict.pkl')

	getModel(opts)
	getIncTTimes(edtdict, odtdict, stadict, opts)

def plotRes(sta, phase, rname='dist'):
	clabel = '{:s} Delay [s]'.format(phase)
	sfile = 'stares-{:s}-{:s}'.format(sta.split('.')[1].lower(), phase.lower())
	vals = loadtxt(sfile, comments='#')
	dt, dtdd, toa, inc, delt, azim = [ vals[:,i]  for i in range(len(vals[0])) ]
	if rname == 'dist':
		r = delt
		rmax = 100
	elif rname == 'inc':
		r = inc
		rmax = 30 
	fig = figure(figsize=(8,6))
	vmin, vmax = opts.vlims
	ax = fig.add_subplot(111, polar=True)
	scatter(90-azim, r, c=dt, cmap=cmap, vmin=vmin, vmax=vmax, s=49)
	cbar = colorbar(orientation='vertical', pad=.1, aspect=20., shrink=0.95)
	cbar.set_label(clabel)
	ax.set_rmax(rmax)
	ax.text(-0.07, -0.07, sta, transform=ax.transAxes, 
		ha='left', va='bottom', size=20)
	ax.text(0.87, -0.07, 'r='+rname, transform=ax.transAxes, 
		ha='left', va='bottom', size=20)
	fignm = sfile + '-' + rname + '.png' 
	return fignm

if __name__ == '__main__':

	opts, stas = getParams()

	rcParams['legend.fontsize'] = 14
	rcParams['axes.labelsize'] = 'large'
	rcParams['xtick.major.size'] = 6
	rcParams['xtick.minor.size'] = 4
	rcParams['xtick.labelsize'] = 'large'
	rcParams['ytick.major.size'] = 6
	rcParams['ytick.minor.size'] = 4
	rcParams['ytick.labelsize'] = 'large'
	rcParams['axes.titlesize'] = 'x-large'

	absdt = True
	opts.refmodel = 'iasp91' 

	stas = ['TA.H17A', 'US.LKWY']
	phases = ['P', 'S']

	#getInc()

	ckey = 'hsv'
	ckey = 'RdBu_r'
	cdict = cm.datad[ckey]
	cmap = matplotlib.colors.LinearSegmentedColormap(ckey, cdict)


	# plot
	sta = stas[0]
	phase = phases[1]	
	opts.vlims = 0, 10

	for rname in 'dist', 'inc':
		for sta in stas:
			fignm = plotRes(sta, phase, rname)
			saveFigure(fignm, opts)

