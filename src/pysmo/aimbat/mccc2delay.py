from numpy import *
import os, sys

from optparse import OptionParser
from deltaz import gd2gc
from getime import getime
from ttcommon import Formats, Filenames, getVel0, readStation, readMLines, parseMLines

#!/usr/bin/env python
"""
File: mccc2delay.py

Convert MCCC derived relative delay times to real delay times.
Works with multiple input files.

Input : *.mc files
Output: *.sx files for S.
  Each MCCC line is relative delay time.
  First line after that contains absolut delay time:  mean(obstt) - mean(prett).
19600102.03214806.mc --> 19600102.03214806.sx

Call getime to calculate theoretical 1d travel time.
	time, elcr, dtdd = getime(phase, slat, slon, elat, elon, edep, 0, 0, 1)
Input lat/lon are in geographic coordinate.


#######
Require phase and PDE info from MCCC output, which replace command-line input and file 'event.list'.

Need to do:
	options of elevation and crust correction. 

	
xlou 04/30/2011
"""

from numpy import *
import os, sys

from optparse import OptionParser
from deltaz import gd2gc
from getime import getime
from ttcommon import Formats, Filenames, getVel0, readStation, readMLines, parseMLines

def getParams():
	""" Parse arguments and options from command line. 
	"""
	usage = "Usage: %prog [options] <mcccfile>"
	parser = OptionParser(usage=usage)
	modelname = 'iasp91'
	parser.set_defaults(modelname=modelname)
	parser.add_option('-c', '--ccorrfile',  dest='ccorrfile', type='str',
		help='Crustal correction for P and S wave travel times from input files.')
	parser.add_option('-t', '--topocorr',  dest='topocorr', action="store_true",
		help='Topography correction for P and S wave travel times.')
	parser.add_option('-m', '--modelname',  dest='modelname', type='str',
		help='Reference 1D model name. Default is {0:s}.'.format(modelname))
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0:
		print usage
		sys.exit()
	return files, opts


def mccc2delay(mcfile, opts):
	""" Get delay times: obs - theo arrivals.
	"""
	d2r = pi/180
	r2d = 180/pi
	radius = 6371.
	fmtsxfile = opts.formats.sxfile
	modnam = opts.modnam

	stadict = opts.stadict
	ccdict = opts.ccdict
	vel0 = opts.vel0
	headlines, mccclines, taillines = readMLines(mcfile)
	phase, event, stations, ttimes, sacnames = parseMLines(mccclines, taillines)
	elat, elon, edep, mb, ms = event['hypo']
	mccctt = ttimes[:,0]
	try:
		mccctt_mean = float(taillines[0].split()[1])
	except:
		mccctt_mean = -999.99
	nsta = len(stations)

	# determine Vp or Vs for calculation of take-off angles and crust/topo correction.
	if phase == 'P' or phase[:3] == 'PKP':
		iph = 0
	elif phase == 'S':
		iph = 1
	elif phase == 'SKSac':
		iph = 1
	else:
		print('Phase: {0:s}. Not P or S. Skip for now..'.format(phase))
		return
	v0 = vel0[iph]

	# calculate theoretical 1d travel time
	theott = []
	takeoff = []
	ccorr = []
	rminds = []
	for i in range(nsta):
		sta = stations[i]
		slat, slon, selv = stadict[sta]
		time, elcr, dtdd = getime(modnam, phase, slat, slon, elat, elon, edep, 0, 0, 1)
		#print sta, phase, elat, elon, edep, time, elcr, v0
		if time < .1:
			print( ' ** Non teleseismic arrival, removed: '+sta )
			rminds.append(i)
		toa = arcsin(dtdd*r2d*v0/radius)
		cc = ccdict[sta][iph]
		theott.append(time+elcr+cc)
		takeoff.append(toa)
		ccorr.append(cc)
	theott = array(theott)
	theott_mean = mean(theott)
	# recalculate mean arrival times without nonteleseismic stations
	# demean, but not remove elements of station list, ttimes.. 
	inds = range(nsta)
	if len(rminds) > 0:
		for i in rminds:
			inds.remove(i)
		mmmmmmmmmmm = mean(array([ mccctt[i] for i in inds]))
		theott_mean = mean(array([ theott[i] for i in inds]))
		ttimes[:,0] -= mmmmmmmmmmm
		mccctt = ttimes[:,0]
		if mccctt_mean > -900:
			mccctt_mean += mmmmmmmmmmm
	theott -= theott_mean
	delay_mean = mccctt_mean - theott_mean
	delay = mccctt - theott

	# select teleseismic stations, save to x file
	evdate = '.'.join(os.path.basename(mcfile).split('.')[:2])

	ofilenm = evdate + '.' + phase.rstrip().lower() + 'x'
	print ('--- MCCC to delay:   {0:s} -> {1:s} '.format(mcfile, ofilenm))

	ofile = open(ofilenm, 'w')
	if len(headlines) > 1:
		line1 = headlines[1][:-4] + 'theo delay, tcorr, real delay, takeoff angle, file \n'
	else:
		line1 = 'station, mccc delay,  std,   cc coeff,   std,   pol,  theo delay, tcorr, real delay, takeoff angle, file \n'
	ofile.write( headlines[0] )
	ofile.write( line1 )
	for i in inds:
		md, sa, cc, sb, pol = ttimes[i]
		sta = stations[i]
		sac = sacnames[i]
		toa = takeoff[i]
		ofile.write( fmtsxfile.format(sta, md, sa, cc, sb, int(pol), theott[i], ccorr[i], delay[i], toa, sac) )
	fmt = 'Mean_arrival_time:  {0:9.4f}  Theo_mean_arrival_time: {1:9.4f} \n'
	line0 = fmt.format( mccctt_mean, theott_mean)
	ofile.write( line0 )
	# if mccc file does not have a line for Mean_arrival_time:
	n = 0
	if taillines[0][:4] == 'Mean': n = 1
	for line in taillines[n:]:
		ofile.write( line )
	ofile.close()
	return edep 


def topocorrection(stadict, vp, vs):
	""" Topo correction of vertical travel time """
	topodict = {}
	for sta in stadict.keys():
		selv = stadict[sta][2]
		topodict[sta] = [ selv/vp, selv/vs ]
	return topodict

def zerocorrection(stadict):
	""" No correction of  travel time """
	zerodict = {}
	for sta in stadict.keys():
		zerodict[sta] = [0, 0]
	return zerodict


def main(ifiles, opts):
	""" Main program """
	formats = opts.formats
	filenames = opts.filenames
	opts.modnam = filenames.moddir + opts.modelname
	model = opts.modnam + '.tvel'

	if os.path.isfile(filenames.staloc):
		stadict = readStation(filenames.staloc)
	else:
		print('station location file {0} does not exist.'.format(filenames.staloc))
		sys.exit()
	opts.stadict = stadict

	vp, vs = getVel0(model)
	opts.vel0 = [vp, vs]
	out = '--> Calculate take-off angles from surface P and S velocities: {0:.2f} {1:.2f} km/s'
	print( out.format(vp, vs) )

	# crust/topo correction
	if not opts.topocorr and opts.ccorrfile is None:
		print('    No crust/topo correction on travel time.')
		ccdict = zerocorrection(stadict)
	elif opts.topocorr:
		print('    Topo correction using surface velocities.')
		ccdict = topocorrection(stadict, vp, vs)
	else:
		print('    Crustal correction from input file: {0:s}'.format(opts.ccorrfile))
		ccdict = readStation(opts.ccorrfile)
		for sta in ccdict.keys():	# remove station loc in ccdict
			ccdict[sta] = ccdict[sta][-2:]
	opts.ccdict = ccdict

	# run mccc2delay
	sfiles = []
	for mcfile in ifiles:
		edep = mccc2delay(mcfile, opts)
		if edep <1.0:  sfiles.append(mcfile)

	# redo mccc2delay if "Bad interpolation"
	if len(sfiles) > 0 and len(ifiles) > 1:
		print('\nEvents with shallow depth (<1.0): ')
		sh = open('tmp.sh', 'w')
		for mcfile in sfiles:
			if not opts.topocorr and opts.ccorrfile is None:
				out = 'mccc2delay.py {:s} -m {:s}'.format(mcfile, opts.modelname)
			elif opts.topocorr:
				out = 'mccc2delay.py {:s} -t -m {:s}'.format(mcfile, opts.modelname)
			else:
				out = 'mccc2delay.py {:s} -c {:s}'.format(mcfile, opts.ccorrfile)
			print(out+'\n')
			sh.write(out+'\n')
		sh.close()
		os.system('chmod +x tmp.sh')
		os.system('sh tmp.sh')

if __name__ == '__main__':
	ifiles, opts = getParams()

	opts.formats = Formats()
	opts.filenames = Filenames()
	main(ifiles, opts)
