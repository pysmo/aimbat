

#!/usr/bin/env python
"""
Read gsac pickle files and create station location file in ascii format.
If -p option is given, save to .pkl in addition.

xlou since 11/25/2011
"""

import os, sys
from optparse import OptionParser
from sacpickle import fileZipMode, readPickle, writePickle

def getParams():
	""" Parse arguments and options. """
	usage = "Usage: %prog [options] <pklfile(s)>"
	parser = OptionParser(usage=usage)
	ofilename = 'loc.sta'
	parser.set_defaults(ofilename=ofilename)
	parser.add_option('-o', '--ofilename',  dest='ofilename', type='str',
		help='Output filename for ascii.')
	parser.add_option('-p', '--savepkl', action="store_true", dest='savepkl',
		help='Save station dict to pickle in addition to ascii.')

	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0:
		print parser.usage
		sys.exit()
	return files, opts

def onePickle(ifile):
	""" Get station dict from one pickle file of gsac. """
	if os.path.isfile(ifile):
		print ('Read file: ' + ifile)
	else:
		print ('File does no exist: '+ifile)
		return
	filemode, zipmode = fileZipMode(ifile)
	if zipmode is not None:
		pklfile = ifile[:-len(zipmode)-1]
	else:
		pklfile = ifile
	gsac = readPickle(pklfile, zipmode)
	return gsac.stadict

def mulPickle(ifiles):
	""" Get station dict from multiple pickle files of gsac. """
	stadict = {}
	for ifile in ifiles:
		sdict = onePickle(ifile)
		if sdict is not None:
			for sta in sdict.keys():
				if sta not in stadict:
					stadict[sta] = sdict[sta]
	return stadict

def writeStation(stadict, ofilename, fmt):
	""" Write station dict to ofile """
	ofile = open(ofilename, 'w')
	for sta, loc in sorted(stadict.items()):
		slat, slon, selv = loc
		ofile.write( fmt.format(sta, slat, slon, selv) )
	ofile.close()


if __name__ == '__main__':
	ifiles, opts = getParams()
	if len(ifiles) == 1:
		stadict = onePickle(ifiles[0])
	else:
		stadict = mulPickle(ifiles)

	fmt = ' {0:<9s} {1:10.5f} {2:11.5f} {3:7.3f} \n'
	print ('--> Save to ascii file: '+opts.ofilename)
	writeStation(stadict, opts.ofilename, fmt)
	if opts.savepkl:
		print ('--> Save to pkl   file: '+opts.ofilename+'.pkl')
		writePickle(stadict, opts.ofilename+'.pkl')


