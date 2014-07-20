#!/usr/bin/env python
"""
Get point constraints from Tony Lowry's crustal thickness model

xlou 02/12/2013

"""

from numpy import *
from etopo5 import etopo5

ifile = 'MapHK.xyheke'
vals = loadtxt(ifile)

#setsd = 1
ofile = 'point.lowry'
fmt = '{:10.4f} '*3 + '{:4.1f} \n'

with open(ofile, 'w') as f:
	for val in vals:
		lon, lat, cc, sd = val[:4]
		topo = etopo5(lat, lon) * 0.001
		moho = cc - topo
		f.write(fmt.format(lat, lon, moho, sd))
