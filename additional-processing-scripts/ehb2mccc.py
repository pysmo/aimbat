#!/usr/bin/env python
"""
File: ehb2mccc.py

Convert EHB residuals to MCCC format.

Input: result of readres.py separated for each phase.
Output: *.mc files and loc.sta.
	
new string formatting instead of % operator.
http://docs.python.org/library/string.html#formatexamples

Example output:
filename: 19600102.03214806.mc

EHB residuals in MCCC format. Evend ID: 19600000002 
station,  obstt,     fprec,    wgt,      elcor,  pol     
 PAS     137.6667    0.0000    0.1000    0.3500    0 ehb 
 SLM      10.6667    0.0000    0.1200    0.0600    0 ehb 
 TAC    -148.3333    0.0000    0.1000    0.5800    0 ehb 
Mean_arrival_time:  1050.2733 
Window 
Variance 
Taper 
Phase: S        
DEQ 196001020321480617697S069244W1446  0mb             60Ms



xlou 04/27/2011
"""


from optparse import OptionParser
from collections import defaultdict
import os, sys
from numpy import array, mean
from deltaz import gd2gc, gc2gd
from ehb import ehbEvent, ehbStation, ehbResidual
from ttcommon import Formats, Filenames, mcName, writeStation

def makeDicts(ifile):
	""" Read residual file into three dicts.
		If there is duplicate, the one with higher precision is used.
		Latitudes of station and event are converted from geocentric to geographic.
	"""
	ifileh = open(ifile, 'ro')
	resdict = defaultdict(dict)
	evtdict = defaultdict(dict)
	stadict = defaultdict(dict)
	for line in ifileh.readlines():
		nev, isol, iyr, imon, iday, ihold, ihr, imin, sec, elat, elon, depth, fmb, fms = ehbEvent(line)
		sta, phasej, slat, slon, elev, delta, azim = ehbStation(line)
		evid = '{0!s:4}{1!s:0>7}'.format(iyr, nev)
		obstt, fprec, prett, rawres, ecor, scor, elcor, resid, iflg, wgt = ehbResidual(line)
		if sta in resdict[evid].keys():
			old = resdict[evid][sta]
			print '--> New record  : ', sta, obstt, fprec, wgt, phasej, nev, iyr, imon, iday
			print ' existing record: ', old[0], old[1], old[2], old[3]
			newsta = fprec > old[2]
		else:
			newsta = True
		if newsta:
			resdict[evid][sta] = [sta, obstt, fprec, wgt, elcor]
			if not evid in evtdict.keys():
				elat = gc2gd(elat)
				evtdict[evid] = [isol, iyr, imon, iday, ihr, imin, sec, elat, elon, depth, fmb, fms]
			if not sta in stadict.keys():
				slat = gc2gd(slat)
				stadict[sta] = [slat, slon, elev]
	ifileh.close()
	return resdict, evtdict, stadict, phasej



def main(ifile, odir):
	""" Main program """
	resdict, evtdict, stadict, phasej = makeDicts(ifile)
	formats = Formats()
	filenames = Filenames()

	# write station location to a file
	writeStation(stadict, odir+'/'+filenames.staloc, formats.staloc)

	# write mc files
	for evid, evres in resdict.items():
		isol, iyr, imon, iday, ihr, imin, sec = evtdict[evid][:7]
		elat, elon, depth, fmb, fms = evtdict[evid][7:]
		evline = formats.event.format(isol, iyr, imon, iday, ihr, imin, sec, elat, elon, depth, fmb, fms)
		mcname = mcName(formats.mcname, iyr, imon, iday, ihr, imin, sec )
		mcfile = open('{0}/{1}'.format(odir, mcname), 'w')
		line0 = 'EHB residuals in MCCC format. Evend ID: {0} \n'.format(evid)
		line1 = 'station,  obstt,     fprec,    wgt,      elcor,  pol     \n'
		mcfile.write(line0)
		mcfile.write(line1)
		mtt = mean(array([ item[1] for sta, item in evres.items() ]))
		for sta, item in sorted(evres.items()):
			#sta, obstt, iprec, elcor, wgt = item
			mcfile.write( formats.mcfile.format(item[0], item[1]-mtt, item[2], item[3], item[4], 0, 'ehb') )
		mcfile.write( 'Mean_arrival_time:  {0:9.4f} \n'.format(mtt) )
		mcfile.write( 'Window \n' )
		mcfile.write( 'Variance \n' )
		mcfile.write( 'Taper \n' )
		mcfile.write( 'Phase: {0:8s} \n'.format(phasej) )
		mcfile.write( evline + '\n' )
		mcfile.close()



if __name__ == '__main__':
	usage = 'Usage: %s resfile out-dir' % sys.argv[0]

	try:
		ifile = sys.argv[1]
		odir  = sys.argv[2]
	except:
		print(usage)
		sys.exit()
	print('--> Convert EHB residuals to MCCC format.')
	print('    Input file: {0}   Output dir: {1}'.format(ifile, odir) )
	if not os.path.isdir(odir):
		os.mkdir(odir)
	main(ifile, odir)

