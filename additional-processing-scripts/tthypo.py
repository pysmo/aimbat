#!/usr/bin/env python
"""
File: tthypo.py

About earthquake hypocenter on teleseismic delay times

xlou 08/28/2012
"""


from pylab import *
import os, sys
from optparse import OptionParser
from commands import getoutput
from ttcommon import Formats, Filenames, getVel0, readStation, readMLines, parseMLines

def getParams():
	""" Parse arguments and options from command line. 
	"""
	usage = "Usage: %prog [options] <mcccfiles>"
	parser = OptionParser(usage=usage)
	catalog = 'ehb'
	parser.set_defaults(catalog=catalog)
	parser.add_option('-c', '--catalog',  dest='catalog', type="str",
		help='Give catalog (pde/isc/ehb). Default is ehb.')
	parser.add_option('-d', '--gethypodiff',  dest='gethypodiff', action="store_true",
		help='Get new hypo and difference for files')
	parser.add_option('-D', '--hfiles',  dest='hfiles', type="str", nargs=2,
		help='Give two hypo files to get a diff file (file2-file1).')
	parser.add_option('-p', '--plotdiff',  dest='plotdiff', action="store_true",
		help='Plot hypo difference')
	parser.add_option('-g', '--savefig', action="store_true", dest='savefig',
		help='Save figure to file instead of showing.')
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0 and opts.gethypodiff:
		print usage
		sys.exit()
	return opts, files

def rmdup(mylist):
	'Remove duplicate item in a list'
	last = mylist[-1]
	for i in range(len(mylist)-2, -1, -1):
		if last == mylist[i]:
			del mylist[i]
		else:
			last = mylist[i]
	return mylist

def sethypo(setfile):
	'Read preset hypos for exceptions.'
	sf = open(setfile, 'r')
	lines = sf.readlines()
	sf.close()
	shypos = {}
	for line in lines:
		evid = line[:17]
		shypos[evid] = line[18:]
	return shypos

def readhypo(hfile):
	'Read hypo file and return evids and txyz'
	values = loadtxt(hfile, usecols=(1,2,3,4,5,6,7,8,9))
	evids = []
	txyzs = []
	for val in values:
		sec = val[3]*3600 + val[4]*60 + val[5]
		lat, lon, dep = val[6:9]
		val[5] *= 100
		y, m, d, h, n, s = [ int(v)  for v in val[:6]]
		evid = '{:4d}{:0>2d}{:0>2d}.{:0>2d}{:0>2d}{:0>4d}'.format(y, m, d, h, n, s)
		evids.append(evid)
		txyzs.append([sec, lon, lat, dep])
	return evids, array(txyzs)

def getdiff(hfilea, hfileb):
	'Get hypo diff (hfileb-hfilea)'
	ofilenm = 'hdiff-' + hfileb.split('-')[-1] + '-' + hfilea.split('-')[-1]
	print('Write to hypodiff file: '+ofilenm)
	eva, dda = readhypo(hfilea)
	evb, ddb = readhypo(hfileb)
	ofile = open(ofilenm, 'w')
	for ev, da, db in zip(eva, dda, ddb):
		dd = db-da
		ofile.write('{:17s} {:9.3f} {:9.3f} {:9.3f} {:9.3f} \n'.format(ev, dd[0], dd[1], dd[2], dd[3]))
	ofile.close()

def readcatalog(catalog, years):
	'Read catalog hypocenters'
	catdir = os.environ['HOME'] + '/work/data/Earthquakes/'
	chypos = {}
	for year in years:
		ifile = catdir + catalog + '-' + year
		cmd = 'cut -d" " -f1 '+ifile
		sols = getoutput(cmd).split()
		if not os.path.isfile(ifile):
			print('File {:s} does not exist.'.format(ifile))
			print('Run: eqcatalog-'+catalog+'.sh '+year + 'at '+catdir)
		else:
			vals = loadtxt(ifile, comments='#', usecols=(1,2,3,4,5,6,7,8,9,10,11))
			chypos[year] = (vals, sols)
	return chypos

def newhypo(mcfile, chypos, ofilenm, shypos={}):
	"""
	Get new hypo and save to new MCCC file.
	Change also the mean arrival time corresponding to origin time change.
	if evid is in shypos, use shypo instead.
	"""
	# read 
	headlines, mccclines, taillines = readMLines(mcfile)
	phase, event, stations, ttimes, sacnames = parseMLines(mccclines, taillines)
	elat, elon, edep, mb, ms = event['hypo']
	year, mon, day, hour, minu, sec = event['time']
	mccctt_mean = float(taillines[0].split()[1])
	asec = hour*3600 + minu*60 + sec
	# set hypo in shypos:
	evid = mcfile.split('/')[-1][:17]
	if evid in shypos:
		shypo = shypos[evid]
		shy = shypo.split()
		isol = shy[0]
		hypo = [ float(f)  for f in shy[1:12]]
		h, m, s = hypo[3:6]
		y, x, z = hypo[6:9]
		dt = h*3600 + m*60 + s - asec
		dx = (x - elon)*100
		dy = (y - elat)*100
		dz = z - edep
		hour, minu, sec, elat, elon, edep = hypo[3:9]
		fmb, fms = hypo[9:11]
	else:
		# search in chypos, find the one with min diff
		hypos, sols = chypos[str(int(year))]
		mmin, mmax = searchsorted(hypos[:,1], (mon, mon+1))			# mon
		dmin, dmax = searchsorted(hypos[mmin:mmax,2], (day, day+1))	# day
		thypos = hypos[mmin+dmin:mmin+dmax]
		dds = []
		dtxyz = []
		for hypo in thypos:
			h, m, s = hypo[3:6]
			y, x, z = hypo[6:9]
			dt = h*3600 + m*60 + s - asec
			dx = (x - elon)*100
			dy = (y - elat)*100
			dz = z - edep
			dd = abs(dt) + abs(dx) + abs(dy) + abs(dz)
			dds.append(dd)
			dtxyz.append([dt, dx, dy, dz])
		# use the one with least difference:
		try:
			ind = argmin(dds)
		except:
			print mcfile
		dt, dx, dy, dz = dtxyz[ind]
		hour, minu, sec, elat, elon, edep = thypos[ind][3:9]
		fmb, fms = thypos[ind][9:11]
		isol = sols[ind+mmin+dmin]
	# change the mean arrival time corresponding to origin time change
	taillines[0] ='Mean_arrival_time:  {0:9.4f} \n'.format(mccctt_mean-dt)
	old = taillines[-1]
	hour = int(hour)
	minu = int(minu)
	# write to file
	new = formats.event.format(isol, year, mon, day, hour, minu, sec, elat, elon, edep, fmb, fms)
	dhypo = '{:9.3f} {:9.3f} {:9.3f} {:9.3f}'.format(dt, dx, dy, dz)
#	print('--> Found event with dt dlon dlat ddep: ' +dhypo)
#	print old, new
#	print('    write new hypo to mcfile : ' + ofilenm) 
	taillines[-1] = new
	ofile = open(ofilenm, 'w')
	for line in headlines + mccclines + taillines:
		ofile.write(line)
	ofile.close()
	return dhypo, old, new


def newhypoAll(opts, files, shypos={}):
	""" 
	Run newhypo for all files.
	Save hypo-diff, hypo-hdf, hypo-ehb.
	shypos for preset hypos.
	"""
	if files[0] == files[0].split('/')[-1]:
		print('Input and output mcccfiles are the same. Exit..')
		sys.exit()		

	years = []
	for mcfile in files:
		year = mcfile.split('/')[-1][:4]
		if year not in years:
			years.append(year)
	print('Read catalog {:s} hypo for years: '.format(catalog), years)
	chypos = readcatalog(catalog, years)

	dhypos, olds, news = [], [], []
	for mcfile in files:
		ofilenm = mcfile.split('/')[-1]
		evid = ofilenm[:17]
		dhypo, old, new = newhypo(mcfile, chypos, ofilenm, shypos)
		dhypos.append(evid + dhypo + '\n')
		olds.append(old)
		news.append(new + '\n')
	# remove duplicates
	dhypos = rmdup(dhypos)
	olds = rmdup(olds)
	news = rmdup(news)

	old = olds[0].split()[0].split('-')[0].lower()
	new = news[0].split()[0].split('-')[0].lower()
	ofiles = ['hdiff-new-old', 'hypo-old', 'hypo-new']
	alines = [dhypos, olds, news]
	for ofile, lines in zip(ofiles, alines):
		print('  Write to file '+ofile)
		of = open(ofile, 'w')
		for line in lines:
			of.write(line)
		of.close()
	print('Suggest:')
	print('mv {:s} hdiff-{:s}-{:s}'.format(ofiles[0],new,old))
	print('mv {:s} hypo-'.format(ofiles[1])+old)
	print('mv {:s} hypo-'.format(ofiles[2])+new)
	return

def plotdiff(fdiff, opts):
	'Plot hypo diff'
	if not os.path.isfile(fdiff):
		print('File does not exist: ' + fdiff)
		sys.exit()
	else:
		print('Read and plot file: '+fdiff)
	diffs = loadtxt(fdiff, usecols=(1,2,3,4))
	dt = diffs[:,0]
	dx = diffs[:,1]
	dy = diffs[:,2]
	dz = diffs[:,3]
	
	dds = [dt, dx, dy, dz]
	#legs = ['dt', 'dx', 'dy', 'dz']
	legs = ['dtime', 'dlon', 'dlat', 'ddep']
	units = ['s', '0.01deg', '0.01deg', 'km']
	nd = len(dds)
	cols = 'crgb'
	fig = figure(figsize=(8,12))
	subplots_adjust(bottom=.05, top=.95, left=.1, right=.95, hspace=.23)
	ax0 = fig.add_subplot(nd, 1, 1)
	axs = [ax0,] + [ fig.add_subplot(nd,1,i+1, sharex=ax0) for i in range(1, nd) ] 
	for i in range(nd):
		dd = dds[i]
		leg = legs[i] + ' mean={:.3f} std={:.3f} [{:s}]'.format(mean(dd), std(dd), units[i])
		axs[i].plot(dd, color=cols[i], marker='.')
		axs[i].set_title(leg)
	axs[i].set_xlabel('Event number')

	tt = fdiff[6:].upper()
	suptitle('Hypo diff ({:s}) '.format(tt) + os.getcwd())

	if opts.savefig:
		savefig(fdiff+'.png', format='png')




if __name__ == '__main__':

	opts, files = getParams()
	formats = Formats()

	files.sort()

	catalog = opts.catalog

	# preset hypos for a catalog
	setfile = 'sethypo-' + catalog
	if os.path.isfile(setfile):
		shypos = sethypo(setfile)
	else:
		shypos = {}

	# get new hypo and diff
	if opts.gethypodiff:
		newhypoAll(opts, files, shypos)

	# get diff
	if opts.hfiles is not None:
		hfilea, hfileb = opts.hfiles
		getdiff(hfilea, hfileb)



	# plot hypo diff
	if opts.plotdiff:
		for fdiff in files:
			plotdiff(fdiff, opts)

	if not opts.savefig:
		show()

