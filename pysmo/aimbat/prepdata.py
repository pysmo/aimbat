#!/usr/bin/env python
#------------------------------------------------
# Filename: prepdata.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2018 Xiaoting Lou
#------------------------------------------------
"""

Python module for preparing time and data arrays (original and filtered in memory) for plotting.
 
:copyright:
    Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""

import numpy as np
import sys
from pysmo.aimbat import qualsort, ttconfig
from pysmo.aimbat import sacpickle as sacpkl
from pysmo.aimbat import filtering as ftr

def dataNorm(d, w=0.05):
    """ 
    Calculate normalization factor for d, which can be multi-dimensional arrays.
    Extra white space is added.
    """
    dmin, dmax = d.min(), d.max()
    dnorm = max(-dmin, dmax) * (1+w)
    return dnorm

def dataNormWindow(d, t, twindow):
    """
    Calculate normalization factor in a time window.
    """
    try:
        indmin, indmax = np.searchsorted(t, twindow)
        indmax = min(len(t)-1, indmax)
        thisd = d[indmin:indmax+1]
        dnorm = dataNorm(thisd)
    except:
        dnorm = dataNorm(d)
    return dnorm

def axLimit(minmax, w=0.05):
    """ 
    Calculate axis limit with white space (default 5%) from given min/max values.
    """
    ymin, ymax = minmax
    dy = ymax - ymin
    ylim = [ymin-w*dy, ymax+w*dy]
    return ylim

def findPhase(filename):
    """ Find phase (P or S) from component info (BH?) in file name 
    """
    lowf = filename.lower()
    ind = lowf.find('bh')
    zt = lowf[ind+2]
    if zt == 'z':
        phase = 'P'
    elif zt == 't':
        phase = 'S'
    else:
        print('Fail to identify phase. Exit.')
        sys.exit()
    return phase

def getFilterPara(sacdh, pppara):
    """
    Get default filter parameters from ttdefaults.conf.
    Override defaults if already set in SAC file
    """
    filterParameters = {}
    filterParameters['band'] = pppara.fvalBand
    filterParameters['lowFreq'] = pppara.fvalLowFreq
    filterParameters['highFreq'] = pppara.fvalHighFreq
    filterParameters['order'] = pppara.fvalOrder
    filterParameters['apply'] = pppara.fvalApply==1
    filterParameters['reversepass'] = pppara.fvalRevPass==1
    # override defaults if already set in SAC files
#    if hasattr(sacdh, pppara.fhdrLowFreq):
    if sacdh.gethdr(pppara.fhdrLowFreq) != -12345.:
        filterParameters['lowFreq'] = sacdh.gethdr(pppara.fhdrLowFreq)
    if sacdh.gethdr(pppara.fhdrHighFreq) != -12345.:
        filterParameters['highFreq'] = sacdh.gethdr(pppara.fhdrHighFreq)
    if sacdh.gethdr(pppara.fhdrBand) != '-1234567':
        filterParameters['band'] =  sacdh.gethdr(pppara.fhdrBand)
    if int(sacdh.gethdr(pppara.fhdrOrder)) != -12345:
        filterParameters['order'] = int(sacdh.gethdr(pppara.fhdrOrder))
    filterParameters['apply'] = sacdh.gethdr(pppara.fhdrApply)==1
    filterParameters['reversepass'] = sacdh.gethdr(pppara.fhdrRevPass)==1
    return filterParameters

def setFilterPara(sacdh, pppara, filterParameters):
    """
    Set filter parameters dict to sacdh.
    """
    sacdh.sethdr(pppara.fhdrApply,    int(filterParameters['apply']))
    sacdh.sethdr(pppara.fhdrBand,     filterParameters['band'])
    sacdh.sethdr(pppara.fhdrLowFreq,  filterParameters['lowFreq'])
    sacdh.sethdr(pppara.fhdrHighFreq, filterParameters['highFreq'])
    sacdh.sethdr(pppara.fhdrOrder,    filterParameters['order'])
    sacdh.sethdr(pppara.fhdrRevPass,  int(filterParameters['reversepass']))
    return

def seisApplyFilter(saclist, filtParas):
    'Filter seismograms by butterworth filter'
    for sacdh in saclist:
        origTimeT = sacdh.time
        origDataT = sacdh.data
        origTimeF, origDataF = ftr.time_to_freq(origTimeT, origDataT, sacdh.delta)
        filtDataT, filtDataF, adjw, adjh = ftr.filtering_time_freq(origTimeT, origDataT, sacdh.delta, filtParas['band'], filtParas['highFreq'], filtParas['lowFreq'], filtParas['order'], filtParas['reversepass'])
        sacdh.datamem = filtDataT
    return

def seisUnApplyFilter(saclist):
    'Filter seismograms by butterworth filter'
    for sacdh in saclist:
        sacdh.datamem = sacdh.data
    return

def seisTimeData(saclist):
    'Create time and data (original and in memory) arrays'
    for sacdh in saclist:
        b, npts, delta = sacdh.b, sacdh.npts, sacdh.delta
        sacdh.time = np.linspace(b, b+(npts-1)*delta, npts)
        sacdh.datamem = sacdh.data.copy()
    return 

def seisTimeRefr(saclist, opts):
    'get reference time for each seismogram'
    reltime = opts.reltime
    for sacdh in saclist:
        if reltime >= 0:
            reftime = sacdh.thdrs[reltime]
            if reftime == -12345.0:
                out = 'Time pick T{0:d} is not defined in SAC file {1:s} of station {2:s}'
                print(out.format(reltime, sacdh.filename, sacdh.netsta))
                sys.exit()
            else:
                sacdh.reftime = reftime
        else:
            sacdh.reftime = 0.
    return

def seisTimeWindow(saclist, twhdrs):
    'get time window for each seismogram'
    for sacdh in saclist:
        sacdh.twhdrs = twhdrs
        tw0 = sacdh.gethdr(twhdrs[0])
        tw1 = sacdh.gethdr(twhdrs[1])    
        if tw0 == -12345.0:
            tw0 = sacdh.time[0]
        if tw1 == -12345.0:
            tw1 = sacdh.time[-1]
        sacdh.twindow = [tw0, tw1] # absolute time values
    return


def sacDataNorm(sacdh, opts):
    'get data normalization factor one seismogram'
    if opts.ynormtwin_on:
        dnorm = dataNormWindow(sacdh.datamem, sacdh.time, sacdh.twindow)
    else:
        dnorm = dataNorm(sacdh.datamem)
    sacdh.datnorm = 1/dnorm * opts.ynorm/2
    return

def seisDataNorm(saclist, opts):
    'get data normalization factor each seismogram'
    for sacdh in saclist:
        sacDataNorm(sacdh, opts)
    return

def seisWave(sacdh):
    'Calculate waveform X and Y for plot'
    x = sacdh.time - sacdh.reftime
    y = sacdh.datamem * sacdh.datnorm
    return x, y 

def seisDataBaseline(gsac):
    """
    Create plotting baselines for each seismogram in selected and deselected sac lists
    Example
            delist (n=5)     selist a(na=11)
        [ -5, -4, -3, -2, -1] [0,  1, 2, 3, 4, 5, 6, 7, 8,  9, 10] <-- yindex
        [  5,  4,  3,  2,  1] [0, -1,-2,-3,-4,-5,-6,-7,-8, -9,-10] <-- ybases
    """
    # similar to plotutils.indexBaseTick for yindex, ybases and yticks
    # Haven't yet set ytick = -ybase 
    for i in range(-len(gsac.delist),0):
        gsac.delist[i].datbase = -i
    for i in range(len(gsac.selist)):
        gsac.selist[i].datbase = -i
    gsac.stkdh.datbase = 0
    return

def prepData(gsac, opts):
    """
    Prepare data for plotting
    """  
    opts.filterParameters = getFilterPara(gsac.saclist[0], opts.pppara)
    print('--> Prepare data for plotting')
    seisTimeData(gsac.saclist)
    seisTimeWindow(gsac.saclist, opts.pppara.twhdrs)
    if opts.filterParameters['apply']:
        seisApplyFilter(gsac.saclist, opts.filterParameters)
    seisTimeRefr(gsac.saclist, opts)
    seisDataNorm(gsac.saclist, opts)
    return gsac

def prepStack(opts):
    'Prep stack from existing sacfile opts.fstack'
    stkdh = sacpkl.SacDataHdrs(opts.fstack, opts.delta)
    seisTimeData([stkdh,])
    seisTimeWindow([stkdh,], opts.pppara.twhdrs)
    if opts.filterParameters['apply']:
        seisApplyFilter([stkdh,], opts.filterParameters)
    seisTimeRefr([stkdh,], opts)
    seisDataNorm([stkdh,], opts)
    qualsort.initQual([stkdh,], opts.hdrsel, opts.qheaders)
    return stkdh
                
def seisSort(gsac, opts):
    'Sort seismograms by file indices, quality factors, time difference, or a given header.'
    sortby = opts.sortby
    # determine increase/decrease order
    if sortby[-1] == '-':
        sortincrease = False
        sortby = sortby[:-1]
    else:
        sortincrease = True
#    opts.labelqual = True 
    # sort 
    if sortby == 'i':   
        gsac.selist, gsac.delist = qualsort.seleSeis(gsac.saclist)
        print('Select seismograms by sacdh.selected')
    elif sortby[0] == 't':    # by time difference
#        ipick = opts.qcpara.ichdrs[0]
#        wpick = 't'+str(opts.reltime)
        ipick = 't'+sortby[2]
        wpick = 't'+sortby[1]
        if ipick == wpick:
            print('Same time pick: {0:s} and {1:s}. Exit'.format(ipick, wpick))
            sys.exit()
        gsac.selist, gsac.delist = qualsort.sortSeisHeaderDiff(gsac.saclist, ipick, wpick, sortincrease)
    elif sortby.isdigit() or sortby in opts.qheaders + ['all',]: # by quality factors
        if sortby == '0' or sortby == 'all':
            opts.qweights = [1./3, 1./3, 1./3]
            print('Sort by all quality factors: ccc+snr+coh')
        elif sortby == '1' or sortby == 'ccc':
            opts.qweights = [1, 0, 0]
            print('Sort by quality factor ccc (Cross Correlation Coefficient)')
        elif sortby == '2' or sortby == 'snr':
            opts.qweights = [0, 1, 0]
            print('Sort by quality factor snr (Signal/Noise Ratio)')
        elif sortby == '3' or sortby == 'coh':
            opts.qweights = [0, 0, 1]
            print('Sort by quality factor coh (Coherence)')
        gsac.selist, gsac.delist = qualsort.sortSeisQual(gsac.saclist, opts.qheaders, opts.qweights, opts.qfactors, sortincrease)
    else: # by a given header
        gsac.selist, gsac.delist = qualsort.sortSeisHeader(gsac.saclist, sortby, sortincrease)
    return


def paraDataOpts(opts, ifiles):
    'Common parameters, data and options'
    pppara = ttconfig.PPConfig()
    qcpara = ttconfig.QCConfig()
    ccpara = ttconfig.CCConfig()
    mcpara = ttconfig.MCConfig()
    gsac = sacpkl.loadData(ifiles, opts, pppara)
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
    # initialize quality factors
    qualsort.initQual(gsac.saclist, opts.hdrsel, opts.qheaders)
    return gsac, opts



