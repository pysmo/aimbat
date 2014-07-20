#!/usr/bin/env python
"""
File: ppcommon.py

Comman plotting functions.

xlou 03/13/2012
"""

from pylab import *
import os
from ttcommon import readPickle, writePickle

def saveFigure(fignm, opts):
	'Save figure to file or plot to screen. No -G option needed.'
	from matplotlib.pyplot import savefig, show
	figfmt = opts.savefig
	if figfmt is None:
		show()
	else:
		fignm = fignm.replace('png', figfmt) 
		savefig(fignm, format=figfmt)
		print('Save figure to : '+ fignm)

def plottri(spoint, tpoints):
	'Plot triangle for testing in interpolation'
	figure()
	plot(spoint[0], spoint[1], 'rs', ms=11)
	for i in range(len(tpoints)):
		plot(tpoints[i,0], tpoints[i,1], 'o')
	plot(tpoints[:,0], tpoints[:,1], 'b-')
	axis('equal')
	show()

def plotcmodel(cmod, colors=['b','r'], lw=1, ls='-', label=None):
	'Plot a 1-D crustal model'
	dp, vp, vs = cmod
	nlayer = len(dp)
	dmax = dp[-1] + 10
	dd = list(dp) + [60,]
	pcol, scol = colors
	for i in range(nlayer):
		if i < nlayer-1:
			x = dp[i], dp[i+1], dp[i+1]
			y = vp[i], vp[i],   vp[i+1]
			z = vs[i], vs[i],   vs[i+1]
		else:
			x = dp[i], dmax
			y = vp[i], vp[i]
			z = vs[i], vs[i]
		if label is not None and i == 0:
			plot(x, y, color=pcol, ls=ls, lw=lw, label=label+' P')
			plot(x, z, color=scol, ls=ls, lw=lw, label=label+' S')
		else:
			plot(x, y, color=pcol, ls=ls, lw=lw)
			plot(x, z, color=scol, ls=ls, lw=lw)

def plotboundary_deprecated(cfile, col='k', lw=1, ls='-', comments='>'):
	""" 
	Plot GMT coastal and political boundaries in > separated xy files.
	Read values between each of two >.
	"""
	print('Plot physiographic/coastal boundary file: '+cfile)
	cfobj = open(cfile)
	lines = cfobj.readlines()
	cfobj.close()
	inds = []
	nline = len(lines)
	for i in range(nline):
		if lines[i][0] == comments:
			inds.append(i)
	inds.append(nline)
	nind = len(inds)
	for i in range(nind-1):
		ia = inds[i] + 1
		ib = inds[i+1]
		vlines = lines[ia:ib]
		if len(vlines) > 1:	# plot at least two points
			vals = array([ [ float(v) for v in line.split() ]  for line in vlines ])
			x = vals[:,0]
			y = vals[:,1]
			plot(x, y, color=col, lw=lw, ls=ls)

def plotboundary(cfile, col='k', lw=1, ls='-', comments='>'):
	""" 
	Plot GMT coastal and political boundaries in > separated xy files.
	Read from pickle file to speed up plotting.
	"""
	print('Plot physiographic/coastal boundary file: '+cfile)
	xys = readboundary(cfile, comments)
	for xy in xys:
		x, y = xy
		plot(x, y, color=col, lw=lw, ls=ls)

def plotcoast(coast=True, international=True, internal=False, col='k'):
	'Plot coast lines'
	cdir = '/opt/local/seismo/data/CoastBoundaries/'
	files = 'coastline-na.xy', 'international-na.xy', 'internal-na.xy'
	cfiles = [ cdir+f  for f in files ]
	cplots = coast, international, internal
	lws = 1, 1, .5
	ls = '-'
	for cfile, cplot, lw in zip(cfiles, cplots, lws):
		if cplot:
			plotboundary(cfile, col, lw, ls)


def plotphysio(provinces=False, cordillera=True, coastappa=False):
	'Plot physiographic provinces'
	pdir = '/opt/local/seismo/data/GeolProv/physio/'
	pfile = pdir + 'physio_provinces.xy'
	cfilea = pdir + 'cordillera.xy'
	cfileb = pdir + 'coastappa.xy'
	ls = '-'
	if provinces:
		plotboundary(pfile, 'm', .5, ls)
	if cordillera:
		plotboundary(cfilea, 'm', 1, ls)
	if coastappa:
		plotboundary(cfileb, 'm', 1, ls)

def plotdelaymap(vdict, vindex, cmap, clabel, opts):
	""" Plot delay times in map view. Use vindex to specify the column number.
	"""
	vals = array([ vdict[sta][:2] + [vdict[sta][vindex],]  for sta in vdict.keys() ])
	lat = vals[:,0]
	lon = vals[:,1]
	dtv = vals[:,2]
	vmin, vmax = opts.vlims
	scatter(lon, lat, c=dtv, vmin=vmin, vmax=vmax, cmap=cmap, marker=opts.marker, alpha=opts.alpha, s=opts.msize**2)
	pcbar = opts.plotcbar
	if pcbar is not None:
		if pcbar == 'h':
			cbar = colorbar(orientation='horizontal', pad=.07, aspect=30., shrink=0.95)
		else:
			cbar = colorbar(orientation='vertical', pad=.01, aspect=20., shrink=0.95)
		cbar.set_label(clabel)
		plotphysio(True, opts.physio)
		plotcoast(True, True, True)
	if opts.axlims is not None:
		axis(opts.axlims)
	else:
		axis('equal')



def readboundary(cfile, comments='>'):
	""" 
	Read GMT coastal and political boundaries in > separated xy files.
	Return (x,y) arrays between each of two >.
	"""
	#print('Read physiographic/coastal boundary file: '+cfile)
	ofile = cfile.replace('.xy', '-xy.pkl')
	if os.path.isfile(ofile):
		xys = readPickle(ofile)
	else:
		cfobj = open(cfile)
		lines = cfobj.readlines()
		cfobj.close()
		inds = []
		nline = len(lines)
		for i in range(nline):
			if lines[i][0] == comments:
				inds.append(i)
		inds.append(nline)
		nind = len(inds)
		xys = []
		for i in range(nind-1):
			ia = inds[i] + 1
			ib = inds[i+1]
			vlines = lines[ia:ib]
			if len(vlines) > 1:	# need at least two points
				vals = array([ [ float(v) for v in line.split() ]  for line in vlines ])
				x = vals[:,0]
				y = vals[:,1]
				xys.append((x, y))
		writePickle(xys, ofile)
	return xys	
	


if __name__ == '__main__':
	plotphysio(True, True, True)
	plotcoast(True, True, True)
	show()

