"""
File: crust.py

Module for crustal models: Crust 2.0, NA04, NA07, Lowry or a combination. 
Reference models: IASP91, MC35, XC35

Get Moho depth/crustal thickness and crustal model.

xlou since 09/30/2009
"""

from numpy import *
import os, sys
from scipy.spatial import KDTree
#from pysmo import crust2
import crust2

### Mohod from NA04 and NA07
def point_moho(latlon=[41,-101], model='NA04', offset=0.1):
	""" 
	Find Moho depth from NA04/NA07 for a point location.
	Program sns/tom2gmt outputs values for 9 points, in which the center one is needed.
	"""
	modir = os.environ['HOME'] + '/work/na/models/' + model.lower()
	model = model.upper()
	if model == 'NA04':
		prog = 'sns'
	elif model == 'NA07':
		prog = 'tom2gmt'
	else:
		print('Model {:s} not recognized.'.format(model))
		sys.exit()
	print('Running {:s} to read {:s} at dir: {:s}'.format(prog, model, modir))
	ftmp = 'tmp'
	lsep = os.linesep
	lat, lon = latlon
	lat0, lat1 = lat-offset, lat+offset
	lon0, lon1 = lon-offset, lon+offset
	lalo = '{:f} {:f} {:f} {:f} \n {:f} {:f}'.format(lat0, lat1, lon0, lon1, offset, offset)
	cmd = 'echo \"2\n{:s}\n{:s}\n\" | {:s} -a {:s} > /dev/null'.format(ftmp, lalo, prog, model)
	print(cmd)
	pwd = os.getcwd()
	os.chdir(modir)
	os.system(cmd)
	dmoho = loadtxt(ftmp)[4][2]
	# tom2gmt gives Moho in m
	if model == 'NA07':
		dmoho *= .001
	os.system('/bin/rm -f '+ftmp)
	os.chdir(pwd)
	return dmoho



### Moho from others (such as Tony Lowry) with irregular spacing
def find_moho(mohoxyz, stadict, knbrs=5, maxdist=0.5):
	""" 
	Triangularly interpolate Moho depth or crustal thickness for stations from irregularly spaced data points.
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
	 	if not found:
			print('Did not find a bounding triangle for station: '+sta)
			xstas.append(sta)
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




### Crust 2
def point_c2weight(latlon=[41,-101]):
	""" 
	Given a lat/lon pair, calculate lat/lon of middle points and weights of interpolation for crust correction.
	Middle point: center of the 2*2 degree cell of Crust 2.0, e.g., (89,-179), (89,-177) ...
	Interpolation: weight average on the middle point and three neighboring middle points.
	Main middle point (mlat,mlon): 
		Middle point of the cell where the input point (flat,flon) is in.
	Three neighboring middle points:
		left/right (mlat,nlon), above or beneath (nlat,mlon), corner (nlat,nlon) of (mlat,mlon).
	Weights: each of the three neighboring middle points are compared with the main middle point.
		The main middle point is counted three times, thus each pair has weight of 1/3.
	"""
	flat, flon = latlon
	if flon > 180: flon -= 360.0
	nla = 90
	nlo = 180
	dx = 360/nlo
	d2r = pi/180
	# Main middle point (indices and lat/lon):
	ilat = int((90.0-flat)/dx) + 1
	ilon = int((flon+180.0)/dx) + 1
	mlat = float(90 - ilat*dx + 1)
	mlon = float(ilon*dx - 180 - 1)
	# Three neighboring middle points and weights:
	nlat = mlat + sign(flat-mlat)*dx
	nlon = mlon + sign(flon-mlon)*dx
	wt = 1.0/3
	wt1 = wt*abs(flon-mlon)/dx
	wt2 = wt*abs(flat-mlat)/dx
	# Weighting:
	dis = sqrt(wt1**2+wt2**2)/wt*dx
	ang = arctan2(wt1,wt2) - pi/4
	wt3 = wt*dis*cos(ang)/dx/sqrt(2)
	if sign(flat-mlat) == 0.0:
		wt = 1.0
		wt1 = wt*abs(flon-mlon)/dx
		wt2 = 0.0
		wt3 = 0.0
	elif sign(flon-mlon) == 0.0:
		wt = 1.0
		wt2 = wt*abs(flat-mlat)/dx
		wt1 = 0.0
		wt3 = 0.0
	wt0 = 1.0 - wt1 - wt2 - wt3
	# main middle point, left/right, above/beneath, corner
	mpoints = array([[mlat,mlon], [mlat,nlon], [nlat,mlon], [nlat,nlon]])
	weights = array([wt0, wt1, wt2, wt3])
	return mpoints, weights 

def point_c2thick(latlon=[41,-101]):
	""" Get Crust 2.0 crustal thickness from the middle points of the 2x2 degree boxes.
	"""
	lat, lon = latlon
	if lon > 180: lon = lon - 360.0
	dx = 2
	ilat = int((90.0-lat)/dx) + 1
	ilon = int((lon+180.0)/dx) + 1
	lat = float(90 - ilat*dx + 1)
	lon = float(ilon*dx - 180 - 1)
	cmoho = crust2.point(lat, lon, 'thick')
	return cmoho

def point_c2thick_intpol(latlon=[41,-101]):
	""" Return interpolated (weighted average) point Crust 2.0 crustal thickness.
	"""
	mpoints, weights = point_c2weight(latlon)
	npts = len(mpoints)
	acmoho = 0.0
	for i in range(npts):
	    cmoho = point_c2thick(mpoints[i])
	    acmoho += cmoho*weights[i]
	return acmoho

def point_c2model(latlon=[41,-101]):
	""" 
	Read Crust 2.0 by crust2.point and return point crustal model including depth, Vp and Vs of each layer.
	The first two layers of water and ice are excluded.

	Example of (41,-101)
	dp: array([ -0.922,  -0.922,  -0.922,   0.078,   1.078,  17.078,  34.078, 45.078])
	vp: array([ 1.5 ,  3.81,  2.5 ,  4.  ,  6.2 ,  6.6 ,  7.3 ,  8.2 ])
	vs: array([ 0.  ,  1.94,  1.2 ,  2.1 ,  3.6 ,  3.7 ,  4.  ,  4.7 ])
	thi:array([  0.   ,   0.   ,   1.   ,   1.   ,  16.   ,  17.   ,  11.   , 45.078])
	"""
	lat, lon = latlon
	if lon > 180: lon -= 360.0
	# Use the middle points of the 2*2 degree box.
	dx = 2
	ilat = int((90.0-lat)/dx) + 1
	ilon = int((lon+180.0)/dx) + 1
	lat = float(90 - ilat*dx + 1)
	lon = float(ilon*dx - 180 - 1)
	# read model
	nlayer = 8
	dp = zeros(nlayer)
	vp = zeros(nlayer)
	vs = zeros(nlayer)
	thi = zeros(nlayer)
	for i in range(nlayer):
		dp[i] = -crust2.point(lat, lon, 't'+str(i))
		vp[i] =  crust2.point(lat, lon, 'vp'+str(i+1))
		vs[i] =  crust2.point(lat, lon, 'vs'+str(i+1))
	cmodel = array([dp[2:], vp[2:], vs[2:]])
	return cmodel


def point_c2model_intpol(latlon=[41,-101]):
	""" 
	Return interpolated (weighted average) point crustal model from Crust 2.0
	The first two layers of water and ice are excluded.
	"""
	nlayer = 6
	mpoints, weights = point_c2weight(latlon)
	npts = len(mpoints)
	acmodel = zeros(nlayer*3).reshape(3, nlayer)
	for i in range(npts):
		cmodel = point_c2model(mpoints[i])
		acmodel += cmodel*weights[i]
	return acmodel


def c2thick(xyrange=[-127,-65,20,55], dxy=[.25,.25], ofilename='moho-crust2', intpol=False):
	print('Write crustal thickness from Crust 2.0 to file: '+ofilename)
	if intpol:
		thick = point_c2thick_intpol
	else:
		thick = point_c2thick
	ofile = open(ofilename, 'w')
	x0, x1 = xyrange[:2]
	y0, y1 = xyrange[2:]
	dx, dy = dxy
	fmt = '{:10.4f} {:10.4f} {:10.4f} \n'
	for lon in arange(x0, x1+dx, dx):
		for lat in arange(y0, y1+dy, dy):
			h = thick([lat, lon])
			ofile.write(fmt.format(lon, lat, h))
	ofile.close()



### reference models:
def refModel(imodnm='iasp91'):
	"""	
	Return reference model with dp, vp and vs.
	Good for depth down to about 220 km.
	"""
	print('Use reference model: '+imodnm)
	if imodnm == 'iasp91':
		idp = array([0.0,  20,   35,   71,	   120,  171,    210])
		ivp = array([5.8,  6.5 , 8.04, 8.0442, 8.05, 8.1917, 8.3])
		ivs = array([3.36, 3.75, 4.47, 4.4827, 4.5,  4.5102, 4.518])
	elif imodnm == 'mc35':
		idp = array([0.0,  2,    20,   35,  210])
		ivp = array([5.2,  5.8,  6.5 , 8.1, 8.2])
		ivs = array([3.0,  3.45, 3.75, 4.5, 4.5231])
	elif imodnm == 'xc35':
		idp = array([0.0,  2.0,  20,   35,   70,    120,    170,    210])
		ivp = array([5.2,  5.8,  6.5 , 8.1,  8.122, 8.1534, 8.185, 8.21])
		ivs = array([3.0,  3.45, 3.75, 4.47, 4.48,  4.493,  4.507, 4.518])
	else:
		print 'Unknown reference model. Exit..'
		sys.exit()
	imodel = array([idp, ivp, ivs])
	return imodel

def meanModel(crustmodel):
	print('Calculate a mean crust model from all stations (dep, vp, vs): ')
	adp, avp, avs = [], [], []
	for sta in crustmodel.keys():
		dp, vp, vs = crustmodel[sta]
		adp.append(dp)
		avp.append(vp)
		avs.append(vs)
	mdp = mean(array(adp), 0)
	mvp = mean(array(avp), 0)
	mvs = mean(array(avs), 0)
	mmodel = mdp, mvp, mvs
	print mdp
	print mvp
	print mvs
	return mmodel


