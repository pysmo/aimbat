#!/usr/bin/env python
"""

xlou 03/01/2012

"""

from pylab import *
from scipy.spatial import KDTree
from ttcommon import readStation



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

def point_line_distance(pointa, pointb, pointc):
	"""
	Calculate distance from pointa to a line specified by two points: pointb and pointc.
	http://mathworld.wolfram.com/Point-LineDistance2-Dimensional.html
	"""
	x0, y0 = pointa
	x1, y1 = pointb
	x2, y2 = pointc
	d = abs((x2-x1)*(y1-y0) - (x1-x0)*(y2-y1)) / sqrt((x2-x1)**2+(y2-y1)**2)
	return d

def findmoho(mohoxyz, stadict, knbrs=5, maxdist=0.5):
	""" 
	Interpolate Moho depth or crustal thickness for stations from irregularly spaced data points.
		(1) Find knbrs nearest neighbours with maximum distance using KDTree (distance is inf if not found);
		(2) Search for bounding triangles for the station from its neighbours
		(3) weight the three points of the triangle by distance to the opposite edge.
	mohoxyz: array of (lon, lat, h) data points
	stadict: dict of station locations
	"""
	mohoxy = mohoxyz[:,:2]
	mohoz = mohoxyz[:,2]
	kdtree = KDTree(mohoxy)
	# indices of possible triangles composed of the neighbours
	# always include the nearest one
	ainds = []
	for i in range(1, knbrs-1):
		for j in range(i+1, knbrs):
			inds = 0, i, j
			ainds.append(inds) 
	ninds = len(ainds)
	# loop over all stations, query kdtree and then try to find a bounding triangle
	astas = stadict.keys()
	xstas = []
	mdict = {}
	for sta in astas:
		sla, slo = stadict[sta][:2]
		spoint = [slo, sla]
		qdists, qinds = kdtree.query(spoint, k=knbrs, p=2, distance_upper_bound=maxdist)
		found = False
		for n in range(ninds):
			inds = ainds[n]
			if not found and qdists[inds[-1]] != inf:
				tinds = [ qinds[i] for i in inds ]
				tdists = [ qdists[i] for i in inds ]
				tpoints = array([ mohoxy[i] for i in tinds ])
				found = point_in_poly(spoint, tpoints)
				#print sta, np, found
	 	if not found:
			print('Did not find a bounding triangle for station: '+sta)
			xstas.append(sta)
			#plottri(spoint, tpoints)
		else:
			nind = 3
			tmohos = array([ mohoz[i] for i in tinds])
			twghts = zeros(3)
			xinds = range(3)
			for i in range(3):
				ii = xinds[0:i] + xinds[i+1:3]
				pointc = tpoints[i]
				pointa, pointb = tpoints[ii[0]], tpoints[ii[1]]
				# weight by inverse of distance
				#twghts[i] = 1./tdists[i]
				# weigth by distance to the opposite edge of the point
				twghts[i] = point_line_distance(pointa, pointb, pointc)
			twghts /= sum(twghts)
			stamoho = sum(tmohos*twghts)
			mdict[sta] = stadict[sta] + [stamoho,]
	print('{:d} out of {:d} stations were not found.. '.format(len(xstas), len(astas)))
	return mdict, xstas


def plottri(spoint, tpoints):
	figure()
	plot(spoint[0], spoint[1], 'rs', ms=11)
	for i in range(len(tpoints)):
		plot(tpoints[i,0], tpoints[i,1], 'o')
	plot(tpoints[:,0], tpoints[:,1], 'b-')
	axis('equal')
	show()


if __name__ == '__main__':
	mfile = 'MapHK.xyheke'
	sfile = 'loc.sta'

	stadict = readStation(sfile)
	svals = loadtxt(sfile, usecols=(1,2))

	vals = loadtxt(mfile)
	mohoxyz = vals[:,:3]
	mohoxy = vals[:,:2]
	mohoz = mohoxyz[:,2]

	knbrs = 5
	maxdist = 0.5
	mdict, xstas = findmoho(mohoxyz, stadict, knbrs, maxdist)
	ystas = mdict.keys()

	svals = array([ stadict[sta][:2] for sta in xstas])
	ovals = array([ stadict[sta][:2] for sta in ystas])

	figure(figsize=(14,8))
	plot(mohoxy[:,0], mohoxy[:,1], 'g.', alpha=.3)
	plot(svals[:,1], svals[:,0], 'r^')
	plot(ovals[:,1], ovals[:,0], 'b^')

	axis([-127, -65, 23, 51])
	axis('equal')

	show()




