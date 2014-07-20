#!/usr/bin/env python
"""
File: ehb.py

Read and select EHB residuals.
Residual files are .gz files from ISC:  http://www.isc.ac.uk/EHB/index.html 
See format.res for reference.

Output one residual file for all events .

Function for reading:
  ehbEvent()
  ehbStation()
  ehbResidual()

iprec        arrival time reading precision          i3
             3  to nearest 1/10th minute
             2  to nearest minute
             1  to nearest ten seconds
             0  to nearest second
            -1  to 1/10th second
            -2  to 1/100th second
convert iprec to fprec in seconds
When iprec == -3, assume 1/1000th seconds.


xlou 04/27/2011
"""

from optparse import OptionParser
from deltaz import gd2gc
from os import system
import sys

def getParams():
	""" Parse arguments and options from command line. 
	"""
	usage = "Usage: %prog [options] <resfile(s)>"
	parser = OptionParser(usage=usage)
	phase = 'P/S'
	dist = 30, 90
	region = 19, 51, -130, -50
	#region = -90, 90, -180, 180
	ofile = 'out.res'
	parser.set_defaults(phase=phase)
	parser.set_defaults(dist=dist)
	parser.set_defaults(region=region)
	parser.set_defaults(ofile=ofile)
	parser.add_option('-d', '--dist',  dest='dist', type='float', nargs=2,
		help='Range of epicentral distance in degree: distmin distmax. Defaults: %.1f %.1f' % dist)
	parser.add_option('-R', '--region',  dest='region', type='float', nargs=4,
		help='Range of station lat/lon: latmin latmax lonmin lonmax. Defaults: %.1f %.1f %.1f %.1f' % region)
	parser.add_option('-p', '--phase',  dest='phase', type='str',
		help='List of seismic phases separated by /. Default: %s' % phase)
	parser.add_option('-o', '--ofile',  dest='ofile', type='str',
		help='Output file name.')
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0:
		print usage
		sys.exit()
	return files, opts


def ehbEvent(line):
	""" Get event id, origin time, hypocenter of the earthquake from EHB residuals. """
	nev = int(line[0:7])
	isol = line[8:11]
	iyr, imon, iday, ihold, ihr, imin = [ int(v) for v in line[31:50].split() ]
	sec, elat, elon, depth, fmb, fms = [ float(v) for v in line[50:86].split() ]
	elat = 90 - elat
	if elon > 180: elon -= 360
	return nev, isol, iyr, imon, iday, ihold, ihr, imin, sec, elat, elon, depth, fmb, fms

def ehbStation(line):
	""" Get station and phase information from EHB residuals.
		slat is geocentric colatitude,  slon 0-360.
	 	station with elevation wrong: MYKOM   88.222 103.850104.311
	"""
	sta = line[102:108]
	phasej = line[158:166]
	#slat, slon, elev, delta, azim = [ float(v) for v in line[108:147].split() ]
	slat, slon        = [ float(v) for v in line[108:124].split() ]
	elev, delta, azim = [ float(v) for v in line[124:147].split() ]
	slat = 90 - slat
	if slon > 180: slon -= 360
	return sta, phasej, slat, slon, elev, delta, azim

def ehbResidual(line):
	""" Get EHB residual times """
	dprec = {3:6., 2:60., 1:10., 0:1., -1:0.1, -2:.01, -3:.001}
	obstt, iprec, prett, rawres         = [ float(v) for v in line[269:299].split() ]
	ecor, scor, elcor, resid, iflg, wgt = [ float(v) for v in line[304:339].split() ]
	iflg = int(iflg)
	fprec = dprec[int(iprec)]
	return obstt, fprec, prett, rawres, ecor, scor, elcor, resid, iflg, wgt




def main(ifiles, opts):
	distmin, distmax = opts.dist
	latmin, latmax, lonmin, lonmax = opts.region
	latmin = gd2gc(latmin)
	latmax = gd2gc(latmax)
	if lonmin > 180: lonmin -= 360
	if lonmax > 180: lonmax -= 360
	if lonmin > lonmax:
		minmax = lonmin
		lonmin = lonmax
		lonmax = minmax
	if latmin > latmax:
		minmax = latmin
		latmin = latmax
		latmax = minmax
	phaselist = [ '%-8s' % ph for ph in opts.phase.split('/')]
	nphase = len(phaselist)
	fph = nphase * ' %s '
	out = '--> Select EHB residuals for phase(s): ' + fph
	out = out % tuple(phaselist)
	out += '\n                       distance range:  %.1f to %.1f ' % opts.dist
	out += '\n                       station region:  %.5f %.5f %.5f %.5f' % opts.region
	out += '\n                    geocentric region:  %.5f %.5f %.5f %.5f' % (latmin, latmax, lonmin, lonmax)
	out += '\n                     output file name:  %s' % opts.ofile
	print out
	print 'Input residual files: ', ifiles

	ofileobj = open(opts.ofile, 'w')
	tfile = 'tmpfile'
	for ifile in ifiles:
		if ifile[-3:] == '.gz':
			cmd = 'gzip -c -d %s > %s' % (ifile, tfile)
			print ' -- decompress and read %s' % ifile
			system(cmd)
			ifile = tfile
		else:
			print ' -- read %s' % ifile
		ifileobj = open(ifile, 'ro')
		for line in ifileobj.readlines():
			sta, phasej, slat, slon, elev, delta, azim = ehbStation(line)
			sela = delta >= distmin and delta <= distmax
			selb = slat >= latmin and slat <= latmax and slon >= lonmin and slon <= lonmax
			if phasej in phaselist and sela and selb:
				ofileobj.write(line)
		ifileobj.close()
	ofileobj.close()
	system('/bin/rm -f %s' % tfile)


if __name__ == '__main__':
	ifiles, opts = getParams()
	main(ifiles, opts)

