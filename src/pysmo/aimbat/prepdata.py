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
from scipy import signal
from pysmo.aimbat import qualsort, ttconfig
from pysmo.aimbat import sacpickle as sacpkl


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

def getFilterPara(gsac, pppara):
    #get default filter parameters
    filterParameters = {}
    filterParameters['band'] = pppara.fvalBand
    filterParameters['lowFreq'] = pppara.fvalLowFreq
    filterParameters['highFreq'] = pppara.fvalHighFreq
    filterParameters['order'] = pppara.fvalOrder
    if pppara.fvalApply == 'True':
        filterParameters['apply'] = True
    else:
        filterParameters['apply'] = False
    if pppara.fvalRevPass == 'True':
        filterParameters['reversepass'] = True
    else:
        filterParameters['reversepass'] = False
    # override defaults if already set in SAC files
    firstSacdh = gsac.saclist[0]
    if hasattr(firstSacdh, pppara.fhdrLowFreq):
        filterParameters['lowFreq'] = firstSacdh.__getattr__(pppara.fhdrLowFreq)
    if hasattr(firstSacdh, pppara.fhdrHighFreq):
        filterParameters['highFreq'] = firstSacdh.__getattr__(pppara.fhdrHighFreq)
    if hasattr(firstSacdh, pppara.fhdrBand):
        filterParameters['band'] = firstSacdh.__getattr__(pppara.fhdrBand)
    if hasattr(firstSacdh, pppara.fhdrOrder):
        filterParameters['order'] = int(firstSacdh.__getattr__(pppara.fhdrOrder))
    return filterParameters

def createFilter(filterParameters, delta):
    'Create butterworth filter. Default is bandpass'
    NYQ = 1.0/(2*delta)
    Wn = [filterParameters['lowFreq']/NYQ,filterParameters['highFreq']/NYQ]
    B, A = signal.butter(filterParameters['order'], Wn, analog=False, btype='bandpass')
    if filterParameters['band']=='lowpass':
        Wn = filterParameters['lowFreq']/NYQ
        B, A = signal.butter(filterParameters['order'], Wn, analog=False, btype='lowpass')
    elif filterParameters['band']=='highpass':
        Wn = filterParameters['highFreq']/NYQ
        B, A = signal.butter(filterParameters['order'], Wn, analog=False, btype='highpass')
    return NYQ, Wn, B, A

def seisDataFilter(gsac, opts):
    'Filter seismograms'
    NYQ, Wn, B, A = createFilter(opts.filterParameters, opts.delta)
    for sacdh in gsac.saclist:
        sacdh.datamem = signal.lfilter(B, A, sacdh.data)
    return 

def seisTimeData(gsac):
    'Create time and data (original and in memory) arrays'
    for sacdh in gsac.saclist:
        b, npts, delta = sacdh.b, sacdh.npts, sacdh.delta
        sacdh.time = np.linspace(b, b+(npts-1)*delta, npts)
        sacdh.datamem = sacdh.data.copy()
    return 

def seisTimeRefr(gsac, opts):
    'get reference time for each seismogram'
    reltime = opts.reltime
    for sacdh in gsac.saclist:
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

def seisTimeWindow(gsac, twhdrs):
    'get time window for each seismogram'
    for sacdh in gsac.saclist:
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

def seisDataNorm(gsac, opts):
    'get data normalization factor each seismogram'
    for sacdh in gsac.saclist:
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
    # see plotutils.indexBaseTick for yindex, ybases and yticks
    # no trace at ybase=0; ytick = -ybase
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
    opts.filterParameters = getFilterPara(gsac, opts.pppara)
    print('Prepare data for plotting')
    seisTimeData(gsac)
    seisTimeWindow(gsac, opts.pppara.twhdrs)
    if opts.filterParameters['apply']:
        seisDataFilter(gsac, opts)
    seisTimeRefr(gsac, opts)
    seisDataNorm(gsac, opts)
    return gsac

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
    elif sortby == 't':    # by time difference
        ipick = opts.qcpara.ichdrs[0]
        wpick = 't'+str(opts.reltime)
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
    convertColors(opts, pppara)
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


def convertColors(opts, pppara):
    'Convert color names to RGBA codes for pg'
    opts.colorwave = convertToRGBA(pppara.colorwave, alpha=pppara.alphawave*100)
    opts.colorwavedel = convertToRGBA(pppara.colorwavedel, alpha=pppara.alphawave*100)
    opts.colortwfill = convertToRGBA(pppara.colortwfill, alpha=pppara.alphatwfill*100)
    opts.colortwsele = convertToRGBA(pppara.colortwsele, alpha=pppara.alphatwsele*100)
    opts.pickcolors = [ convertToRGB(c) for c in pppara.pickcolors ]
    return




#------------------------------------------------
# Modified from Arnav Sankaran's utils.py in 2016
#    Email: arnavsankaran@gmail.com
# Copyright (c) 2016 Arnav Sankaran
#------------------------------------------------
def convertToRGBA(color, alpha):
    colors = {
        'b': (0, 0, 255, alpha),
        'g': (0, 255, 0, alpha),
        'r': (255, 0, 0, alpha),
        'c': (0, 255, 255, alpha),
        'm': (255, 0, 255, alpha),
        'y': (255, 255, 0, alpha),
        'k': (0, 0, 0, alpha),
        'w': (255, 255, 255, alpha),
        'd': (150, 150, 150, alpha),
        'l': (200, 200, 200, alpha),
        's': (100, 100, 150, alpha),
    }
    colors = colorAlias(colors)
    colors['gray'] = (128, 128, 128, alpha)
    return colors[color]

def convertToRGB(color):
    colors = {
        'b': (0, 0, 255),
        'g': (0, 255, 0),
        'r': (255, 0, 0),
        'c': (0, 255, 255),
        'm': (255, 0, 255),
        'y': (255, 255, 0),
        'k': (0, 0, 0),
        'w': (255, 255, 255),
        'd': (150, 150, 150),
        'l': (200, 200, 200),
        's': (100, 100, 150),
    }
    colors = colorAlias(colors)
    colors['gray'] = (128, 128, 128)
    return colors[color]

def colorAlias(colors):
    alias = {
            'b': 'blue',
            'g': 'green',
            'r': 'red',
            'c': 'cyan',
            'm': 'mangeta',
            'y': 'yellow',
            'k': 'black',
            'w': 'white',
            'd': 'darkgray',
            'l': 'lightgray',
            's': 'slate',
            }
    for key, val in alias.items():
        colors[val] = colors[key]
    return colors
