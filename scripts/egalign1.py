#!/usr/bin/env python
"""
Example python script for seismogram alignments by SAC p1
 
Xiaoting Lou (xlou@u.northwestern.edu)
03/07/2012
"""

import matplotlib.pyplot as plt
import matplotlib.transforms as transforms
from pysmo.aimbat.sacpickle import loadData, SacDataHdrs
from pysmo.aimbat.plotphase import getOptions, sacp1, sacp2, sacprs
from pysmo.aimbat.ttconfig import PPConfig, QCConfig, CCConfig, MCConfig


def axes1(npick=2):
	fig = plt.figure(figsize=(9.5,12.7))
	axs = [fig.add_subplot(1,npick,i+1) for i in range(npick) ]
	plt.subplots_adjust(bottom=.04, top=0.97, left=.065, right=.905, wspace=.4, hspace=.1)
	return axs

def getwin(gsac, opts, pick='t2'):
	'Get time window from array stack'
	sacdh = gsac.stkdh
	twh0, twh1 = opts.pppara.twhdrs
	tw0 = sacdh.gethdr(twh0)
	tw1 = sacdh.gethdr(twh1)
	tref = sacdh.gethdr(pick)
	tw = tw0-tref, tw1-tref
	print('Time window wrt {:s}: [{:.1f}  {:.1f}] s'.format(pick, tw[0], tw[1]))
	return tw

def plotwin(ax, tw, pppara):
	'Plot time window'
	tw0, tw1 = tw
	ymin, ymax = ax.get_ylim()
	a, col = pppara.alphatwfill, pppara.colortwfill
	ax.fill([tw0,tw1,tw1,tw0], [ymin,ymin,ymax,ymax], col, alpha=a, edgecolor=col)

def load():
	'load data'	
	opts, ifiles = getOptions()
	pppara = PPConfig()
	ccpara = CCConfig()
	gsac = loadData(ifiles, opts, pppara)
	if opts.filemode == 'pkl':
		opts.fstack = None
	else:
		opts.fstack = ccpara.fstack
		gsac.stkdh = SacDataHdrs(opts.fstack, opts.delta)
	opts.pppara = pppara
	opts.ccpara = ccpara
	return gsac, opts



if __name__ == '__main__':	
	
	gsac, opts = load()
	saclist = gsac.saclist

	xxlim = -20, 20
	reltimes = [0, 3]
	npick = len(reltimes)
	axs = axes1(npick)
	twa = -10, 10
	twb = getwin(gsac, opts, 't2')
	twins = [twa, twb]
	tts = ['Predicted', 'Measured']
	for i in range(npick):
		opts.reltime = reltimes[i]
		ax = axs[i]
		sacp1(saclist, opts, ax)
		ax.set_xlim(xxlim)
		plotwin(ax, twins[i], opts.pppara)
		ax.set_title(tts[i])

	labs = 'ab'
	for ax, lab in  zip(axs, labs):
		tt = '(' + lab + ')'
		trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
		ax.text(-.05, 1, tt, transform=trans, va='center', ha='right', size=16)	

	plt.savefig('egalignp1.pdf', format='pdf')

	plt.show()	

