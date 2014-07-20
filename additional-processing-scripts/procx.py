#!/usr/bin/env python
"""
File: procx.py

Process xfiles to assemble delay times from all rays.

Input: 
  xfiles like *.px and *.sx

Output: 
  rayout = ref.rays  -> REFerence Travel-time Rays (source-receiver pair).
    ray number, evdate, station, mccc delay, std, cross coef, take-off angle, azimuth, relative delay, 0, phase
  staout = ref.tsta  -> REFerence Travel-time STAtion locations
  evtout = ref.teqs  -> REFerence Travel-time EarthQuakeS
  stacal = ref.tcals -> REFerence Travel-time CALibration terms for Stations
  evtcal = ref.tcale -> REFerence Travel-time CALibration terms for Earthquakes
                                 (i.e. earthquake relocation terms
  stacut = cut.sta_cut: station has occurances less than cutnum
  The last one (stacut) is not calculated here.

Zero calibration is given to 
  ref.tcals: sta, 0, count of stations
  ref.tcale: evt, 0, count of events

More here:
  evstloc = ref.evst --> location of event and station (lon/lat) pairs for GMT plotting


xlou 05/01/2011
"""

from numpy import *
import os, sys

from optparse import OptionParser
from deltaz import gd2gc, deltaz
from ttcommon import Formats, Filenames, readStation, writeStation, readMLines, parseMLines

def getParams():
	""" Parse arguments and options from command line. 
	"""
	usage = "Usage: %prog [options] <xfiles>"
	parser = OptionParser(usage=usage)
	cutnum = 5
	absdt = False
	parser.set_defaults(cutnum=cutnum)
	parser.set_defaults(absdt=absdt)
	parser.add_option('-a', '--absdt',  dest='absdt', action="store_true",
		help='Use absolute delay times if True, relative if False. Default is %s.' % absdt)
	parser.add_option('-c', '--cutnum',  dest='cutnum', type='int',
		help='Cut-off number of stations for a given event. Default is %s.' % cutnum)
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0:
		print usage
		sys.exit()
	return files, opts




def main(ifiles, opts):
	d2r = pi/180
	r2d = 180/pi
	formats = opts.formats
	filenames = opts.filenames
	cutnum = opts.cutnum
	absdt = opts.absdt
	if absdt:
		tag = 'abs'
	else:
		tag = 'rel'
	fmtsxfile = formats.sxfile
	fmtrefray = formats.refray
	staloc = filenames.staloc
	stadict = readStation(filenames.staloc)
	print('--> Cut-off number of arrivals per event: {0:d}'.format(cutnum))
	# file names and handles
	refeqs = filenames.refeqs
	refsta = filenames.refsta
	refray = filenames.refray
	stacal = filenames.stacal
	evtcal = filenames.evtcal
	fhteqs = open(refeqs, 'w')
	fhrays = open(refray, 'w')
	fhcals = open(stacal, 'w')
	fhcale = open(evtcal, 'w')
	evstloc = filenames.evstloc
	fhevst = open(evstloc, 'w')
	stacount = {}
	evtcount = {}
	h = 0
	for mcfile in ifiles:
		# read mcfile
		headlines, mccclines, taillines = readMLines(mcfile)
		if len(mccclines) < cutnum:
			print('  Skip file:       ' + mcfile)
		else:
			print('  Processing file ({:s} tt): {:s}'.format(tag,mcfile))
			phase, event, stations, ttimes, sacnames = parseMLines(mccclines, taillines)
			elat, elon, edep, mb, ms = event['hypo']
			nsta = len(stations)
			mccctt_mean = float(taillines[0].split()[1])
			theott_mean = float(taillines[0].split()[3])
			evdelay = mccctt_mean - theott_mean
			# write evtout
			evdate = '.'.join(os.path.basename(mcfile).split('.')[:2])
			fhteqs.write( evdate + '   ' + taillines[-1][6:] +'\n')
			evtcount[evdate] = nsta
			# calculate azimuth, write rayout
			for i in range(nsta):
				sta = stations[i]
				h += 1
				if sta in stacount.keys():
					stacount[sta] += 1
				else:
					stacount[sta] = 1 
				slat, slon, selv = stadict[sta]
				delt, azim = deltaz(slat, slon, elat, elon, True)
				if azim > 180: azim -= 360
				mcdelay, sa, cc = ttimes[i,:3]
				rdelay, toa = ttimes[i][7], ttimes[i][8]
				if absdt: 
					rdelay += evdelay
				fhrays.write( fmtrefray.format(h, evdate, sta, mcdelay, sa, cc, toa, azim*d2r, rdelay, 0, phase) )
				fhevst.write( '> {0:s} {1:s} \n'.format(evdate, sta) )
				fhevst.write( '{0:10.5f} {1:10.5f} \n{2:10.5f} {3:10.5f} \n'.format(elon, elat, slon, slat) )
				

	# write event cal/count
	for evdate, num in sorted(evtcount.items()):
		fhcale.write( '{0:s} {1:9.5f} {2:6d} \n'.format(evdate, 0, num) )
	fhrays.close()
	fhteqs.close()
	fhcale.close()

	# write sta cal/count
	newsta = {}
	for sta in stacount.keys():
		newsta[sta] = stadict[sta]
		fhcals.write( '{0:<9s} {1:9.5f} {2:6d} \n'.format(sta, 0, stacount[sta]) )
	writeStation(newsta, refsta, formats.staloc)
	fhcals.close()
	

if __name__ == '__main__':
	ifiles, opts = getParams()
	opts.formats = Formats()
	opts.filenames = Filenames()

	main(ifiles, opts)

