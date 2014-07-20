#!/usr/bin/env python
"""
Get mccc delay times and save to file for each event for plotting.

xlou 11/25/2011
"""

import os, sys
from optparse import OptionParser
from ttcommon import Formats, readStation, writeStation, readMLines, parseMLines

def getParams():
	""" Parse arguments and options from command line. 
	"""
	usage = "Usage: %prog [options] <mcccfile>"
	parser = OptionParser(usage=usage)
	staloc = 'loc.sta'
	parser.set_defaults(staloc=staloc)
	parser.add_option('-s', '--staloc',  dest='staloc', type='str',
		help='Station location file. Default is: '+staloc)
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0:
		print usage
		sys.exit()
	return opts, files

def main(ifiles, opts):
	""" Main program """
	formats = opts.formats
	if os.path.isfile(opts.staloc):
		stadict = readStation(opts.staloc)
	else:
		print('station location file {0:s} does not exist.'.format(opts.staloc))
		sys.exit()
	for mcfile in ifiles:
		headlines, mccclines, taillines = readMLines(mcfile)
		phase, event, stations, ttimes, sacnames = parseMLines(mccclines, taillines)
		dtdict = {}
		for sta, tt in zip(stations, ttimes):
			slat, slon, selv = stadict[sta]
			dtdict[sta] = slat, slon, tt[-2]
		dtfile = mcfile[:18] + 'dt' + phase.lower()
		writeStation(dtdict, dtfile, formats.staloc)
		print ('Read mccc delay times: {0:s} --> {1:s}'.format(mcfile, dtfile))


if __name__ == '__main__':
	opts, ifiles = getParams()
	opts.formats = Formats()
	main(ifiles, opts)

