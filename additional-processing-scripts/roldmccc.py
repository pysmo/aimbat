#!/usr/bin/env python
"""
File: roldmccc.py

Convert old MCCC files to new format, mainly for Polaris and TWIST.

Polaris:
 WLVO  -3.0937   0.10000  0.87777 0.10000    0 2003.016.00.53.15.0000.CN.WLVO..HHZ.D.SAC 
 HRV   41.7350   0.10000  0.76499 0.10000    0 2003.016.00.57.05.0418.IU.HRV..BHZ.R.SAC 
PDE 200301160053150 44284N129024W 10
PHS: P  


TWIST:
 5150   1.0565   0.00901  0.80189 0.21837    0 5150.z                   
 5190  -1.3299   0.00661  0.79228 0.48871    0 5190.z                   
 B12   -4.0446   0.00661  0.84842 0.32557    0 b12.z                    
No weighting of equations.
Window:   3.00   Inset:   1.00   Shifts:   1.00  0.10  0.05
Variance: 0.00645   Coefficient: 0.80475   Sample rate:  100.000
Taper:   1.00
Filter: BP co  0.6000  2.0000  pa 2 BU np  2 tr  0.3000 at  30.000
PHS: P
PDE 19971022095547744719N146211E15455 MB             51MS



xlou 04/27/2011
"""


from optparse import OptionParser
from collections import defaultdict
import os, sys
from numpy import array, mean
from deltaz import gd2gc, gc2gd
from ttcommon import Formats, Filenames, readMLines, mcName

def getParams():
	""" Parse arguments and options from command line. 
	"""
	usage = "Usage: %prog [options] <mcccfile>"
	parser = OptionParser(usage=usage)
	odir = '.'
	parser.set_defaults(odir=odir)
	parser.add_option('-o', '--output-dir',  dest='odir', type='str',
		help='Output directory. Default is %s' % odir)
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0:
		print usage
		sys.exit()
	return files, opts

def readPDE(pde):
	""" Read origin time and hypocenter from pde. """
	isol = pde[:3]
	otime = pde[4:19]
	iyr = int(otime[:4])
	imon = int(otime[4:6])
	iday = int(otime[6:8])
	ihr = int(otime[8:10])
	imin = int(otime[10:12])
	sec = float(otime[12:15])/10.
	otime = [iyr, imon, iday, ihr, imin, sec]
	if len(pde) < 40:
		lat = float(pde[20:25])/1000.
		lon = float(pde[26:32])/1000.
		dep = float(pde[33:36])
		ns = pde[25]
		ew = pde[32]
		if ns == 'S': lat = -lat
		if ew == 'W': lon = -lon
		mb, ms = 0., 0.
	else:
		lat = float(pde[19:24])/1000.
		lon = float(pde[25:31])/1000.
		dep = float(pde[32:35])
		ns = pde[24]
		ew = pde[31]
		if ns == 'S': lat = -lat
		if ew == 'W': lon = -lon
		try:
			mb = float(pde[35:37])/10
		except:
			mb = 0
		try:
			ms = float(pde[53:55])/10
		except:
			ms = 0
	return lat, lon, dep, otime, mb, ms


def convert(mcfile, opts):
	formats = opts.formats
	filenames = opts.filenames
	odir = opts.odir
	# read
	headlines, mccclines, taillines = readMLines(mcfile)		
	for line in taillines:
		if line[:3] == 'PDE' or line[:3] == 'HDS' or line[:3] == 'GS ': 
			pde = line
			isol = 'PDE'
		elif line[:3] == 'PHS' or line[:5] == 'PHASE' or line[:5] == 'Phase':
			phase = line.split()[1]
	elat, elon, edep, otime, mb, ms	= readPDE(pde)
	iyr, imon, iday, ihr, imin, sec = otime
	evline = formats.event.format(isol, iyr, imon, iday, ihr, imin, sec, elat, elon, edep, mb, ms)

	stations = [ line[1:6].rstrip() for line in mccclines ]
	ttimes = array([ [ float(v) for v in line[6:].split()[:5] ] for line in mccclines ])
	sacnames = [ line.split()[-1] for line in mccclines ]
	nsta = len(stations)

	# write	head
	mcname = mcName(formats.mcname, iyr, imon, iday, ihr, imin, sec )
	mcfile = open('{0}/{1}'.format(odir, mcname), 'w')
	nhead = len(headlines)
	if nhead == 2:
		mcfile.write(headlines[0])
		mcfile.write(headlines[1])
	elif nhead == 1:
		mcfile.write(headlines[0])
	else:
		mcfile.write('MCCC \n')
	# write mccc
	for i in range(nsta):
		sta = stations[i]
		md, sa, cc, sb, pol = ttimes[i,:5]
		pol = int(pol)
		mcfile.write( formats.mcfile.format(sta, md, sa, cc, sb, pol, sacnames[i]) )
	# write tail
	for line in taillines[:-2]:
		mcfile.write(line)
	mcfile.write( 'Phase: {0:8s} \n'.format(phase) )
	mcfile.write( evline + '\n' )

	mcfile.close()


def main(ifiles, opts):
	""" Main program """
	formats = Formats()
	filenames = Filenames()

	for mcfile in ifiles:
		print('Regenerate MCCC file: ' + mcfile )
		convert(mcfile, opts)

if __name__ == '__main__':
	ifiles, opts = getParams()
	opts.formats = Formats()
	opts.filenames = Filenames()

	odir = opts.odir
	if not os.path.isdir(odir):
		os.mkdir(odir)
	print('--> Convert old MCCC files to new format.')
	print('    Output dir: {0}'.format(odir) )
	if not os.path.isdir(odir):
		os.mkdir(odir)

	main(ifiles, opts)
