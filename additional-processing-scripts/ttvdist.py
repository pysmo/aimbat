#!/usr/bin/env python
"""
File: ttdistv.py

MCCC delay times variations over distance.

xlou 03/21/2012
"""

from pylab import *
import os, sys, glob, string
import matplotlib.transforms as transforms
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from mpl_toolkits.basemap import Basemap
from mpl_toolkits.mplot3d import axes3d
from matplotlib.collections import PolyCollection
from matplotlib.colors import colorConverter
from ttcommon import readStation, readPickle, writePickle
from ppcommon import saveFigure, readboundary
from ttdict import getParser, delKeys, getDict, delayStats 
from deltaz import deltaz, azdelt
from etopo5 import etopo5

d2k = 6371*pi/180	# deg to km
d2r = pi/180		# deg to rad

def getParams():
	""" Parse arguments and options from command line. """
	parser = getParser()
	nstamin = 1
	parser.set_defaults(nstamin=nstamin)
	parser.add_option('-n', '--nstamin',  dest='nstamin', type='int',
		help='Minimun number of measurements for each event.')
	#parser.add_option('-s', '--stadistfile',  dest='stadistfile', type='str',
	#	help='Read station distances from file. Give all to read all.')
	parser.add_option('-w', '--writedist', dest='writedist', action="store_true", 
		help='Write station distances to files')
	parser.add_option('-d', '--getdd', dest='getdd', action="store_true", 
		help='Get dtdist.')
	parser.add_option('-p', '--plotdd', dest='plotdd', action="store_true", 
		help='Plot dtdist.')
	parser.add_option('-1', '--onephase', dest='onephase', action="store_true", 
		help='Plot one phase a time.')
	parser.add_option('-3', '--plot3d', dest='plot3d', action="store_true", 
		help='Plot 3d.')
	parser.add_option('-t', '--ta', action="store_true", dest='ta',
		help='For TA A-Z-0-9 lines. Otherwise use all stations.')
	parser.add_option('-I', '--indexing',  dest='indexing', type='str',
		help='Indexing for subplot: a b c ')
	opts, files = parser.parse_args(sys.argv[1:])
	return opts, files

def saveStation(sdict, ofilename):
	""" Write station dict to file.
		Item of the dict has at least three fields such as lat/lon/elv and lat/lon/delay/std.
		Format is automatically adjusted according to number of fields.
	"""
	##sort by first value
	sitems = sorted(sdict.items(), key=lambda x: x[1][0])
	values = [ [item[0],]+item[1] for item in sitems ]
	# convert dict to list
	#values = [ [sta,] + sdict[sta]  for sta in sorted(sdict.keys()) ]

	fmt = ' {0:<9s} {1:10.5f} {2:11.5f} '
	nfmt = len(fmt.split())
	nval = len(values[0])
	for i in range(nfmt, nval):
		fmt += '{' + str(i) + ':8.3f} '
	fmt += '\n'
	print('Save dict to file "{0:s}" using format: {1:s}'.format(ofilename,fmt))
	ofile = open(ofilename, 'w')
	for line in values:
		ofile.write(fmt.format(*line))
	ofile.close()


def getDistOld(sdict, uselon=True):
	""" 
	For each station in sdict, calculate distance to a reference station.
	Reference station is selected by the smallest lat or lon.
	Distance are both in km and deg for saveStation().
	"""
	if uselon:
		ind = 1
	else:
		ind = 0
	vmin = 400
	for sta in sdict.keys():
		if sdict[sta][ind] < vmin:
			vmin = sdict[sta][ind]
			sta0 = sta
	lat0, lon0 = sdict[sta0][:2]
	d2k = 6371*pi/180	# deg to km
	for sta in sdict.keys():
		lat1, lon1 = sdict[sta][:2]
		dist, azim = deltaz(lat0, lon0, lat1, lon1)
		if isnan(dist):
			if lat0 == lat1 and lon0 == lon1:
				dist = .0
			else:
				print('NaN detected. Exit')
				sys.exit()
		#sdict[sta] = [dist*d2k, dist]
		sdict[sta] = [dist*d2k, dist, lat1, lon1]
	return sdict 

def getDistProj(sdict, uselon=True, proj=True):
	"""
	For each station in sdict, calculate (projected) distance along a profile.
	The two ending stations of the profile are determined from min/max of lat or lon.
	Distance are both in km and deg for saveStation().
	"""
	if uselon:
		ind = 1
	else:
		ind = 0
	vmin = 400
	vmax = -400
	for sta in sdict.keys():
		if sdict[sta][ind] < vmin:
			vmin = sdict[sta][ind]
			sta0 = sta
		if sdict[sta][ind] > vmax:
			vmax = sdict[sta][ind]
			sta2 = sta
	# get two ending points: 
	print('Two ending stations: {:s} + {:s} '.format(sta0, sta2))
	lat0, lon0 = sdict[sta0][:2]
	lat2, lon2 = sdict[sta2][:2]
	d2k = 6371*pi/180	# deg to km
	d2r = pi/180		# deg to rad
	dist0, azim0 = deltaz(lat0, lon0, lat2, lon2)
	for sta in sdict.keys():
		lat1, lon1 = sdict[sta][:2]
		dist, azim = deltaz(lat0, lon0, lat1, lon1)
		if isnan(dist):
			if lat0 == lat1 and lon0 == lon1:
				dist = .0
			else:
				print('NaN detected. Exit')
				sys.exit()
		if proj: # project dist to the profile
			#print ('Projected distance difference:  {:10s} {:6.1f}'.format(sta, dist*(1-cos((azim-azim0)*d2r))*d2k))
			dist *= cos((azim-azim0)*d2r)
		sdict[sta] = [dist*d2k, dist, lat1, lon1]
	# get topo projection
	#dd = 0.1 # deg
	#dists = arange(-10*dd, dist0+dd*11, dd)
	dd = 5 # km
	dists = arange( -20*dd, dist0*d2k+dd*21, dd)
	tdict = {}
	for i in range(len(dists)):
		d = dists[i]/d2k
		lat1, lon1 = azdelt(lat0, lon0, d, azim0)
		topo = etopo5(lat1, lon1)
		ds = '{:0>5d}'.format(i)
		tdict[ds] = [d*d2k, topo*.001]
	return sdict, tdict

def sortDist(sdict):
	""" 
	Sort station dict by distance and return list.
	Only keep the km distance.
	"""
	slist = sorted(sdict)
	dlist = [ sdict[sta][0]  for sta in slist ]
	inds = argsort(array(dlist))
	sdlist = [ [slist[i], dlist[i]]  for i in inds ]
	return sdlist

def delayDist(dtdict, sdlist, absdt, shiftps=(0,0), nstamin=1):
	"""
	Get delay time variation in distances for each event.
	"""
	print('Get delay time variation in distances for each event. Min nsta: '+str(nstamin))
	phs = ['P', 'S']
	dddict = {}	# individual delay measurments
	dmdict = {}	# mean delay
	for sta, dist in sdlist:
		dmdict[sta] = [ [], [] ]
	for evid in sorted(dtdict):
		evdict = dtdict[evid]
	 	dps = [None, None]
		for i in range(2):
			ph = phs[i]
			if ph in evdict:
				dt = []
				xdict, xdelay = evdict[ph]
				if not absdt: xdelay = 0
				for sta, dist in sdlist:
					if sta in xdict:
						t = xdict[sta] + xdelay
						dt.append([dist, t])
						dmdict[sta][i].append(t)
				if len(dt) >= nstamin:
					dt = array(dt)
					dt[:,1] += shiftps[i]
					dps[i] = dt
		dddict[evid] = dps
	dtp, dts = [], []
	sdlistnew = []
	for sta, dist in sdlist:
		tp, ts = dmdict[sta]
		if len(tp) >= 3 and len(ts) >= 3:
			dtp.append([dist, mean(tp), std(tp)])
			dts.append([dist, mean(ts), std(ts)])
			sdlistnew.append([sta, dist])
		else:
			print('*** Less than {:d} measurements, station removed: {:s}'.format(3,sta))
	dtp = array(dtp)
	dts = array(dts)
	dtp[:,1] += shiftps[0]
	dts[:,1] += shiftps[1]
	dtmean = dtp, dts 
	return dddict, dtmean, sdlistnew


def delayDistPlot(dddict, dtmean, sdlist, axs, opts):
	' Plot delay variation over distances '
	phs = ['P', 'S']
	np = len(phs)
	if opts.absdt:
		key = 'Absolute '
	else:
		key = 'Relative '
	for i in range(np):
		axs[i].axhline(y=0, ls='-', color='k', lw=2)
		axs[i].plot([10,20],[0,0], color=opts.pcol, marker='.', ls='-', ms=opts.pms, alpha=opts.alpha,
			label='Measurements')
		axs[i].set_ylabel(key + phs[i] + ' Delay Time [s]')
	axs[i].set_xlabel('Distance [km]')
	# meansurements
	for evid in dddict.keys():
		dps = dddict[evid]
		if opts.randcol:
			col = rand(3)
		else:
			col = opts.pcol 
		for i in range(np):
			dt = dps[i]
			if dt is not None:
				axs[i].plot(dt[:,0], dt[:,1], color=col, marker='.', ls='-', ms=opts.pms, alpha=opts.alpha)
	# mean
	colsym = opts.mcol + opts.msym
	for i in range(np):
		axs[i].plot(dtmean[i][:,0], dtmean[i][:,1], colsym, ms=opts.mms, mew=opts.mew, label='Station-average')
		if opts.ylims[i] is not None:
			axs[i].set_ylim(opts.ylims[i])
	if opts.xlim is not None:
		axs[i].set_xlim(opts.xlim)
	#axs[i].legend(loc=3)
	axs[i].legend(bbox_to_anchor=(0, -0.01), loc=2, borderaxespad=0., shadow=True, fancybox=True, handlelength=3, numpoints=1)
	#axs[0].legend(bbox_to_anchor=(0.5, 1.01), loc=8, borderaxespad=0., shadow=True, fancybox=True, handlelength=3, numpoints=1)
	# label stations
	ax = axs[0]
	trans = transforms.blended_transform_factory(ax.transData, ax.transAxes)
	for sd in sdlist[0], sdlist[-1]:
		sta, dist = sd
		ax.plot(dist, .97, 'k^', ms=9, transform=trans)
		ax.text(dist, 1.03, sta, transform=trans, va='bottom', ha='center', size=11)	


def saveMean(sdlist, dtmean, ofile):
	'save delay means to file'
	sddict = {}
	for i in range(len(sdlist)):
		sta, dist = sdlist[i]
		tp, ts = dtmean
		mtp, stp = tp[i,1:3]
		mts, sts = ts[i,1:3]
	#for sd, mtp, mts in zip(sdlist, dtmean[0][:,1], dtmean[1][:,1]):
	#	sta, dist = sd
	#	sddict[sta] = [dist, mtp, mts]
		sddict[sta] = [dist, mtp, mts, stp, sts]
		print(sta, dist, mtp, mts, stp, sts)
	saveStation(sddict, ofile)

def delayDistPlotRun(dtdict, sdfile, opts):	
	'Run delayDistPlot '
	tpfile = sdfile + '-topo'
	vals = loadtxt(tpfile, usecols=(1,2))
	dists = vals[:,0]
	topos = vals[:,1]

	dddict, dtmean, sdlist, ftag = delayDistGet(dtdict, sdfile, opts)

	fig = figure(figsize=(7, 8))
	ax0 = fig.add_subplot(2, 1, 1)
	ax1 = fig.add_subplot(2, 1, 2, sharex=ax0)
	subplots_adjust(left=.1, right=.95, bottom=.08, top=0.86, hspace=.08)
	rcParams['legend.fontsize'] = 9
	# plot topo
	ax = fig.add_axes([0.1, 0.92, 0.85, 0.065], sharex=ax0)
	axs = [ax0, ax1, ax]
	ax.plot(dists, topos, 'k-')
	zz = zeros(len(dists))
	ax.fill_between(dists, zz, topos, color='k', alpha=.3)
	tmin, tmax = min(topos), max(topos)
	dt = (tmax - tmin)*.2
	ax.set_ylim(tmin-dt, tmax+dt)
	ax.set_yticks([])
	ax.set_ylabel('Topo')
	# plot dt dist
	if opts.blackwhite:
		opts.randcol = False
	else:
		opts.randcol = True
	opts.pcol = 'k'
	opts.pms = 4
	opts.mcol = 'k'
	opts.msym = '+'
	opts.mms = 11
	opts.msym = '*'
	opts.mew = 2
	opts.alpha = .4
	if opts.blackwhite:
		opts.alpha = .2
		opts.alpha = .4

	opts.xlim = None
	opts.xlim = -100, sdlist[-1][1] + 100
	delayDistPlot(dddict, dtmean, sdlist, axs, opts)

	# indexing
	if opts.indexing is not None:
		#ax = ax0
		tt = '(' + opts.indexing + ')'
		trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
		#ax.text(-.05, 1.1, tt, transform=trans, va='center', ha='right', size=16)	
		ax.text(-.06, 1.1, tt, transform=trans, va='top', ha='right', size=16)	

	key = '-'.join(sdfile.split('/')[-1].split('.'))
	if opts.randcol:
		fignm = odir + 'ddline-rc-' + ftag + key + '.png'
	else:
		fignm = odir + 'ddline-kw-' + ftag + key + '.png'
	saveFigure(fignm, opts)



####### new #######
def delayDistGet(dtdict, sdfile, opts):
	'Get delay dists and save to pkl.'
	if opts.rmean:
		ftag = 'm'
	else:
		ftag = ''
	if opts.absdt:
		ftag += 'abs-'
	else:
		ftag += 'rel-'
	mfile = sdfile + '-' + ftag[:-1]
	afile = mfile + '.pkl'
	if not os.path.isfile(afile):
		sdict = readStation(sdfile)
		sdlist = sortDist(sdict)
		dddict, dtmean, sdlist = delayDist(dtdict, sdlist, opts.absdt, opts.shiftps, opts.nstamin)
		writePickle((dddict, dtmean, sdlist, ftag), afile)
		saveMean(sdlist, dtmean, mfile)
	else:
		dddict, dtmean, sdlist, ftag = readPickle(afile)
	return dddict, dtmean, sdlist, ftag

def delayDistPlot1(dddict, dtmean, sdlist, ax, opts, phase='S'):
	' Plot delay variation over distances for one phase'
	if phase == 'P':
		ni = 0
	elif phase == 'S':
		ni = 1
	if opts.absdt:
		key = 'Absolute '
	else:
		key = 'Relative '
	ax.axhline(y=0, ls='-', color='k', lw=3)
	ax.plot([10,20],[0,0], color=opts.pcol, marker='.', ls='-', ms=opts.pms, alpha=opts.alpha,
		label='Measurements')
	ax.set_ylabel(key + phase + ' Delay Time [s]')
	ax.set_xlabel('Distance [km]')
	# meansurements
	for evid in sorted(dddict):
		dps = dddict[evid]
		if opts.randcol:
			col = rand(3)
		else:
			col = opts.pcol
		dt = dps[ni]
		if dt is not None:
			ax.plot(dt[:,0], dt[:,1], color=col, marker='.', ls='-', ms=opts.pms, alpha=opts.alpha)
	# mean
	colsym = opts.mcol + opts.msym
	ax.plot(dtmean[ni][:,0], dtmean[ni][:,1], colsym, ms=opts.mms, mew=opts.mew, label='Station-average')
	if opts.ylims[ni] is not None:
		ax.set_ylim(opts.ylims[ni])
	ax.set_xlim(opts.xlim)
	ax.xaxis.set_major_locator(opts.xmajorLocator)
	ax.xaxis.set_minor_locator(opts.xminorLocator)
	ax.yaxis.set_major_locator(opts.ymajorLocator)
	ax.yaxis.set_minor_locator(opts.yminorLocator)
	# why not working?
	#setp(getp(ax, 'xticklines'), 'linewidth', 22)
	ticklines = ax.get_xticklines() + ax.get_yticklines()
	for line in ticklines:
		line.set_linewidth(33)
	#ax.legend(bbox_to_anchor=(0, -0.01), loc=2, borderaxespad=0., shadow=True, fancybox=True, handlelength=3, numpoints=1)
	ax.legend(bbox_to_anchor=(0.5, 1.01), loc=8, borderaxespad=0., ncol=2,
		shadow=True, fancybox=True, handlelength=3, numpoints=1)
	# label stations
	trans = transforms.blended_transform_factory(ax.transData, ax.transAxes)
	for sd in sdlist[0], sdlist[-1]:
		sta, dist = sd
		ax.plot(dist, .97, 'k^', ms=12, transform=trans)
		ax.text(dist, 1.03, sta, transform=trans, va='bottom', ha='center', size=11)	


def plottopo(sdfile, ax):
	tpfile = sdfile + '-topo'
	vals = loadtxt(tpfile, usecols=(1,2))
	dists = vals[:,0]
	topos = vals[:,1]
	ax.plot(dists, topos, 'k-')
	zz = zeros(len(dists))
	ax.fill_between(dists, zz, topos, color='k', alpha=.3)
	tmin, tmax = min(topos), max(topos)
	dt = (tmax - tmin)*.2
	ax.set_ylim(tmin-dt, tmax+dt)
	ax.set_yticks([])
	ax.set_ylabel('Topo')


def plotphysio(m):
	pdir = '/opt/local/seismo/data/GeolProv/physio/'
	pfiles = 'physio_provinces.xy',	'cordillera.xy', 'coastappa.xy'
	plws = 0.6, 2, 2
	for i in range(len(pfiles)):
		xys = readboundary(pdir + pfiles[i])
		plw = plws[i]
		for xy in xys:
			mx, my = m(xy[0], xy[1])
			m.plot(mx, my, 'm-',lw=plw)

def plotmap(stadict, sdlist, opts):
	'Plot map of projection and stations'
	sta0, dist0 = sdlist[0]
	sta2, dist2 = sdlist[-1]
	print('Two ending stations: {:s} + {:s} '.format(sta0, sta2))
	lat0, lon0 = stadict[sta0][:2]
	lat2, lon2 = stadict[sta2][:2]
	delt, bazim = deltaz(lat2, lon2, lat0, lon0)
	delta, azim = deltaz(lat0, lon0, lat2, lon2)
	# ending points of map
	da = (opts.xlim[0]-dist0)/d2k
	db = (opts.xlim[1]-dist2)/d2k
	lata, lona = azdelt(lat0, lon0, da, azim)
	latb, lonb = azdelt(lat2, lon2, db, bazim+180)
	# lowerleft and upper right corners
	qdist = 0.22 * (opts.xlim[1]-opts.xlim[0])/d2k
	latll, lonll = azdelt(lata, lona, qdist, azim+90)
	latur, lonur = azdelt(latb, lonb, qdist, bazim+90)
	scol = opts.scol
	# plot map
	if opts.omercproj:  # Oblique Mercator, not rot to North
		print('Basemap: Oblique Mercator projection')
		m = Basemap(projection='omerc', no_rot=True,
			lon_0=0,lat_0=0,
			llcrnrlat=latll,urcrnrlat=latur,llcrnrlon=lonll,urcrnrlon=lonur,
			lon_1=lon0,lat_1=lat0, lon_2=lon2,lat_2=lat2,
			resolution='i')
	else:  # Miller Cylindrial
		print('Basemap: Miller Cylindrial projection')
		m = Basemap(projection='mill',  
			llcrnrlat=lata-qdist,urcrnrlat=latb+qdist,llcrnrlon=lona,urcrnrlon=lonb,
			resolution='i')
	m.drawcoastlines()
	m.drawstates()
	m.drawparallels(np.arange(-80.,81.,5.), labels=[False,True,True,False])
	m.drawmeridians(np.arange(-180.,181.,5.), labels=[True,False,False,True])
	m.fillcontinents(color='lightgray',lake_color='lightblue')
	m.drawmapboundary(fill_color='lightblue')
	# plot projection line, stations, on map
	mx, my = m([lona, lonb], [lata,latb])
	m.plot(mx, my, color='k',ls='-', lw=3)
	mx, my = m([lon0,lon2], [lat0,lat2])
	m.plot(mx, my, color=scol, marker='^', ls='None', ms=12)
	vals = array([ stadict[sd[0]][:2]  for sd in sdlist[1:-1] ])
	y, x = [ vals[:,i]  for i in range(2) ] 
	mx, my = m(x, y)
	m.plot(mx, my, color=scol, marker='^', ls='None', ms=7)
	plotphysio(m)

def delayDistPlotRun1(dtdict, sdfile, opts, phase='S'):	
	'Run delayDistPlot1 for one phase'
	dddict, dtmean, sdlist, ftag = delayDistGet(dtdict, sdfile, opts)
	if opts.xlimdef is None:
		opts.xlim = -100, sdlist[-1][1] + 100
	else:
		opts.xlim = None
	rcParams['legend.fontsize'] = 9
	if not opts.pmap:
		fig = figure(figsize=(7, 5))
		axd = fig.add_axes([0.1, 0.1, 0.85, 0.7])
		axt = fig.add_axes([0.1, 0.9, 0.85, 0.065], sharex=axd)
	else:
		fig = figure(figsize=(9, 9))
		axd = fig.add_axes([0.1, 0.06, 0.82, 0.4])
		axt = fig.add_axes([0.1, 0.52, 0.82, 0.05], sharex=axd)
		axm = fig.add_axes([0.1, 0.58, 0.82, 0.4])
	plotmap(stadict, sdlist, opts)
	plottopo(sdfile, axt)
	# plot dt dist
	if opts.blackwhite:
		opts.randcol = False
	else:
		opts.randcol = True
	opts.pcol = 'k'
	opts.pms = 4
	opts.mcol = 'k'
	opts.mms = 11
	opts.msym = '*'
	opts.mew = 2
	opts.alpha = .6
	if opts.blackwhite:
		opts.alpha = .4
	delayDistPlot1(dddict, dtmean, sdlist, axd, opts, phase)
	# indexing
	ax = axm
	if opts.indexing is not None:
		tt = '(' + opts.indexing + ')'
		trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
		ax.text(-.07, 1.07, tt, transform=trans, va='top', ha='right', size=16, fontweight='bold')	
	# save figure
	key = sdfile.split('/')[-1]
	fignm = odir + 'ddline-kw-{:s}{:s}-{:s}.png'.format(ftag, phase.lower(), key)
	if opts.randcol: 
		fignm = fignm.replace('kw', 'rc')
	saveFigure(fignm, opts)


def readdd(dtdict, sdfile, opts, phase='S'):
	'read for lon/lat/dtmean/dtstd'
	if phase == 'P':
		ip = 0
	elif phase == 'S':
		ip = 1
	dddict, dtmean, sdlist, ftag = delayDistGet(dtdict, sdfile, opts)
	vals = []
	stas = []
	for i in range(len(sdlist)):
		sta = sdlist[i][0]
		val = stadict[sta][:2] + list(dtmean[ip][i][1:3])
		vals.append(val)
		stas.append(sta)
	vals = array(vals)
	y = vals[:,0]
	x = vals[:,1]
	z = vals[:,2]
	s = vals[:,3]
	return x, y, z, s, stas



def delayDistPlot3(dtdict, sdfiles, mcols, opts, phase):
	fig = figure(figsize=(12,8))
	subplots_adjust(left=.0, right=1, bottom=.0, top=1)
	azim, elev = opts.azimelev
	ax = fig.gca(projection='3d', azim=azim, elev=elev)

	ax.set_xlabel(r'Longitude [$^\circ$]')	
	ax.set_ylabel(r'Latitude [$^\circ$]')	
	ax.set_zlabel('{:s} Delay Time [s]'.format(phase))	
	pdir = '/opt/local/seismo/data/GeolProv/physio/'
	pfiles = 'physio_provinces.xy',	'cordillera.xy', 'coastappa.xy'
	plws = 0.6, 2, 2
	for i in range(len(pfiles)):
		xys = readboundary(pdir + pfiles[i])
		for xy in xys:
			x, y = xy
			ax.plot(x, y, zdir='z', color='m')

	for j in range(len(sdfiles)):
		sdfile, mcol, tag = sdfiles[j], mcols[j], opts.tags[j]
 		x, y, z, s, stas = readdd(dtdict, sdfile, opts, phase)
		for i in range(len(x)): # loop for station
			xi, yi, zi, si = x[i], y[i], z[i], s[i]
			if zi >= 0:
				col = 'r'
			else:
				col = 'b'
			# value point, 0 point (background color), line:
			ax.plot([xi, ], [yi, ], [zi,], zdir='z', marker='o', ms=6, mfc=mcol,mec=mcol)
			if opts.plotstd:
				ax.plot([xi, xi], [yi, yi], [zi-si,zi+si], zdir='z', marker='o', ms=4, ls='-', mfc=mcol,mec=mcol)
			ax.plot([xi, ], [yi, ], [0, ], color='g', zdir='z', marker='^', alpha=0.6)
			ax.plot([xi, xi], [yi, yi], [0, zi], color=col, zdir='z', ls='-')
		# station name:
		shifts = opts.atagshifts, opts.btagshifts
		for i in 0, -1:
			tx, ty, tz = x[i], y[i], 0
			sta = stas[i]
			sa, sb = shifts[i][j]
			#arrow(tx+.5, ty, 3, 1, head_width=.77, color='k', ls='solid')
			ax.text(tx+sa, ty+sb, tz, sta, size=15, fontweight='bold', zdir='x')
	#index
	ax.text2D(0.01, 0.97, '({:s})'.format(opts.index), transform=ax.transAxes,
		va='top', ha='left', size=20, fontweight='bold')

	fx0, fx1 = ax.get_xlim()
	fy0, fy1 = ax.get_ylim()
	n = 3
	fz = zeros((n,n))
	fx, fy = meshgrid(linspace(fx0, fx1, n), linspace(fy0, fy1, n))
	ax.plot_surface(fx, fy, fz, color='g', alpha=.3)

	ax.set_zlim(-8,8)
	fignm = opts.fignm
	saveFigure(fignm, opts)




if __name__ == '__main__':

	ckey = 'RdBu_r'
	cdict = cm.datad[ckey]
	cmap = matplotlib.colors.LinearSegmentedColormap(ckey, cdict)

	opts, sdfiles = getParams()
	locsta = opts.locsta
	stadict = readStation(locsta)

	#dtdict = getDict(opts, ifiles)
	dtdict = readPickle(opts.ifilename)

	absdt = opts.absdt
	rmean = opts.rmean
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

	### get distances for station lines
	odir = './stalines/'
	#deffile = 'stadist'
	deffile = odir + 'dd-d'
	if opts.writedist:
		if not os.path.isdir(odir):
			os.makedirs(odir)
		if opts.ta: # ta lines
			# get keys
			if False:
				net = 'TA.'
				keys = []
				for sta in stadict.keys():
					if sta[:3] == net:
						key = net + sta[3]
						if key not in keys:
							keys.append(key)
			#keys = ['TA.A', 'TA.H', 'TA.S', 'TA.1' ]
			# get sta for each key
			#for key in keys:
			# TA.[A-Z]??? TA.[0-9]???
			for s in string.digits + string.uppercase:
				key = 'TA.' + s
				sdict = {}
				nk = len(key)
				for sta in sorted(stadict):
					if sta[:nk] == key and sta[nk].isdigit():
						sdict[sta] = stadict[sta]
				sdict, tdict = getDistProj(sdict)
				ofile = odir + key.replace('.', '-').lower()
				saveStation(sdict, ofile)
				saveStation(tdict, ofile+'-topo')
			# TA.?33? -- TA.?45?
			for i in range(33, 46):
				sdict = {}
				for sta in sorted(stadict):
					if sta[:2] == 'TA' and sta[4:6] == str(i) :
						sdict[sta] = stadict[sta]
				sdict, tdict = getDistProj(sdict, False)
				ofile = odir + 'ta-' + str(i)
				saveStation(sdict, ofile)
				saveStation(tdict, ofile+'-topo')	
		else: # include all statios
			sdict, tdict = getDistProj(stadict)
			saveStation(sdict, deffile)
			saveStation(tdict, deffile+'-topo')
		sys.exit()

	# get mean delays for shifts
	if absdt and rmean:
		pdict, mtp, stp = delayStats(dtdict, stadict, 'P', absdt, rmean)
		sdict, mts, sts = delayStats(dtdict, stadict, 'S', absdt, rmean)
		opts.shiftps = -mtp, -mts
	else:
		opts.shiftps = 0, 0

	### Get dtdist for a given station line
	#sdfile = opts.stadistfile
	#if sdfile is None:
	#	print('*** Give -s option a station distance file. ***')
	#	sys.exit()
	#if not os.path.isfile(sdfile) and sdfile != 'all':
	#	print('Station distance file does not exist: '+sdfile)
	#	sys.exit()

	if opts.getdd:
		for sdfile in sdfiles:
			if not os.path.isfile(sdfile):
				print('Station distance file does not exist: '+sdfile)
				sys.exit()
			else:
				print('Get delay time variation for stations: '+sdfile)
				net = sdfile.split('/')[-1][:2]
				#if net == 'xr': 
				#	opts.nstamin = 20
				#else:
				#	opts.nstamin = 10 
				dddict, dtmean, sdlist, ftag = delayDistGet(dtdict, sdfile, opts)

	### plot dtdist
	opts.xlimdef = None
	#opts.xlimdef = -100, 3700
	opts.pmap = True
	opts.xmajorLocator = MultipleLocator(500)
	opts.xminorLocator = MultipleLocator(100)
	opts.ymajorLocator = MultipleLocator(1)
	opts.yminorLocator = MultipleLocator(.5)
	opts.majorFormatter = FormatStrFormatter('%d')
	rcParams['legend.fontsize'] = 10
	rcParams['axes.labelsize'] = 'large'
	rcParams['xtick.major.size'] = 6
	rcParams['xtick.minor.size'] = 4
	rcParams['xtick.labelsize'] = 'large'
	rcParams['ytick.major.size'] = 6
	rcParams['ytick.minor.size'] = 4
	rcParams['ytick.labelsize'] = 'large'
	rcParams['axes.titlesize'] = 'x-large'

	opts.omercproj = True # use ObliqueMercator for TA.36 XA XR
	if opts.plotdd:
		for sdfile in sdfiles:
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

			# plot both P and S in the same figures
			if not opts.onephase: 
				delayDistPlotRun(dtdict, sdfile, opts)
			else:
			# plot P and S separately
				phs = 'S',
				phs = 'P', 'S'
				for phase in phs:
					delayDistPlotRun1(dtdict, sdfile, opts, phase)
	### plot 3d
	opts.plotstd = True
	opts.plotstd = False
	phase ='S'
	mcols = 'DarkCyan', 'IndianRed', 'DarkGreen', 'Gold', 'Coral',  'Lime', 'AquaMarine', 'Pink'
	#odir = 'stalines/'
	if opts.plot3d:
		tags = 'ahlqz'
		asd = [ odir + 'ta-'+t  for t in tags ]
		opts.tags = [ sd.split('/')[-1].upper()  for sd in asd ]
		acols = mcols[:5]
		opts.fignm = odir + 'dtdist3d-ta.png'
		opts.azimelev = -70, 58
		opts.atagshifts = [ (-13,1), ] * 5
		opts.btagshifts = [ (3,-2), ] * 5
		opts.index = 'a'
		delayDistPlot3(dtdict, asd, acols, opts, phase)

		bsd = [ odir + 'ta-36', odir+'xa-d', odir+'xr-d' ]
		opts.tags = [ 'TA-36', 'XAXJ', 'XRNM' ]
		bcols = mcols[5:8]
		opts.fignm = odir + 'dtdist3d-xx.png'
		opts.azimelev = -123, 53
		opts.atagshifts = [ (-8, 0.3), (-14, -3), (-7, 3)]
		opts.btagshifts = [ (5,2), ] * 3
		opts.index = 'b'
		delayDistPlot3(dtdict, bsd, bcols, opts, phase)


