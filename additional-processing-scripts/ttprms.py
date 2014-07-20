#!/usr/bin/env python
"""
RMS of predicted-observed delays

xlou 02/06/2013

"""

import os, sys, commands
from numpy import loadtxt
from pylab import *
from optparse import OptionParser
from ttcommon import readStation, readPickle, writePickle
from ppcommon import saveFigure
from ttdict import lsq
from aimbat.xcorr import xcorr_full

def getParams():
	""" Parse arguments and options. """
	usage = "Usage: %prog [options] <corr(s)>"
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

#
#def plotrms():
#	rfile  = 'note-rms'
#	tdict = readStation(rfile)
#	ip = 1
#	fig = figure()
#	for key in sorted(tdict):
#		val = tdict[key][ip]
#		axhline(y=val)
#	ylabel('Delay Time RMS [s]')
#	fig.canvas.manager.window.focus_force()
#	#fig.canvas.manager.window.activateWindow()
#	show()
#
#def numsta():
#	# number of stations from actually measured stations (same as padict)
#	alist = sorted(readStation('stadt-sol9-s'))
#	for prov in sorted(ttdict):
#		slist = sorted(readStation(stadir+prov))
#		ns = len(list(set(alist).intersection(slist)))
#		print prov, ns
#
#def plotprms(provs, phase='S'):
#	# geo provinces areas:
#	padict = readStation('locsta-area')
#	#ttfile = 'gprov-s-avstd' 
#	ttfile = 'gprov-{:s}-avstd'.format(phase.lower())
#	ttdict = readStation(ttfile)
#	# delay, area, nsta
#	tspa = array([ [ttdict[prov][1], padict[prov][0], padict[prov][1] ]  for prov in provs ])
#	tt = tspa[:,0]
#	pa = tspa[:,1]
#	ns = tspa[:,2]
#
#	if opts.normarea:
#		pa /= ns
#		fignm = 'gaprov-{:s}.png'.format(phase.lower())
#	else:
#		fignm = 'gprov-{:s}.png'.format(phase.lower())
#	namcols = [ pidict[prov][1:3] for prov in provs ] 
#
#	figure(figsize=(9,7))
#	subplots_adjust(left=0.1, right=0.96, top=0.72, bottom=0.09)
#	for i in range(len(provs)):
#		nam, col = namcols[i]
#		plot(pa[i], tt[i], marker='s', ls='None', color=col, label=nam, ms=12)
#	ylabel('Standard Deviation of {:s} Delays [s]'.format(phase))
#	if opts.normarea:
#		xlabel(r'NArea of Geological Provinces Norm by #sta [$10^4$km$^2$/nsta]')
#	else:
#		xlabel(r'Area of Geological Provinces [$10^4$km$^2$]')
#	legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=4, numpoints=1,
#		ncol=3, mode="expand", borderaxespad=0.)
##	subplot(121)
##	plot(pa, tt, 's')
##	subplot(122)
##	plot(pa/ns, tt, 's')
##
#	# fit without mrm
##	provs.remove('mrm')
##	tspa = array([ [ttdict[prov][1], padict[prov][0]/padict[prov][1]]  for prov in provs ])
##	x = tspa[:,1] 
##	y = tspa[:,0]
##	a, b, sa, sb = lsq(x, y)
##	px = array([0, 1])
##	py = a*px + b
##	plot(px, py, '-')
#	return fignm
#
#



def getDelay(dtfile, evids, dtag=None):
	"""
	get observed (dtag=None) or predicted (dtag=d7) delays, mean removed
	Because procx.py limit min number of measurements, so that three events are not included 
	  in ray tracing and thus predicting. Need to give events.
	"""
	if dtag is None:
		dtdict = readPickle(dtfile)
	else:
		dtdict = readPickle(dtfile)[dtag]
	alldt = []
	#evids = sorted(dtdict)
	for evid in evids:
		evdict = dtdict[evid]
		if phase in evdict:
			xdict, xdelay = evdict[phase]
			if not absdt: xdelay = 0
			alldt += [ xdict[sta]+xdelay  for sta in sorted(xdict) ]
	alldt = array(alldt)
	mdt = mean(alldt)
	alldt -= mdt
	return alldt, mdt


def plotDelayStaave(dtag):
	odtfile = 'stadt-sol9-' + phase.lower()
	odtdict = readStation(odtfile)
	ostas = sorted(odtdict)
	aoii = arange(len(ostas))
	aodt = array([ odtdict[sta][2]  for sta in ostas ])
	print('predicted - observed: dave, drms, ccor ')
	ofilename = 'dtdiff-staave-' + dtag
	ofile = open(ofilename, 'w')
	ofile.write('#ModPred-Obs  dave    drms rms(rmean) ccor \n')
	mdict = {}
	for mod in mods:
		mfile = '../{:s}/pdt-abs-{:s}-{:s}'.format(mod, phase.lower(), dtag)
		pdtdict = readStation(mfile)
		stas = sorted(pdtdict)
		inds = [ ostas.index(sta)  for sta in stas ]
		odt = array([ odtdict[sta][2]  for sta in stas ])
		pdt = array([ pdtdict[sta][2]  for sta in stas ])
		odm = mean(odt)
		pdm = mean(pdt)
		dave = pdm - odm
		drms = sqrt(mean((pdt-odt)**2))
		mrms = sqrt(mean((pdt-odt-dave)**2))
		ccor = corrcoef(odt, pdt)[0][1]
		#print('{:10s}  {:6.2f}  {:6.2f}  {:6.2f}  {:6.2f}'.format(mod, dave, drms, mrms, ccor))
		ofile.write('{:10s}  {:6.2f}  {:6.2f}  {:6.2f}  {:6.2f} \n'.format(mod, dave, drms, mrms, ccor))
		mdict[mod] = inds, pdt
	print('Save to file: '+ofilename)
	ofile.close()
	# plot obs
	figure(figsize=(20,6))
	subplots_adjust(left=.04, right=.9, bottom=.1, top=0.96)
	plot(aoii, aodt, label='obs')
	for mod in mods:
		inds, pdt = mdict[mod]
		plot(inds, pdt, label=mod)
	#legend()
	legend(bbox_to_anchor=(1.007, 0, 0.1, .1), loc=4, numpoints=1,
		ncol=1, mode="expand", borderaxespad=0.)
	text(0.02, 0.95, dtag, transform=gca().transAxes, fontsize=20,
		ha='left')
	xlabel('Station number')
	ylabel('Sta-ave delay time [s]')
	fignm = ofilename + '.png'
	return fignm

def getDelayStaall(obsfile, ofilename):
	if not os.path.isfile(ofilename):
		ofile = open(ofilename, 'w')
		ofile.write('#Pred-Obs    Omean   Pmean   dave     drms dmrms(rmean) ccor \n')
		# give events because not all events predicted
		evids = [ line.split()[0]  for line in open('../na04/ref.teqs').readlines() ]
		# observed:
		odt, odm = getDelay(obsfile, evids)
		# predicted:
		fmt = '{:10s} ' + ' {:6.2f} '*6 + '\n'
		for mod in mods:
			mfile = '../{:s}/pdtdicts.pkl'.format(mod)
			pdt, pdm = getDelay(mfile, evids, dtag)
			dave = pdm - odm
			drms = sqrt(mean((pdt-odt)**2))
			mrms = sqrt(mean((pdt-odt-dave)**2))
			ccor = corrcoef(odt, pdt)[0][1]
			ofile.write(fmt.format(mod, odm, pdm, dave, drms, mrms, ccor))
		ofile.close()
		print('Save to file: '+ofilename)
	mdict = readStation(ofilename)
	return mdict


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

	#for phase in 'P', 'S':
	#	fignm = plotprms(provs, phase)
	#	saveFigure(fignm ,opts)

	modfile = '../modinds'
	mods = [ line.split()[1]  for line in open(modfile).readlines() ]
	phase = 'S'
	absdt = True


	# sta-average
	dtag = 'da'
	dtag = 'd7'
	dtags = 'd7', #'da'
	if opts.staave:
		for dtag in dtags:
			fignm = plotDelayStaave(dtag)
			saveFigure(fignm, opts)

	# all measurements
	ctags = ifiles
	dtag = 'da'
	if opts.staall:
		#ctag = opts.correction
		for ctag in ctags:
			if ctag == 'raw' : # no crust/event correction
				obsfile = 'rawdtdict.pkl'
				ofilename = 'dtdiff-staall-raw-' + dtag
			elif ctag == 'cc': # crust correction
				obsfile = 'dtdict.pkl'
				ofilename = 'dtdiff-staall-cc-' + dtag
			elif ctag == 'ec': # crust+event correction
				obsfile = 'erdtdict.pkl'
				ofilename = 'dtdiff-staall-ec-' + dtag
			ofilename = 'dtdiff-staall-{:s}-{:s}'.format(dtag, ctag)
			mdict = getDelayStaall(obsfile, ofilename)


	sys.exit()

