#!/usr/bin/env python
"""
Example python script for SAC plotting replication: p1, p2, prs.

Xiaoting Lou (xlou@u.northwestern.edu)
03/07/2012
"""

from pylab import *
import matplotlib.transforms as transforms
from pysmo.aimbat.sacpickle import loadData
from pysmo.aimbat.plotphase import getDataOpts, PPConfig, sacp1, sacp2, sacprs


# figure
fig = figure(figsize=(9,12))

rectp2 = [.09, .050, .8, .15]
rectp1 = [.09, .245, .8, .33]
rectp0 = [.09, .620, .8, .36]

axp2 = fig.add_axes(rectp2)
axp1 = fig.add_axes(rectp1)
axp0 = fig.add_axes(rectp0)

# read data and then plot
gsac, opts = getDataOpts()

# prs
opts.ynorm = .95
saclist = gsac.saclist
prs = sacprs(saclist, opts, axp0)

# p1
opts.ynorm = 1.7 
p1 = sacp1(saclist, opts, axp1)

# p2
opts.reltime = 0
p2 = sacp2(saclist, opts, axp2)

axp0.set_xlim(625, 762)
axp1.set_xlim(625, 762)
axp2.set_xlim(-45, 65)

# numbering
axs = [axp0, axp1, axp2]
labs = 'ABC'
for ax, lab in  zip(axs, labs):
	tt = '(' + lab + ')'
	trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
	ax.text(-.05, 1, tt, transform=trans, va='center', ha='right', size=16)	

fig.savefig('egplot.png', format='png', dpi=300)
show()


