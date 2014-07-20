#!/usr/bin/env python
"""
Python module/script for crust correction of teleseismic travel times using a crustal model.
	Crustal model: Crust 2.0, NA04, NA07, Lowry or a combination.

xlou since 09/30/2009
"""

from pylab import *
import os, sys
from matplotlib.font_manager import FontProperties
from optparse import OptionParser
from ttcommon import readStation, saveStation, readPickle 
from ppcommon import plotcmodel, plotcoast, plotphysio, saveFigure
from crust import refModel, meanModel

def getParams():
	""" Parse arguments and options from command line. 
	"""
	usage = "Usage: %prog [options] "
	parser = OptionParser(usage=usage)
	refmodel = 'iasp91'
	stafile = 'loc.sta'
	mohomodel = 'na04-lowry'
	parser.set_defaults(mohomodel=mohomodel)
	parser.set_defaults(refmodel=refmodel)
	parser.set_defaults(stafile=stafile)
	parser.add_option('-c', '--crustcorr',  dest='crustcorr', action="store_true",
		help='Crustal correction for body wave travel times')
	parser.add_option('-C', '--ccorrplot',  dest='ccorrplot', action="store_true",
		help='Plot crustal corrections')
	parser.add_option('-m', '--mohomodel',  dest='mohomodel', type='str',
		help='Moho model for crustal correction.')
	parser.add_option('-r', '--refmodel',  dest='refmodel', type='str',
		help='Reference model. Default is {:s}'.format(refmodel))
	parser.add_option('-s', '--stafile',  dest='stafile', type='str',
		help='Station location file. Default is {:s}'.format(stafile))
	parser.add_option('-p', '--ccpart',  dest='ccpart', type='str',
		help='Crustal correction partition. Give hist/map for plotting histogram or map')
	parser.add_option('-P', '--plotmodel',  dest='plotmodel', action="store_true",
		help='Plot crustal model and reference model.')
	parser.add_option('-g', '--savefig', type='str', dest='savefig',
		help='Save figure to file instead of showing (png/pdf)')
	opts, files = parser.parse_args(sys.argv[1:])
	return opts, files

def vtTime(model, depth, output=False):
	"""	
	Calculate vertical P and S travel times to a given depth.
	Velocity model are given by dp, vp and vs just like in function refModel().
	"""
	dp, vp, vs = model
	nlay = len(dp)
	# Find depth in the model
	m = -1
	for i in range(nlay-1):
		if depth >= dp[i] and depth < dp[i+1]:
			m = i
			#print '  Depth %5.1f km found at layer %i' % (depth, m)
			continue
	if m == -1 and depth > 0:
		#print '  Depth %5.1f (> %5.1f) km beneath the bottom of the reference' % (depth, dp[-1])
		m = nlay-1
	# Get vertical travel time
	timep = 0.0
	times = 0.0
	for i in range(m):
		timep += (dp[i+1]-dp[i])/vp[i]
		times += (dp[i+1]-dp[i])/vs[i]
	timep += (depth-dp[m])/vp[m]
	times += (depth-dp[m])/vs[m]
	if output:
		print '--> Vertical travel time down to %5.1f km: %7.3f s, %7.3f s ' % (depth, timep, times)
	return timep, times

def ccTime(cmodel, imodel, topo=9, depth=-1, output=False):
	"""	
	Calculate crustal corrections for teleseismic P and S travel times.
	cmodel=array([dp,vp,vs]): crustal model derived from Crust 2.0/NA04.
	imodel=array([idp,ivp,ivs]): reference model.
	Travel time difference of cmodel-imodel.
	Trace from elevation for cmodel and 0 for imodel down to a given depth.
	If topo is given (!=9), topo correction is also calculated, otherwise zero.
		It is the effect of difference in the given topo and crust2 topo.
	"""
	# Max of Moho depth in crustal model and reference model. 
	if depth == -1:
		depth = max(cmodel[0][-1], 35)
	ctimep, ctimes = vtTime(cmodel, depth)
	itimep, itimes = vtTime(imodel, depth)
	# if topo is not given, use elevation (positive above sea-level) of Crust 2.0
	ele = -cmodel[0][0]
	if topo == 9:
		topo = ele
	# Corrections, crust and topo
	ctp = ctimep-itimep
	cts = ctimes-itimes
	### use upper crust velocity of Crust 2.0 for crustal correction
	vp = cmodel[1][2]
	vs = cmodel[2][2]
	ttp = (topo-ele)/vp
	tts = (topo-ele)/vs
	if output:
		print 'Travel time in the reference model: %7.3f s, %7.3f s' % (itimep, itimes)
		print 'Travel time in the crustal   model: %7.3f s, %7.3f s' % (ctimep, ctimes)
		print 'Crustal corrections without topo:   %7.3f s, %7.3f s' % (ctp, cts)
		print 'Topo corrections:                   %7.3f s, %7.3f s' % (ttp, tts)
		print 'All corrections:                    %7.3f s, %7.3f s' % (ctp+ttp, cts+tts)
	ctime = ctp, cts
	ttime = ttp, tts 
	return ctime, ttime

def ccPartTopo(cmodel):
	"""
	Crustal correction contributed by topography, compared to upper crust velocity of the crustal model.
	"""
	dp, vp, vs = cmodel
	ttp = -dp[0]/vp[2] 
	tts = -dp[0]/vs[2]
	ttime = ttp, tts
	return ttime
 
def ccPartSedi(cmodel):
	""" 
	Crustal correction contributed by sediments (first two layers of cmodel) of the crustal model. 
	"""
	dp, vp, vs = cmodel
	da = dp[1]-dp[0]
	db = dp[2]-dp[1]
	stp = (da/vp[0] + db/vp[1]) - (da+db)/vp[2]
	sts = (da/vs[0] + db/vs[1]) - (da+db)/vs[2]
	stime = stp, sts
	return stime 

def ccPartMoho(imodel, newmoho=40.0, defmoho=35.0):
	""" 
	Crustal corrections contributed by only Moho Depth.
	Change the default moho depth in reference model to new moho.
	"""
	cmodel = imodel.copy()
	dp = imodel[0]
	nlay = len(dp)
	for i in range(nlay):
		if abs(dp[i]-defmoho) <= 1e-6:
			m = i
			break
	cmodel[0][m] = newmoho
	depth = max(defmoho, newmoho)
	ctimep, ctimes = vtTime(cmodel, depth)
	itimep, itimes = vtTime(imodel, depth)
	mtime = ctimep-itimep, ctimes-itimes
	return mtime

def ccPartLayer(cmodel, mmodel):
	"""
	Crustal correction for crustal layering of the crustal model.
	Compare to the mean of the crustal models using the same surface and moho depth.
	"""
	dp, vp, vs = cmodel
	ldp = dp[2:]
	lvp = vp[2:]
	lvs = vs[2:]
	dp, vp, vs = mmodel
	mdp = dp[2:]
	mvp = vp[2:]
	mvs = vs[2:]
	ldp[0]  = mdp[0]
	ldp[-1] = mdp[-1]
	lmodel = ldp, lvp, lvs
	imodel = mdp, mvp, mvs
	ltimep, ltimes = vtTime(lmodel, mdp[-1])
	mtimep, mtimes = vtTime(imodel, mdp[-1])
	ltime = ltimep - mtimep, ltimes - mtimes
	return ltime

def ccPart(cmodel, imodel, mmodel, moho=-1, defmoho=35.0):
	""" 
	Calculate crustal correction partition/contributions from:
	-- whole crust
	-- sediments
	-- topography
	-- Moho depth
	-- crustal layering
	If moho is -1, use moho of the given crustal model.
	"""
	if moho < 0: moho = cmodel[0][-1]
	ctime, xtime = ccTime(cmodel, imodel, 9, -1)
	stime = ccPartSedi(cmodel)
	ttime = ccPartTopo(cmodel)
	mtime = ccPartMoho(imodel, moho, defmoho)
	ltime = ccPartLayer(cmodel, mmodel)
	return ctime, stime, ttime, mtime, ltime

def ccPartArray(crustmodel, imodel, mdict, stadict, ofile):
	print('Calcualte crustal correction partition for multiple stations.')
	mmodel = meanModel(crustmodel)
	cdict = {}
	for sta in stadict.keys():
		cmodel = crustmodel[sta]
		sloc = tuple(stadict[sta])
		if type(mdict) == type({}):
			moho = mdict[sta][-1]
		else:
			moho = -1
		ctime, stime, ttime, mtime, ltime = ccPart(cmodel, imodel, mmodel, moho)
		cdict[sta] = list(sloc + ctime + stime + ttime + mtime + ltime)
	saveStation(cdict, ofile)

def ccTopoSediMoho(cmodel, imodel, topo, moho=-1, defmoho=35.0):
	"""
	Crust correction contributed by topography, sediments and Moho depth.
	Three types:
	* (a) Topo          : topo compared to upper crust in refmodel (for joint inversion of BW+SW)
	* (b) Topo+Sedi     : topo + crust 2 sedi 
	* (c) Topo+Sedi+Moho: topo + crust 2 sedi + na04-lowry moho (for BW only inversion)
   Four more types:
	* (d) Sedi          : (crust2 sedi compared to upper crust of the same thickness)
	* (e) Moho          : (na04-lowry moho)
	* (f) Topo+Moho     : (real topo + na04-lowry moho)
	* (g) Crust2        : (crust2 all)
	If moho is -1, use moho of the given crustal model.
	"""
	cdp, cvp, cvs = cmodel
	idp, ivp, ivs = imodel
	# topo - 0
	cca = topo/ivp[0], topo/ivs[0]
	# sedi + topo - remaining upper crust
	dsa = cdp[1] - cdp[0]
	dsb = cdp[2] - cdp[1]
	dc = dsa+dsb - topo
	ccbp = dsa/cvp[0] + dsb/cvp[1] - dc/ivp[0]
	ccbs = dsa/cvs[0] + dsb/cvs[1] - dc/ivs[0]
	ccb = ccbp, ccbs
	# sedi + topo + moho
	if moho < 0: moho = cdp[-1]
	mtime = ccPartMoho(imodel, moho, defmoho)
	ccc = ccbp+mtime[0], ccbs+mtime[1]
	# sedi only - upper crust
	ccdp = dsa/cvp[0] + dsb/cvp[1] - (dsa+dsb)/ivp[0]
	ccds = dsa/cvs[0] + dsb/cvs[1] - (dsa+dsb)/ivs[0]
	ccd = ccdp, ccds
	# moho only
	cce = mtime
	# topo + moho
	ccf = cca[0]+cce[0], cca[1]+cce[1]
	# crustt2
	ccg, dum = ccTime(cmodel, imodel, 9, -1)
	ccall = cca, ccb, ccc, ccd, cce, ccf, ccg
	return ccall

def ccTSMArray(crustmodel, imodel, mohodict, stadict, ccfiles, defmoho=35.0):
	print('Crustal correction for three types, calling ccTopoSediMoho.')
	#ccadict, ccbdict, cccdict = {}, {}, {}
	#ccafile, ccbfile, cccfile = ccfiles
	ncc = len(ccfiles)
	ccdicts = [ {} for i in range(ncc) ]
	for sta in stadict.keys():
		cmodel = crustmodel[sta]
		topo, moho = mohodict[sta][2:4]
		ccall = ccTopoSediMoho(cmodel, imodel, topo, moho, defmoho)
		sloc = stadict[sta][:3]
		for i in range(ncc):
			ccdicts[i][sta] = sloc + list(ccall[i])
	for i in range(ncc):
		saveStation(ccdicts[i], ccfiles[i])

def ccPartArrayPlotHist(ccfile):
	print('Plot crustal correction partition in hist from ccfile: '+ccfile)
	cdict = readStation(ccfile)
	labs = 'All', 'Sediment', 'Topography', 'MohoDepth', 'Layering' 
	cols = 'bgrcm'
	vals = array([ cdict[sta]  for sta in sorted(cdict.keys()) ])
	ptime = vals[:,3::2]
	stime = vals[:,4::2]
	nt = len(ptime[0])
	# mean and absolute means of correction times
	mtp = mean(ptime, 0)
	mts = mean(stime, 0)
	atp = mean(abs(ptime), 0)
	ats = mean(abs(stime), 0)
	rtp = [ sqrt(mean(ptime[:,i]**2))  for i in range(nt) ]
	rts = [ sqrt(mean(stime[:,i]**2))  for i in range(nt) ]
	# plot histograms
	figure(figsize=(10,16))
	subplots_adjust(left=.07, right=.97, bottom=.05, top=0.96, hspace=.12, wspace=.05)
	rcParams['legend.fontsize'] = 11
	subplot(211)
	print('------- P correction times -------')
	for i in range(nt):
		lab = '{:11s}: rms {:4.2f} s, mean {:4.2f} s'.format(labs[i], rtp[i], mtp[i])
		print(lab)
		hist(ptime[:,i], histtype='step', ec=cols[i], fc=cols[i], label=lab, lw=2)
		legend(loc=2, prop=fontp)
	xlim(-1,1)
	xlabel('P correction time [s]')
	title('Crustal correction partition from {:s}'.format(ccfile))
	subplot(212)
	print('------- S correction times -------')
	for i in range(nt):
		lab = '{:11s}: rms {:4.2f} s, mean {:4.2f} s'.format(labs[i], rts[i], mts[i])
		print(lab)
		hist(stime[:,i], histtype='step', ec=cols[i], fc=cols[i], label=lab, lw=2)
		legend(loc=2, prop=fontp)
	xlabel('S correction time [s]')
	xlim(-2,2)
	fignm = ccfile + '-hist.png'
	saveFigure(fignm, opts)


def ccPartArrayPlotMap(ccfile, vlims):
	print('Plot crustal correction partition in map from ccfile: '+ccfile)
	cdict = readStation(ccfile)
	labs = 'All', 'Sediment', 'Topography', 'MohoDepth', 'Layering' 
	vals = array([ cdict[sta]  for sta in sorted(cdict.keys()) ])
	ptime = vals[:,3::2]
	stime = vals[:,4::2]
	pstime = ptime, stime
	nt = len(ptime[0])
	latlon = array([ stadict[sta][:2]  for sta in sorted(cdict.keys()) ])
	lat = latlon[:,0]
	lon = latlon[:,1]
	figure(figsize=(24,11))
	subplots_adjust(left=.015, right=.99, bottom=.03, top=0.96, hspace=.06, wspace=.065)
	sz = 4
	for i in range(nt):
		for j in range(2):
			subplot(2,nt,i+1+j*nt)
			vmin, vmax = vlims[i][j]
			scatter(lon, lat, c=pstime[j][:,i], vmin=vmin, vmax=vmax, marker='o', cmap=cmap, alpha=.5, s=sz**2)
			plotphysio(False, True)
			plotcoast(True, True, True)
			axis([-126, -66, 25, 50])
			cbar = colorbar(orientation='h', pad=.07, aspect=30, shrink=.95)
			cbar.set_label(labs[i])
	subplot(2,5,1)
	title('P correction [s] ({:s})'.format(ccfile))
	subplot(2,5,6)
	title('S correction [s] ({:s})'.format(ccfile))
	fignm = ccfile + '-map.png'
	saveFigure(fignm, opts)

 

def plotmodels(crustmodel0, crustmodel1, imodel):
	print('Plot crustal model and reference model')
	mmodel0 = meanModel(crustmodel0)
	mmodel1 = meanModel(crustmodel1)
	imodel0 = imodel.copy()
	imodel1 = imodel.copy()
	imodel0[0][0] = mmodel0[0][0]
	imodel1[0][0] = mmodel1[0][0]
	# trace model down to 40 km
	dmax = 40
	mtp0, mts0 = vtTime(mmodel0, dmax)
	mtp1, mts1 = vtTime(mmodel1, dmax)
	itp0, its0 = vtTime(imodel0, dmax)
	itp1, its1 = vtTime(imodel1, dmax)
	dtp0 = mtp0 - itp0
	dts0 = mts0 - its0
	dtp1 = mtp1 - itp1
	dts1 = mts1 - its1
	tt0 = 'Crust-Ref: P {:.3f}s S {:.3f}s '.format(dtp0, dts0)
	tt1 = 'Crust-Ref: P {:.3f}s S {:.3f}s '.format(dtp1, dts1)
	print tt0
	print tt1
	# plot
	figure(figsize=(10,16))
	subplots_adjust(left=.07, right=.97, bottom=.05, top=0.96, hspace=.12, wspace=.03)
	rcParams['legend.fontsize'] = 11
	cols = ['b', 'r']
	#
	subplot(211)
	plotcmodel(imodel, cols, 3, '-', label=imodnm.upper())
	plotcmodel(mmodel0, cols, 3, '--', label='Mean crust2')
	xlim(-5,50)
	ylabel('Velocity [km/s]')
	legend(loc=2)
	title(tt0)
	#
	subplot(212)
	plotcmodel(imodel, cols, 3, '-', label=imodnm.upper())
	plotcmodel(mmodel1, cols, 3, '--', label='Mean crust2intopl')
	xlim(-5,50)
	xlabel('Depth [km]')
	ylabel('Velocity [km/s]')
	legend(loc=2)
	title(tt1)
	if opts.savefig:
		savefig('ccmodel-iasp91-crust2.png', format='png')
	else:
		show()

def plotcc(ccfiles, labs, vlims, ofile):
	print('Plot crustal corrections ')
	avals = [ loadtxt(ccfile, usecols=(1,2,4,5))  for ccfile in ccfiles ]
	ncc = len(ccfiles)
	figure(figsize=(18,12))
	subplots_adjust(left=.02, right=.99, bottom=.04, top=0.96, hspace=.06, wspace=.065)
	sz = 5
	for i in range(ncc):
		vals = avals[i]
		lat = vals[:,0]
		lon = vals[:,1]
		tp  = vals[:,2]
		ts  = vals[:,3]
		tps = tp, ts
		for j in range(2):
			subplot(2,ncc,i+1+j*ncc)
			vmin, vmax = vlims[i][j]
			scatter(lon, lat, c=tps[j], vmin=vmin, vmax=vmax, marker='o', cmap=cmap, alpha=.5, s=sz**2)
			plotphysio(False, True)
			plotcoast(True, True, True)
			axis([-126, -66, 25, 50])
			cbar = colorbar(orientation='h', pad=.07, aspect=30, shrink=0.95)
			cbar.set_label(labs[i][j])
	fignm = ofile + '.png'
	#fignm = ofile + '-scale2.png'
	saveFigure(fignm, opts)



if __name__ == '__main__':

	ckey = 'RdBu_r'
	ckey = 'jet'
	cdict = cm.datad[ckey]
	cmap = matplotlib.colors.LinearSegmentedColormap(ckey, cdict)

	fontp = FontProperties()
	fontp.set_family('monospace')

	cfile = '/opt/local/seismo/data/GeolProv/physio/cordillera.xy'
	coastdir = '/opt/local/seismo/data/CoastBoundaries/'
	files = 'coastline-na.xy', 'international-na.xy', 'political-na.xy'
	cfiles = [cfile,] + [coastdir+f  for f in files]
	colors = 'mkkkkk'

	opts, ifiles = getParams()

	stafile = opts.stafile
	imodnm = opts.refmodel
	stadict = readStation(stafile)
	imodel = refModel(imodnm)

	# crustal model and crustal correction partition:
	cmfile0 = 'sta-cmodel-crust2.pkl'
	cmfile1 = 'sta-cmodel-crust2intpol.pkl'
	crustmodel0 = readPickle(cmfile0)
	crustmodel1 = readPickle(cmfile1)
	ccfile0 = 'sta-ccpart-crust2'
	ccfile1 = 'sta-ccpart-crust2intpol'
	ccfile2 = 'sta-ccpart-crust2intpol-na04-lowry'
	mfile = 'sta-moho-na04-lowry'

	if not os.path.isfile(ccfile0):
		ccPartArray(crustmodel0, imodel, -1, stadict, ccfile0)
	if not os.path.isfile(ccfile1):
		ccPartArray(crustmodel1, imodel, -1, stadict, ccfile1)
	if not os.path.isfile(ccfile2):
		if os.path.isfile(mfile):
			mohodict = readStation(mfile)
		else:
			mohodict = readStation('sta-moho-na04')
		ccPartArray(crustmodel1, imodel, mohodict, stadict, ccfile2)

	# colorbar scales
	vlims = [[(None, None),] * 2, ] * 5
	vlims = [ [(-1,1), (-2,2)], [(-1,1), (-2,2)], [(-.4,.4), (-.8,.8)], [(-.4,.4),(-.8,.8)], [(-.3,.3),(-.6,.6)] ] 	
	vlims = [ [(-1,1), (-2,2)], ] * 5
	vlims = [ [(-.5,.5), (-1,1)], ] * 5
	if opts.ccpart is not None:
		if opts.ccpart == 'hist':
			ccPartArrayPlotHist(ccfile0)
			ccPartArrayPlotHist(ccfile1)
			ccPartArrayPlotHist(ccfile2)
		elif opts.ccpart == 'map':
			ccPartArrayPlotMap(ccfile0, vlims)
			ccPartArrayPlotMap(ccfile1, vlims)
			ccPartArrayPlotMap(ccfile2, vlims)
		else:
			print('Unknown option for opts.ccpart.')
			sys.exit()

	# plot crustal model
	if opts.plotmodel:
		plotmodels(crustmodel0, crustmodel1, imodel)

	# crustal correction using crust2intpol and na04-lowry moho:
	crustmodel = crustmodel1
	mfile = 'sta-moho-' + opts.mohomodel

	defmoho = 35.0
	ccfilea = 'sta-cca-' + imodnm
	ccfileb = 'sta-ccb-' + imodnm
	ccfilec = 'sta-ccc-' + imodnm
	ccfiled = 'sta-ccd-' + imodnm
	ccfilee = 'sta-cce-' + imodnm
	ccfilef = 'sta-ccf-' + imodnm
	ccfileg = 'sta-ccg-' + imodnm
	ccfiles = ccfilea, ccfileb, ccfilec, ccfiled, ccfilee, ccfilef, ccfileg
	if opts.crustcorr:
		#if not (os.path.isfile(ccfilea) and os.path.isfile(ccfileb) and os.path.isfile(ccfilec)):
		print('Calculate crustal correction using moho file: '+mfile)
		mohodict = readStation(mfile)
		ccTSMArray(crustmodel, imodel, mohodict, stadict, ccfiles, defmoho)

	# plot crustal corrections:
	ofile = 'sta-cc-' + imodnm
	ccs = 'Topo', 'Topo+Sedi', 'Topo+Sedi+Moho'
	labs = [ [ '{:s} Correction for {:s} [s]'.format(cc, pp) for pp in 'PS' ]  for cc in ccs ]
	# colorbar scales
	vlims = [ [(None, None),] * 2, ] * 3
	#vlims = [ [(-.5,.5), (-1,1)], [(-1,1), (-2,2)], [(-1.2,1.2), (-2.4,2.4)] ]
	#vlims = [ [(-1,1), (-2,2)], ] * 3
	#vlims = [ [(-.5,.5), (-1,1)], ] * 3
	if opts.ccorrplot:
		plotcc(ccfiles, labs, vlims, ofile)

	sys.exit()

	# test:
	mmodel = meanModel(crustmodel0)
	astas = stadict.keys()[:3]
	for sta in astas:
		print('\n--> Station: '+ sta)
		cmodel = crustmodel0[sta]
		ctime, stime, ttime, mtime, ltime = ccPart(cmodel, imodel, mmodel)
		print sta, ctime, stime, ttime, mtime, ltime



