#!/usr/bin/env python
"""
File: deltaz.py

Python module for geo coordinates and calculation of distance and azimuth.
Run as main script to do deltaz and azdelt.


Input and output lat/lon/delta/azimuth for deltaz and azdelt are all in degrees. 
Coversion between degree and radian,
  for sphere:    *pi/180 and *180/pi
  for ellipsoid: gd2gc() and gc2gd(), where geocentric latitude is used.

Code based on Suzan's deltaz.f and azdelt.f for spherical earth,
  Ken Creager's delaz and coortr in VanDecar's getime.f

World Geodetic Survery (WGS-84) ellipsoid:
  Equatorial radius:    a = 6378.137 km
  Polar      radius:    b = 6356.7523142 km
  Angular eccentricity: alpha = arccos(b/a)
  First eccentricity:   e = sin(alpha), e**2 = 0.00669437999014
  First flattening:     f = (a-b)/a = 1 - cos(alpha)

Conversion between geocentric and geodetic latitudes
		gc = arctan((1-e**2)*tan(gd))
  for latitudes smaller than latpole=89.9, otherwise equal.


xlou 04/2011
"""

from optparse import OptionParser
from numpy import pi, sin, cos, tan, arcsin, arccos, arctan, arctan2
import sys


d2r = pi/180
r2d = 180/pi
pio2 = pi/2
p = pi/180
ees = 0.00669437999014
ee1 = 1 - ees
latpole = 89.9


def gc2gd(gclat):
	""" geocentric --> geodetic latitude in degrees
	"""
	if abs(gclat) < latpole:
		gdlat = arctan(tan(gclat*d2r)/ee1) * r2d
	else:
		gdlat = gclat
	return gdlat

def gd2gc(gdlat):
	""" geodetic --> geocentric latitude in degrees
	"""
	if abs(gdlat) < latpole:
		gclat = arctan(ee1*tan(gdlat*d2r)) * r2d
	else:
		gclat = gdlat
	return gclat

def deltaz(lat1, lon1, lat2, lon2, ellipsoid=True):
	""" Calculate delta and azimuth from lat/lon of two points.
	"""
	if ellipsoid:
		teta1 = gd2gc(lat1) * d2r
		teta2 = gd2gc(lat2) * d2r
	else:
		teta1 = lat1 * d2r
		teta2 = lat2 * d2r
	fi1   = lon1 * d2r
	fi2   = lon2 * d2r
	if teta1 > pio2 or teta1 < -pio2:
		print 'Error, non-existent latitude: ', teta1
	if teta2 > pio2 or teta2 < -pio2:
		print 'Error, non-existent latitude: ', teta2
	delta = _deltas(teta1, fi1, teta2, fi2) * r2d
	azimu = _azimus(teta1, fi1, teta2, fi2) * r2d
	if azimu < 0: azimu += 360
	return delta, azimu

def azdelt(lat, lon, delta, azimuth, ellipsoid=True):
	""" Give lat/lon of a point, delta and azimuth, calculate the other point.
	"""
	if ellipsoid:
		teta1 = gd2gc(lat) * d2r
	else:
		teta1 = lat * d2r
	fi1 = lon * d2r
	delta   *= d2r
	azimuth *= d2r
	fi2   = _fi2s(fi1, teta1, azimuth, delta)
	teta2 = _teta2s(teta1, azimuth, delta)
	if ellipsoid:
		lat2 = gc2gd(teta2*r2d)
	else:
		lat2 = teta2 * r2d
	lon2 = fi2 * r2d
	return lat2, lon2

def _deltas(teta1, fi1, teta2, fi2):
	""" Calculate distance in degree (delta) from lat/lon of two points.
	"""
	term1   = sin(teta1) * sin(teta2)
	factor2 = cos(teta1) * cos(teta2)
	factor1 = cos(fi1-fi2)
	term2   = factor1 * factor2
	som     = term1 + term2
	if som > 1.0: print 'deltaz: som>1.0', som
	delta = arccos(som)
	return delta

def _azimus(teta1, fi1, teta2, fi2):
	""" Calculate azimuth in degree from lat/lon of two points.
	"""
	factor1 = cos(teta2)
	factor2 = sin(teta1)
	factor3 = cos(fi2-fi1)
	term1   = sin(teta2) * cos(teta1)
	term2   = factor1 * factor2 * factor3
	teller  = factor1 * sin(fi2-fi1)
	rnoemer = term1 - term2
	azimuth = arctan2(teller, rnoemer)
	return azimuth

def _fi2s(fi1, teta1, azimuth, delta):
	""" Find fi2 
	"""
	term1   = cos(delta) * sin(fi1) * cos(teta1)
	factor2 = sin(delta) * cos(azimuth) * sin(teta1)
	term2   = factor2 * sin(fi1)
	factor3 = sin(delta) * sin(azimuth)
	term3   = factor3 * cos(fi1)
	teller  = term1 - term2 + term3
	term1   = cos(delta) * cos(fi1) * cos(teta1)
	term2   = factor2 * cos(fi1)
	term3   = factor3 * sin(fi1)
	rnoemer = term1 - term2 - term3
	fi2 = arctan2(teller, rnoemer)
	return fi2

def _teta2s(teta1, azimuth, delta):
	""" Find teta2
	"""
	term1 = cos(delta) * sin(teta1)
	term2 = sin(delta) * cos(azimuth) * cos(teta1)
	som   = term1 + term2
	teta2 = arcsin(som)
	return teta2


def getParams():
	""" Parse arguments and options from command line. 
	"""
	usage = "Usage: %prog [options]"
	parser = OptionParser(usage=usage)
	ellips = False
	parser.set_defaults(ellips=ellips)
	parser.add_option('-a', '--azdelt', dest='azdelt', type='float', nargs=4,
		help='Give first point (lat0 lon0 delta azimuth) to get second point lat1 and lon1.')
	parser.add_option('-d', '--deltaz', dest='deltaz', type='float', nargs=4,
		help='Give two points (lat0 lon0 lat1 lon2) and get delta and azimuth.')
	parser.add_option('-e', '--ellips', action="store_true", dest='ellips',
		help='Consider Earth as an ellipsoid, otherwise sphere. Default is %s.' % ellips)
	opts, files = parser.parse_args(sys.argv[1:])
	if opts.azdelt is None and opts.deltaz is None:
		print 'Run %prog -h for help.'
		sys.exit()
	return opts

def main(opts):
	if opts.deltaz is not None:
		lat0, lon0, lat1, lon1 = opts.deltaz
		delt, azim = deltaz(lat0, lon0, lat1, lon1, opts.ellips)
		print 'Input:  lat0 lon0 lat1 lon1 = %.3f %.3f %.3f %.3f ' % opts.deltaz
		print 'Output: delta azimuth = %.3f %.3f' % (delt, azim)
	elif opts.azdelt is not None:
		lat0, lon0, delt, azim = opts.azdelt
		lat1, lon1 = azdelt(lat0, lon0, delt, azim, opts.ellips)
		print 'Input:  lat0 lon0 delt azim = %.3f %.3f %.3f %.3f ' % opts.azdelt
		print 'Output: lat1 lon1 = %.3f %.3f ' % (lat1, lon1)

if __name__ == '__main__':
	opts = getParams()
	main(opts)

