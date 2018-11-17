#!/usr/bin/env python
#------------------------------------------------
# Filename: seismodata.py
#   Author: Arnav Sankaran, Xiaoting Lou
#    Email: arnavsankaran@gmail.com
#
# Copyright (c) 2016 Arnav Sankaran
#------------------------------------------------
"""
Python module for extracting waveform data from sac files.

:copyright:
    Arnav Sankaran, Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""

from sacpickle import readPickle
from numpy import linspace, array
from scipy import signal

import sys
from ttconfig import PPConfig, QCConfig, CCConfig, MCConfig, getParser
from sacpickle import loadData
from qualsort import initQual
from algmccc import findPhase

from algiccs import ccWeightStack
import filtering


class DataItem(object):
    def __init__(self, xPts, yPts, name):
        self.x = xPts
        self.y = yPts
        self.name = name

def getOptions():
    """ Parse arguments and options. """
    parser = getParser()
    maxsel = 37
    maxdel = 3
    maxnum = maxsel, maxdel
    twcorr = -15, 15
    sortby = '1'
    fill = 1
    reltime = 0
    xlimit = -30, 30
    parser.set_defaults(xlimit=xlimit)
    parser.set_defaults(twcorr=twcorr)
    parser.set_defaults(reltime=reltime)
    parser.set_defaults(maxnum=maxnum)
    parser.set_defaults(sortby=sortby)
    parser.set_defaults(fill=fill)
    parser.add_option('-b', '--boundlines', action="store_true", dest='boundlines_on',
        help='Plot bounding lines to separate seismograms.')
    parser.add_option('-n', '--netsta', action="store_true", dest='nlab_on',
        help='Label seismogram by net.sta code instead of SAC file name.')
    parser.add_option('-m', '--maxnum',  dest='maxnum', type='int', nargs=2,
        help='Maximum number of selected and deleted seismograms to plot. Defaults: {0:d} and {1:d}.'.format(maxsel, maxdel))
    parser.add_option('-p', '--phase',  dest='phase', type='str',
        help='Seismic phase name: P/S .')
    parser.add_option('-s', '--sortby', type='str', dest='sortby',
        help='Sort seismograms by i (file indices), or 0/1/2/3 (quality factor all/ccc/snr/coh), or t (time pick diff), or a given header (az/baz/dist..). Append - for decrease order, otherwise increase. Default is {:s}.'.format(sortby))
    parser.add_option('-t', '--twcorr', dest='twcorr', type='float', nargs=2,
        help='Time window for cross-correlation. Default is [{:.1f}, {:.1f}] s'.format(twcorr[0],twcorr[1]))
    parser.add_option('-g', '--savefig', action="store_true", dest='savefig',
        help='Save figure instead of showing.')
    opts, files = parser.parse_args(sys.argv[1:])
    if len(files) == 0:
        print(parser.usage)
        sys.exit()
    return opts, files


def getDataOpts():
    'Get SAC Data and Options'
    opts, ifiles = getOptions()
    pppara = PPConfig()
    qcpara = QCConfig()
    ccpara = CCConfig()
    mcpara = MCConfig()

    gsac = loadData(ifiles, opts, pppara)

    # set defaults
    filterParameters = {}
    filterParameters['apply'] = False
    filterParameters['advance'] = False
    filterParameters['band'] = 'bandpass'
    filterParameters['lowFreq'] = 0.05
    filterParameters['highFreq'] = 0.25
    filterParameters['order'] = 2
    filterParameters['reversepass'] = False
    opts.filterParameters = filterParameters

    # override defaults if already set in SAC files
    firstSacdh = gsac.saclist[0]
    if hasattr(firstSacdh, 'user0'):
        filterParameters['lowFreq'] = firstSacdh.user0
    if hasattr(firstSacdh, 'user1'):
        filterParameters['highFreq'] = firstSacdh.user1
    if hasattr(firstSacdh, 'kuser0'):
        filterParameters['band'] = firstSacdh.kuser0
    if hasattr(firstSacdh, 'kuser1'):
        filterParameters['order'] = int(firstSacdh.kuser1)

    mcpara.delta = opts.delta
    opts.qheaders = qcpara.qheaders
    opts.qweights = qcpara.qweights
    opts.qfactors = qcpara.qfactors
    opts.hdrsel = qcpara.hdrsel
    opts.fstack = ccpara.fstack
    ccpara.qqhdrs = qcpara.qheaders
    ccpara.twcorr = opts.twcorr
    # find phase:
    if opts.phase is None:
        phase = findPhase(ifiles[0])
        print ('Found phase to be: ' + phase + '\n')
    else:
        phase = opts.phase
    mcpara.phase = phase
    opts.qcpara = qcpara
    opts.ccpara = ccpara
    opts.mcpara = mcpara
    opts.pppara = pppara
    # more options:
    opts.upylim_on = False
    opts.twin_on = True
    opts.sort_on = True
    opts.pick_on = True
    opts.zero_on = False
    opts.nlab_on = True
    opts.ynormtwin_on = True
    #checkCoverage(gsac, opts)
    initQual(gsac.saclist, opts.hdrsel, opts.qheaders)
    return gsac, opts

def getWaveDataSetFromSacItem(sacitem, opts):
    b = sacitem.b
    npts = sacitem.npts
    delta = sacitem.delta
    x = linspace(b, b + (npts - 1) * delta, npts)
    y = array(sacitem.data)

    if hasattr(opts, 'filterParameters') and opts.filterParameters['apply']:
        originalTime = x
        originalSignalTime = y
        filteredSignalTime, filteredSignalFreq, adjusted_w, adjusted_h = filtering.filtering_time_freq(originalTime, originalSignalTime, opts.delta, opts.filterParameters['band'], opts.filterParameters['highFreq'], opts.filterParameters['lowFreq'], opts.filterParameters['order'], opts.filterParameters['reversepass'])
        return DataItem(x, filteredSignalTime, sacitem.netsta)

    twh0, twh1 = opts.pppara.twhdrs
    tw0 = sacitem.gethdr(twh0)
    tw1 = sacitem.gethdr(twh1)
    twindow = [tw0, tw1]

    if opts.ynorm > 0:
        if opts.ynormtwin_on:
            try:
                indmin, indmax = numpy.searchsorted(x, twindow)
                indmax = min(len(x) - 1, indmax)
                thisd = y[indmin : indmax + 1]
                dnorm = dataNorm(thisd)
            except:
                dnorm = dataNorm(y)
        else:
            dnorm = dataNorm(y)
        dnorm = 1 / dnorm * opts.ynorm * .5
    else:
        dnorm = 1
    y = y * dnorm

    return DataItem(x, y, sacitem.netsta)

def dataNorm(d, w=0.05):
    dmin, dmax = d.min(), d.max()
    dnorm = max(-dmin, dmax) * (1+w)
    return dnorm
