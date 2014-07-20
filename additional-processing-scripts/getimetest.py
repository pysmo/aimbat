#!/usr/bin/env python
# Do getime
# xlou 05/09/2011

import sys
from getime import getime

phase = 'S'
ie, id, ic = 0, 0, 1
moddir = '/opt/local/seismo/data/models/'

if __name__ == '__main__':
	usage = '%s modname phase slat slon elat elon edep' % sys.argv[0]
	if len(sys.argv) != 8:
		print usage
		sys.exit()
	mod = moddir + sys.argv[1]
	phase = sys.argv[2]
	
	slat, slon, elat, elon, evdp = [ float(v) for v in sys.argv[3:8] ] 
	
	time, elcr, dtdd = getime(mod, phase, slat, slon, elat, elon, evdp, ie, id, ic)
	print 'slat, slon, elat, elon, evdp: ', slat, slon, elat, elon, evdp
	print 'time, elcr, dtdd: ', time, elcr, dtdd 
