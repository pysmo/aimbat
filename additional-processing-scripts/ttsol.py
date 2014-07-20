#!/usr/bin/env python
"""

Estimate solution of Gm=d by  m=G'd:

xlou 01/11/2013

"""

from pylab import *
import os, sys
from scipy.sparse import dok_matrix
from matplotlib.font_manager import FontProperties
from ttcommon import readStation, saveStation
from ppcommon import saveFigure
from ttdict import getParser, getDict, delayPairs, delKeys, lsq


def getGrid(moshell='model.sortedshell'):
	'from getgrid.f'
	print('Read file ' + moshell)
	# read first two lines
	with open(moshell) as mfile:
		mline0 = mfile.readline()
		mline1 = mfile.readline()
	ntr,nt,imx,dmxd,cold,ola,olo,oazi,nshells = array([ float(v)  for v in mline0.split() ])
	ntr, nshells = int(ntr), int(nshells)
	m3d = ntr*nshells	# 3d vel nodes
	mcols = m3d + ntr	# moho nodes
	#return mcols, ntr, (mline0, mline1)
	return ntr, nshells, (mline0, mline1)

def readGD(gfile, dfile, ny):
	d = loadtxt(dfile)
	nx = len(d)
	print('Read  G ({:d} x {:d}) d ({:d} x 1) matrices from files: {:s} {:s}'.format(nx, ny, nx, gfile, dfile))
	#g = zeros(nx*ny).reshape(nx,ny)
	gmat = dok_matrix((nx,ny))
	for ga in loadtxt(gfile):
		i, j, v = ga
		gmat[int(i), int(j)] = v
	g = gmat.tocsr()
	return g, d


def gload(g):
	for ga in loadtxt(gfile):
		i, j, v = ga
		# exclude event nodes:
		if int(j) < ny:
			g[int(i)-1, int(j)-1] = v
	return g

def gread(g):
	with open(gfile) as f:
		for line in f.readlines():
			i, j, v = line.split()
			if int(j) < ny:
				g[int(i)-1, int(j)-1] = v
	return g

def gline(g):
	with open(gfile) as f:
		while True:
			try:
				i, j, v = f.readline().split()
			except:
				break
			if int(j) < ny:
				g[int(i)-1, int(j)-1] = v
	return g


if __name__ == '__main__':

	#opts, ifiles = getParams()

	moshell = 'model.sortedshell'
	dfile = 'tt_data'
	gfile = 'tt_partials'

	ntr, nshells, mlines = getGrid(moshell)
	ny = ntr * nshells	# only vel nodes but not moho nodes

	d = loadtxt(dfile, usecols=(3,))

	nx = len(d)
	print('Read G ({:d} x {:d}) d ({:d} x 1) matrices from files: {:s} {:s}'.format(nx, ny, nx, gfile, dfile))
	g = dok_matrix((nx,ny))
	g = gload()
	#g = gread()
	#g = gline()


	print('Calculate GTd')
	g = g.tocsr()
	gtd = g.T*d
	print('gtd min max : {:7.3f} {:7.3f}'.format(gtd.min(), gtd.max() ))
	print('Normalize by norm of G columns')
	g = g.tocsc()
	nr, nc = g.shape
	#gcn = [ [i,(g[:,i].data**2).sum()]  for i in range(nc) if g[:,i].getnnz() > 0]
	indptr = g.indptr
	data = g.data
	#gcn = [ [i, sum(data[indptr[i]:indptr[i+1]]**2)]  for i in range(nc)  if indptr[i+1] > indptr[i] ]
	for i in range(nc):
		if indptr[i+1] > indptr[i]:
			#print sum(data[indptr[i]:indptr[i+1]]**2)
			#gtd[i] /= sum(data[indptr[i]:indptr[i+1]]**2)
			gtd[i] /= sum(data[indptr[i]:indptr[i+1]])

	print('gtd min max : {:7.3f} {:7.3f}'.format(gtd.min(), gtd.max() ))

	# write to solution file
	solfile = 'gtd'
	with open(solfile, 'w') as f:
		for line in mlines:
			f.write(line)
		fmt = '{:f} '*gtd.shape[0] #+ '\n'
		f.write(fmt.format(*gtd))
		print('Put zeros in moho grid')
		fmt = '{:f} '*ntr + '\n'
		zz = zeros(ntr)
		f.write(fmt.format(*zz))
