#!/usr/bin/env python
"""
Separate stations into two groups, one west and the other east of the Rocky Mountains.

xlou 03/01/2012

"""

from pylab import *
import os, sys
from commands import getoutput
from ttcommon import readStation, saveStation
from ppcommon import plotcoast, plotphysio, plotdelaymap


def isleft(pointa, pointb, pointc):
	"""
	Tell if pointc is to the left of a line which starts from pointa and ends at pointb (a-->b) 
	using the Z-component of cross product of two vectors: (a-->b, a-->c) 
	
	If 	cpz >  0: to the left
		cpz == 0: on the line
		cpz <  0: to the right

	Inputs: three points with x, y coordinates.
	"""
	ax, ay = pointa
	bx, by = pointb
	cx, cy = pointc
	cpz = sign( (bx - ax) * (cy - ay) - (by - ay) * (cx-ax) )
	if cpz > 0:
		left = True
	else:
		left = False
	return left 


def findsep(sepfile, stafile):
	"""
	Find stations to the west and east of a line defined by sepfile.
	"""
	slonlat = loadtxt(sepfile, comments='>')
	slon = slonlat[:,0]
	slat = slonlat[:,1]
	minlon = min(slon)
	maxlon = max(slon)
	nsep = len(slonlat)
	stadict = readStation(stafile)
	swest, seast = [], []
	for sta in sorted(stadict.keys()):
		sla, slo = stadict[sta][:2]
		if slo < minlon:
			swest.append(sta)
		elif slo > maxlon:
			seast.append(sta)
		else:			
			found = False
			# beneath first point (lowest lat)
			if sla < slat[0]:
				pointa = slonlat[0]
				pointb = slonlat[1]
				found = True
			# above last point (highest lat)
			elif sla > slat[-1]:
				pointa = slonlat[-2]
				pointb = slonlat[-1]
				found = True
			# in between, find all lat bounding point pairs 
			# and use the closest (longitude distance) one
			else:
				pp = []
				for i in range(nsep-1):
					if (sla - slat[i]) * (sla - slat[i+1]) <= 0:
						found = True
						pointa = slonlat[i]
						pointb = slonlat[i+1]
						d = abs(pointa[0]-slo) + abs(pointb[0]-slo)
						pp.append([d, pointa, pointb])
				d, pointa, pointb = sorted(pp)[0]
			if found:
				west = isleft(pointa, pointb, [slo, sla])
				if west:
					swest.append(sta)
				else:
					seast.append(sta)
			else:
				print ('Did not find lat bounding points for station: ' + sta)
				sys.exit()
	nw = len(swest)
	ne = len(seast)
	nsta = len(stadict)
	if nw + ne != nsta:
		print('Numbers of station do not match!')
		print(nw, ne, nsta)
	dwest, deast = {}, {}
	for sta in swest:
		dwest[sta] = stadict[sta]
	for sta in seast:
		deast[sta] = stadict[sta]
	return dwest, deast


def plotline(ifile, col='m'):
	slonlat = loadtxt(ifile, comments='>')
	slon = slonlat[:,0]
	slat = slonlat[:,1]
	plot(slon, slat, color=col, marker='.', ms=3, lw=1)

def plotsta(d, col, marker='^', leg='None'):
	vals = array([ d[sta]  for sta in d.keys() ])
	lat = vals[:,0]
	lon = vals[:,1]
	scatter(lon, lat, color=col, marker=marker, label=leg)

def sepEW():
	# rockies
	dwest, deast = findsep(wsepfile, stafile)
	fwest = stafile + '.west'
	feast = stafile + '.east'
	saveStation(dwest, fwest)
	saveStation(deast, feast)

	# appalachians
	ewest, eeast = findsep(esepfile, feast)
	fwest = feast + 'west'
	feast = feast + 'east'
	saveStation(ewest, fwest)
	saveStation(eeast, feast)

	figure(figsize=(10,8))

	plotline(wsepfile, 'm')
	plotline(esepfile, 'y')

	plotsta(dwest, 'r')
	plotsta(ewest, 'g')
	plotsta(eeast, 'b')
	

	show()




def point_in_poly(point, poly):
	"""
	Determine if a point is inside a given polygon or not.
	Polygon is a list of (x,y) pairs. 
	This function returns True or False.  
	The algorithm is called the "Ray Casting Method".
	"""
	x, y = point
	n = len(poly)
	inside = False
	p1x, p1y = poly[0]
	for i in range(n+1):
		p2x, p2y = poly[i % n]
		if y > min(p1y,p2y):
			if y <= max(p1y,p2y):
				if x <= max(p1x,p2x):
					if p1y != p2y:
						xints = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
					if p1x == p2x or x <= xints:
						inside = not inside
		p1x, p1y = p2x, p2y
	return inside


def getPoly(polyfile):
	'Get polygons by > separated files (for gmt plotting)'
	with open(polyfile) as f:
		lines = f.readlines()
		n = len(lines)
		inds = []
		for i in range(n):
	 		if lines[i][0] == '>': 
				inds.append(i)
		nseg = len(inds)
		#print('File {:s} : {:d} segments'.format(polyfile, nseg))
		inds += [n,]
		polys = []
		for i in range(nseg):
			ia, ib = inds[i]+1, inds[i+1]
			poly = [  [float(v)  for v in line.split() ]  for line in lines[ia:ib] ]
			polys.append(poly)
		return polys


def staPoly(stadict, polys, ofile):
	'Find stations in polygons and save to file'
	insdict = {} 
	for sta in sorted(stadict):
		sloc = stadict[sta][:2][::-1]
		inside = False
		for poly in polys:
			ins = point_in_poly(sloc, poly)
			if ins: 
				inside = True
				break
		if inside:
			insdict[sta] = stadict[sta]
	saveStation(insdict, ofile)
	return insdict

def getPolyAll(pdir):
	'get polys for all physio provinces'
	nphysio = 25
	polydict = {}
	for i in range(1, 1+nphysio):
		pfile = pdir + 't{:d}'.format(i)
		if os.path.isfile(pfile):
			polydict[i] = getPoly(pfile)
	return polydict


def plotPhysio():
	polydict = getPolyAll(pdir)
	fig = figure(figsize=(9, 7))
	if np <= 9:
		subplots_adjust(left=0.07, right=0.98, top=0.84, bottom=0.08)
	elif np < 12:
		subplots_adjust(left=0.07, right=0.98, top=0.8, bottom=0.08)
	elif np < 15:
		subplots_adjust(left=0.07, right=0.98, top=0.76, bottom=0.08)
	else:
		subplots_adjust(left=0.07, right=0.98, top=0.72, bottom=0.08)
	marker = '^'
	for prov in aprovs:
		inds, name, col, = pidict[prov][:3]
		ofile = stafile + '-' + prov
		if not os.path.isfile(ofile):
			ninds = len(inds)
			polys = []
			for i in range(ninds):
				polys += polydict[inds[i]]
			insdict = staPoly(stadict, polys, ofile)
		else:
			insdict = readStation(ofile)
		plotsta(insdict, col, marker, name)

	legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=4,
		ncol=3, mode="expand", borderaxespad=0.)

	plotcoast(True, True, True)
	plotphysio(True, True, True)

	axis([-126, -66, 25, 50])
	xlabel('Longitude')
	ylabel('Latitude')

	savefig(fignm, fmt=fignm.split('.')[-1])
	#fignm = fignm.replace('pdf', 'png')
	#savefig(fignm, fmt=fignm.split('.')[-1], dpi=200)

	#show()



def area(p):
	"""
	http://stackoverflow.com/questions/451426/how-do-i-calculate-the-surface-area-of-a-2d-polygon

	Calculate surface area of a 2D polygon.
	Basically sum the cross products around each vertex. Much simpler than triangulation.
	Python code, given a polygon represented as a list of (x,y) vertex coordinates, implicitly wrapping around from the last vertex to the first:

	"""
	return 0.5 * abs(sum(x0*y1 - x1*y0  for ((x0, y0), (x1, y1)) in segments(p)))

def segments(p):
	return zip(p, p[1:] + [p[0]])


def getPhysioArea():
	polydict = getPolyAll(pdir)
	padict = {}
	pafile = 'locsta-area'
	for prov in aprovs:
		inds, name, col, = pidict[prov][:3]
		sfile = stafile + '-' + prov
		if True:
			ninds = len(inds)
			pa = 0
			for i in range(ninds):
				polys = polydict[inds[i]]
				for poly in polys:
					pa += area(poly)
			nsta = int(getoutput('cat {:s} | wc -l'.format(sfile)).split()[0])
			padict[prov] = [pa, nsta]
	saveStation(padict, pafile)



if __name__ == '__main__':
	stafile = 'loc.sta'
	pdir = '/opt/local/seismo/data/GeolProv/physio/'
	wsepfile = pdir + 'cordillera.xy'
	esepfile = pdir + 'coastappa.xy'

	#sepEW()
	rcParams['legend.fontsize'] = 14

	stadict = readStation(stafile)

	# poly from pysio
	pdir = os.environ['HOME'] + '/work/data/GeolProv/physio/'

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

	wprovs = 'pacmt', 'intmt', 'rocky'
	eprovs = 'super', 'intpl', 'inthl', 'appal', 'coast'
	fignm = 'usphysta1.pdf'

	wprovs = 'pbp', 'csm', 'cbp', 'cop', 'bar', 'nrm', 'mrm', 'wyb', 'srm'
	eprovs = 'super', 'grp', 'cel', 'ilp', 'inthl', 'appal', 'coast'
	fignm = 'usphysta2.pdf'

	aprovs = wprovs + eprovs
	np = len(wprovs) + len(eprovs)

	#plotPhysio()


	getPhysioArea()

