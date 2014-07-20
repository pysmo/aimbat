#!/usr/bin/env python

from numpy import *
import os, sys



def pointmoho(latlon=[41,-101], offset=0.1, model='NA04'):
	""" 
	Find Moho depth from NA04/NA07 for a point location.
	Program sns/tom2gmt outputs values for 9 points, in which the center one is needed.
	"""
	modir = os.environ['HOME'] + '/work/na/models/' + model.lower()
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
	os.system('/bin/rm -f '+ftmp)
	os.chdir(pwd)
	return dmoho


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


if __name__ == '__main__':


	latlon=[41,-101]
	offset=0.1
	model='NA04'

	#m = pointmoho(latlon, offset, model)
	#print m

	pb = [0,0]
	pc = [1,1]

	pa = 2,4

#	print point_line_distance(pa, pb, pc)

	knbrs = 5
	ainds = []
	for i in range(1, knbrs-1):
		for j in range(i+1, knbrs):
			inds = 0, i, j
			print inds

