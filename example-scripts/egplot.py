#!/usr/bin/env python
"""
Example python script for SAC plotting replication: p1, p2, prs.

Xiaoting Lou (xlou@u.northwestern.edu)
03/07/2012
"""

import matplotlib.pyplot as plt
import matplotlib.transforms as transforms
from pysmo.aimbat.plotphase import getDataOpts, sacp1, sacp2, sacprs

# figure axes
fig = plt.figure(figsize=(9,12))
rectp2 = [.09, .050, .8, .15]
rectp1 = [.09, .245, .8, .33]
rectp0 = [.09, .620, .8, .36]
axp2 = fig.add_axes(rectp2)
axp1 = fig.add_axes(rectp1)
axp0 = fig.add_axes(rectp0)

# read data and plot
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
# set x limits
axp0.set_xlim(625, 762)
axp1.set_xlim(625, 762)
axp2.set_xlim(-45, 65)
# numbering
axs = [axp0, axp1, axp2]
labs = 'abc'
for ax, lab in  zip(axs, labs):
	tt = '(' + lab + ')'
	trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
	ax.text(-.05, 1, tt, transform=trans, va='center', ha='right', size=16)	

fig.savefig('egplot.pdf', format='pdf')
plt.show()


