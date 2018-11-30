#!/usr/bin/env python
"""
Example python script for seismogram alignments by SAC p2
 
Xiaoting Lou (xlou@u.northwestern.edu)
03/07/2012
"""

import matplotlib.pyplot as plt
import matplotlib.transforms as transforms
from pysmo.aimbat.sacpickle import loadData, SacDataHdrs
from pysmo.aimbat.plotphase import getOptions, sacp1, sacp2, sacprs
from pysmo.aimbat.ttconfig import PPConfig, QCConfig, CCConfig, MCConfig


def axes2(npick=4):
	fig2 = plt.figure(figsize=(9,12))
	ax0 = fig2.add_subplot(npick,1,1)
	axsacs = [ ax0 ] + [ fig2.add_subplot(npick,1,i+1, sharex=ax0) for i in range(1, npick) ]
	plt.subplots_adjust(bottom=.05, top=0.96, left=.1, right=.97, wspace=.5, hspace=.24)
	return axsacs


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

	reltimes = [0, 1, 2, 3]
	tlabs = 'abcd'
	npick = len(reltimes)
	axs = axes2(npick)

	for i in range(npick):
		opts.reltime = reltimes[i]
		tpick = 't' + str(opts.reltime)
		ax = axs[i]
		sacp2(saclist, opts, ax)
		#ax.text(0.03,0.93, 'Aligned by '+ tpick.upper() , fontsize=12,
		#	horizontalalignment='left',
		#	verticalalignment='top', 
		#	transform=ax.transAxes)
		ax.set_xlim(xxlim)
		tt = '(' + tlabs[i] + ')'
		trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
		ax.text(-.05, 1, tt, transform=trans, va='center', ha='right', size=16)	

	plt.savefig('egalignp2.pdf', format='pdf')
	plt.show()	

