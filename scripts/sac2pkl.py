#!/usr/bin/env python
#------------------------------------------------
# Filename: sac2pkl.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2011-2012 Xiaoting Lou
#------------------------------------------------
"""
Python script to convert between SAC files and pickle file.

:copyright:
	Xiaoting Lou

:license:
	GNU General Public License, Version 3 (GPLv3) 
	http://www.gnu.org/licenses/gpl.html
"""

import sys
from optparse import OptionParser
from sacpickle import sac2pkl, pkl2sac, fileZipMode

def getOptions():
	""" Parse arguments and options. """
	usage = "Usage: %prog [options] <sacfile(s)>"
	parser = OptionParser(usage=usage)

	ofilename = 'sac.pkl'
	delta = -1
	parser.set_defaults(delta=delta)
	parser.set_defaults(ofilename=ofilename)
	parser.add_option('-s', '--s2p', action="store_true", dest='s2p',
		help='Convert SAC files to pickle file. Default is True.')
	parser.add_option('-p', '--p2s', action="store_true", dest='p2s',
		help='Convert pickle file (save headers) to SAC files.')
	parser.add_option('-d', '--delta',  dest='delta', type='float',
		help='Time sampling interval. Default is %f ' % delta)
	parser.add_option('-o', '--ofilename',  dest='ofilename', type='str',
		help='Output filename which works only with -s option.')
	parser.add_option('-z', '--zipmode',  dest='zipmode', type='str',
		help='Zip mode: bz2 or gz. Default is None.')

	opts, files = parser.parse_args(sys.argv[1:])
	opts.s2p = True
	if opts.p2s:
		opts.s2p = False
	if len(files) == 0:
		print(parser.usage)
		sys.exit()
	return opts, files


def main():
	opts, ifiles = getOptions()
	if opts.s2p:
		print('File conversion: sac --> pkl')
		sac2pkl(ifiles, opts.ofilename, opts.delta, opts.zipmode)
	elif opts.p2s:
		print('File conversion: pkl --> sac')
		filemode, zipmode = fileZipMode(ifiles[0])
		for pkfile in ifiles:
			pkl2sac(pkfile, zipmode)


if __name__ == '__main__':
	main()
