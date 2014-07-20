#!/usr/bin/env python
# Module for extracting relative delay times from results of MCCC.
###
#  when there is no S arrivals, net name is not right (same as sta name).
### xlou 10/27/2009 

from numpy import *
import os, sys, glob

try:
	import cPickle as pickle
except:
	import pickle

####### read and write pickle
def writePickle(d, picklefile):
	fh = open(picklefile, 'w')
	pickle.dump(d, fh)
	fh.close()
	
def	readPickle(picklefile):
	fh = open(picklefile, 'r')
	d = pickle.load(fh)
	fh.close()
	return d
	
#######
def readDict(ifilenm):
	""" Read a text file to a dictionary with first column as keys.
		For ref.tsta files: key=sta, values = lat lon ele.
		Make numbers float if possible.
	"""
	ifile = open(ifilenm,'r')
	lines = ifile.readlines()
	ifile.close()
	ddict = {}
	for line in lines:
		#if line[0] != ' ': continue	
		sline = line.split()
		if sline == []: continue	# skip empty lines
		sta = sline[0]
		values = sline[1:]
		for i in arange(len(values)):
			try:
				values[i] = float(values[i])
			except:
				pass
		ddict[sta] = values
	return ddict


#######
def mcccDict(dfilenm):
	""" Read MCCC delay times to a dictionary.
		Key: sta
		Values: SAC file name, real delay times.
	"""
	dfile = open(dfilenm,'r')
	lines = dfile.readlines()
	dfile.close()

	mdict = {}	
	for line in lines:
		if line[0] != ' ': continue
		sta = line[1:5].split()[0]
		ccoef = float(line[26:33])
		ccorr = float(line[57:62])
		dt = float(line[63:71])
		sacf = line[82:].split()[0]
		#net = sacf.split('.')[0]
		#net = net.upper()
		#netsta = net + '.' + sta
		#print netsta, ccoef,ccorr,dt,sacf
		mdict[sta] = [sacf,dt]
	return mdict


#######
#def delayDict(mdict,rdict,ofilenm):
def delayDict(dfilenm,rfilenm,ofilenm):
	""" Return delay times dictionary with more attributes.
		==> Merge mcccDict and refDict (only use lat lon ele [:3]).
		Write dictionary of delay times to a text file.
	"""
	mdict = mcccDict(dfilenm)
	rdict = readDict(rfilenm)
	ddict = {}
	ofile = open(ofilenm,'w')
	for sta in sorted(mdict.keys()):
		refdt = rdict[sta][:3] + mdict[sta]
		ddict[sta] = refdt
		ofile.write(' %-4s %9.5f %10.5f %5.3f %-16s %6.3f\n' % tuple([sta]+refdt))
	ofile.close()
	#pkfile = ofilenm + '.pkl'
	#writePickle(ddict,pkfile)
	return ddict


#######
def nullDict(rfilenm,nodt=-99.999):
	""" Return dictionary of ref.tsta when delay times are not available.
	"""
	rdict = readDict(rfilenm)
	ndict = {}
	for sta in sorted(rdict.keys()):
		ndict[sta] = rdict[sta][:3] + [sta] + [nodt]
	return ndict


#######
def psdDict(pdict,sdict,rdict,ofilenm,nodt=-99.999):
#def psdDict(pfilenm,sfilenm,rfilenm,ofilenm,nodt=-99.999):
	""" Return delay times of P and S together to a common dictonary.
		Write the dict to a pickle file.
	"""
	#rdict = readDict(rfilenm)
	#pmdict = mcccDict(pfilenm)
	#smdict = mcccDict(sfilenm)
	#pdict = delayDict(pmdict,rdict,ofilenm)
	#sdict = delayDict(smdict,rdict,ofilenm)

	dicts = [pdict,sdict]
	nd = len(dicts)
	psdict = {}
	dt = zeros(nd)
	ofile = open(ofilenm,'w')
	for sta in sorted(rdict.keys()):
		for i in arange(nd):
			ddict = dicts[i]
			if sta in ddict:
				dt[i] = ddict[sta][4]
				net = ddict[sta][3].split('.')[0].upper()
			else:
				dt[i] = nodt
		if dt[0] != nodt or dt[1] != nodt: 
			refdt = rdict[sta][:3] + [net] + list(dt)
			psdict[sta] = refdt
			ofile.write(' %-4s %9.5f %10.5f %5.3f %-4s %7.3f %7.3f\n' % tuple([sta]+refdt))
	ofile.close()
	pkfile = ofilenm + '.pkl'
	writePickle(ddict,pkfile)
	return psdict

#######
def dtDict(stas,alldict,nodt=-99.999):
	""" Return ddict of P and S delays from all events, using station names as keys.
		alldict: alldict[ev] = [psdict,evhypo], where psdict = dtime.psdDict().
		stas: station names, all or only part of the stations are used as keys.
		ddict: dictionary of P (col 0 2 4...) and S (col 1 3 5...) delay times
	"""
	ddict = {}
	for ev in sorted(alldict.keys()):
#		print '==============',ev
#		psdict,mw = alldict[ev]
		tt = alldict[ev]
		psdict = tt[0]
# average P and S delay
#		mw = tt[1]
#		avp,avs = tt[1:3]

		for sta in stas:
			try:
				dt = psdict[sta][4:6]
			except:
				dt = [nodt,nodt]
			if sta in ddict.keys():
				ddict[sta] += dt
			else:
				ddict[sta] = dt
	# remove mean
	nn = len(ddict[ddict.keys()[0]])
	for i in arange(nn):
		mt = 0.0
		nt = 0
		for sta in stas:
			if ddict[sta][i] > nodt+1: 
				mt += ddict[sta][i]
				nt += 1
		if nt > 0:
			mt /= nt
			for sta in stas:
				if ddict[sta][i] > nodt+1:
					ddict[sta][i] -= mt
	return ddict


#######
def realDelay(ddict,nodt=-99.999):
	""" Return real delay times, excluding nodt=-99.999, as array for plotting.
		ddict: dictionary of P (col 0 2 4...) and S (col 1 3 5...) delay times
	"""
	realtp = {}
	realts = {}
	for sta in ddict.keys():
		stp = []
		sts = []
		ndt = len(ddict[sta])
		for dt in ddict[sta][0:ndt:2]:
			if dt > nodt:
				stp.append(dt)
		for dt in ddict[sta][1:ndt:2]:
		    if dt > nodt:
		        sts.append(dt)
		if stp != []:
			realtp[sta] = stp
		if sts != []:
			realts[sta] = sts
	return realtp,realts

#######
def mergeDict(adict,bdict):
	""" Return a dictionary of common keys, and both values of two dictionaries.
		bdict.keys() is a subset of adict.keys()
		adict.values
		e.g.: adict = dist, bdict = ddict
			return an array of dist and delay.
	"""
	dd = []
	for sta in bdict.keys():
		dd.append([adict[sta]] + bdict[sta])
	dd = array(sorted(dd))
	return dd

######
def saveDict(alldict,ofilenm):
	""" Save delay dictionay of all events to ascii file.
	    Output file is like that of psdDict() and dtget.py
	"""
	ofile = open(ofilenm,'w')
	for ev in alldict.keys():
		dt = alldict[ev][0]
		ofile.write('/ %s \n' % ev)
		for sta in sorted(dt.keys()):
			ofile.write(' %-4s %9.5f %10.5f %5.3f %-4s %7.3f %7.3f\n' % tuple([sta]+dt[sta]))
	ofile.close()
	return 

#######
#since 11/17/2010
#######
def getEventDelay(evdir='.', ipick='t4', dtfile='pystdt', psfile='tps'):
	""" Get delays for an event.
		ipick can be t4/west/east
		Output $dtfile for each p0/s0 and $psfile for both p/s delays.
	"""
	# reference file for station and event info
	tsta = 'ref.tsta'
	teqs = 'event.list'
	# output files
	dtfile += '.' + ipick
	psfile += '.' + ipick
	tpsfile = evdir + '/' + psfile
	### pseudo delay time if it is not available
	nodt = -99.999
	# One of P and S must exists.
	pdir = evdir + '/p0/'
	sdir = evdir + '/s0/'
	ref = glob.glob(pdir+tsta) + glob.glob(sdir+tsta)
	rfilenm = ref[0]
	# find hypocenter and magnitude
	evh = glob.glob(pdir+teqs) + glob.glob(sdir+teqs)
	efilenm = evh[0]
	efile = open(efilenm, 'ro')
	line = efile.readline()
	efile.close()
	sline = line.split()
	evhypo = [float(sline[0]), float(sline[1]), float(sline[3]), float(sline[10])]
	# P
	if os.path.isdir(pdir):
		pfilenm = glob.glob(pdir+'[1-9]*x.'+ipick)
		print '  P: ', pfilenm
		if pfilenm != []:
			pdict = delayDict(pfilenm[0], rfilenm, pdir+dtfile)
		else:
			pdict = nullDict(rfilenm, nodt)
	else:
		pdict = nullDict(rfilenm, nodt)
	# S
	if os.path.isdir(sdir):
		sfilenm = glob.glob(sdir+'[1-9]*x.'+ipick)
		print '  S: ', sfilenm
		if sfilenm != []:
			sdict = delayDict(sfilenm[0], rfilenm, sdir+dtfile)
		else:
			sdict = nullDict(rfilenm, nodt)
	else:
		sdict = nullDict(rfilenm, nodt)
	# both
	rdict = readDict(rfilenm)
	psdict = psdDict(pdict, sdict, rdict, tpsfile, nodt)
	return psdict, evhypo

#######
if __name__ == '__main__':
#	dir = '/Users/xlou/work/mccc/na/auto/usarray/2008/data/mw65/Event_2008.07.23.15.26.19.950/'
#	pfilenm = dir + 'p0/2008205.15261995.uupx.t4'
#	sfilenm = dir + 's0/2008205.15261995.uusx.t4'

#	dir = '/Users/xlou/work/new/testcc/mw70/Event_2008.07.05.02.12.04.480/'
#	pfilenm = dir + 'p0/2008187.02120448.uupx.t4'
#	sfilenm = dir + 's0/2008187.02120448.uusx.t4'

	rfilenm = dir + 'p0/ref.tsta'
	
	ista = '109C'
	rdict = readDict(rfilenm)
	#pmdict = mcccDict(pfilenm)
	#smdict = mcccDict(sfilenm)
	#pdict = delayDict(pmdict,rdict,'stdt.t4.p')
	#sdict = delayDict(smdict,rdict,'stdt.t4.s')
	#ddict = readDict('stdt.t4.p')
	#ndict = nullDict(rdict)
	#print pdict[ista], ddict[ista]

	pdict = delayDict(pfilenm,rfilenm,'stdt.t4.p')
	sdict = delayDict(sfilenm,rfilenm,'stdt.t4.s')
	psdict = psdDict(pdict,sdict,rdict,'tps',-99.999)
	ndict = nullDict(rfilenm)
	#psdict = psdDict(pfilenm,sfilenm,rfilenm,'tps',-99.999)
	print ista,psdict[ista]

	rtp,rts = realDelay(psdict)	


