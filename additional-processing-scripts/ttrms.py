#!/usr/bin/env python
"""
Plot delay rms

xlou 01/31/2013
"""

import os, sys, commands
from numpy import loadtxt
from pylab import *
from optparse import OptionParser
from ttcommon import readStation
from ppcommon import saveFigure
from ttdict import lsq

def getParams():
	""" Parse arguments and options. """
	usage = "Usage: %prog [options] <file(s)>"
	parser = OptionParser(usage=usage)
	ojinv = 'out.jinv'
	parser.set_defaults(ojinv=ojinv)
	parser.add_option('-g', '--savefig', dest='savefig', type='str', 
		help='Save figure instead of showing (png/pdf).')
#	parser.add_option('-o', '--ojinv',  dest='ojinv', type='str',
#		help='Output file of jinv (input for this program).')
#	parser.add_option('-e', '--einv', action="store_true", dest='einv',
#		help='Compare dmeans with event terms')
#	parser.add_option('-j', '--jinv', action="store_true", dest='jinv',
#		help='Compare jinv results')
	opts, files = parser.parse_args(sys.argv[1:])
	return opts, files


def plotrms():
	rfile  = 'note-rms'
	tdict = readStation(rfile)
	ip = 1
	fig = figure()
	for key in sorted(tdict):
		val = tdict[key][ip]
		axhline(y=val)
	ylabel('Delay Time RMS [s]')
	fig.canvas.manager.window.focus_force()
	#fig.canvas.manager.window.activateWindow()
	show()

def numsta():
	# number of stations from actually measured stations (same as padict)
	alist = sorted(readStation('stadt-sol9-s'))
	for prov in sorted(ttdict):
		slist = sorted(readStation(stadir+prov))
		ns = len(list(set(alist).intersection(slist)))
		print prov, ns

def plotprms(provs, phase='S'):
	# geo provinces areas:
	padict = readStation('locsta-area')
	#ttfile = 'gprov-s-avstd' 
	ttfile = 'gprov-{:s}-avstd'.format(phase.lower())
	ttdict = readStation(ttfile)
	# delay, area, nsta
	tspa = array([ [ttdict[prov][1], padict[prov][0], padict[prov][1] ]  for prov in provs ])
	tt = tspa[:,0]
	pa = tspa[:,1]
	ns = tspa[:,2]

	if opts.normarea:
		pa /= ns
		fignm = 'gaprov-{:s}.png'.format(phase.lower())
	else:
		fignm = 'gprov-{:s}.png'.format(phase.lower())
	namcols = [ pidict[prov][1:3] for prov in provs ] 

	figure(figsize=(9,7))
	subplots_adjust(left=0.1, right=0.96, top=0.72, bottom=0.09)
	for i in range(len(provs)):
		nam, col = namcols[i]
		plot(pa[i], tt[i], marker='s', ls='None', color=col, label=nam, ms=12)
	ylabel('Standard Deviation of {:s} Delays [s]'.format(phase))
	if opts.normarea:
		xlabel(r'NArea of Geological Provinces Norm by #sta [$10^4$km$^2$/nsta]')
	else:
		xlabel(r'Area of Geological Provinces [$10^4$km$^2$]')
	legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=4, numpoints=1,
		ncol=3, mode="expand", borderaxespad=0.)
#	subplot(121)
#	plot(pa, tt, 's')
#	subplot(122)
#	plot(pa/ns, tt, 's')
#
	# fit without mrm
#	provs.remove('mrm')
#	tspa = array([ [ttdict[prov][1], padict[prov][0]/padict[prov][1]]  for prov in provs ])
#	x = tspa[:,1] 
#	y = tspa[:,0]
#	a, b, sa, sb = lsq(x, y)
#	px = array([0, 1])
#	py = a*px + b
#	plot(px, py, '-')
	return fignm


if __name__ == '__main__':

	opts, ifiles = getParams()

	rcParams['legend.fontsize'] = 14
	rcParams['axes.labelsize'] = 'large'
	rcParams['xtick.major.size'] = 6
	rcParams['xtick.minor.size'] = 4
	rcParams['xtick.labelsize'] = 'large'
	rcParams['ytick.major.size'] = 6
	rcParams['ytick.minor.size'] = 4
	rcParams['ytick.labelsize'] = 'large'
	rcParams['axes.titlesize'] = 'x-large'

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

	stadir = os.environ['HOME'] + '/work/na/sod/tamw60pkl/evsta/loc.sta-'
	wprovs = 'pbp', 'csm', 'cbp', 'cop', 'bar', 'nrm', 'mrm', 'wyb', 'srm'
	eprovs = 'super', 'grp', 'cel', 'ilp', 'inthl', 'appal', 'coast', 
	provs = wprovs + eprovs

	opts.normarea = True

	for phase in 'P', 'S':
		fignm = plotprms(provs, phase)
		saveFigure(fignm ,opts)



