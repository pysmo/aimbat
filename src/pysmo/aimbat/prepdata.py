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

def prepData(gsac, opts, pppara):
    """
    Create time and data (original and filtered in memory) arrays for plotting.
    """
    # get default filter parameters
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
    opts.filterParameters = filterParameters
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
    # create time array and filtered data in memory
    for sacdh in gsac.saclist:
        b, npts, delta = sacdh.b, sacdh.npts, sacdh.delta
        sacdh.time = np.linspace(b, b+(npts-1)*delta, npts)
        d = sacdh.data.copy()
        # filter time signal d
        if hasattr(opts, 'filterParameters') and opts.filterParameters['apply']:
            NYQ = 1.0/(2*opts.delta)
            # make filter, default is bandpass
            Wn = [opts.filterParameters['lowFreq']/NYQ, opts.filterParameters['highFreq']/NYQ]
            B, A = signal.butter(opts.filterParameters['order'], Wn, analog=False, btype='bandpass')
            if opts.filterParameters['band']=='lowpass':
                Wn = opts.filterParameters['lowFreq']/NYQ
                B, A = signal.butter(opts.filterParameters['order'], Wn, analog=False, btype='lowpass')
            elif opts.filterParameters['band']=='highpass':
                Wn = opts.filterParameters['highFreq']/NYQ
                B, A = signal.butter(opts.filterParameters['order'], Wn, analog=False, btype='highpass')
            sacdh.datamem = signal.lfilter(B, A, d)
        else:
            sacdh.datamem = d
        # get reference time 
        reltime = opts.reltime
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
        # get time window
        sacdh.twhdrs = pppara.twhdrs
        tw0 = sacdh.gethdr(pppara.twhdrs[0])
        tw1 = sacdh.gethdr(pppara.twhdrs[1])    
        if tw0 == -12345.0:
            tw0 = sacdh.time[0]
        if tw1 == -12345.0:
            tw1 = sacdh.time[-1]
        sacdh.twindow = [tw0, tw1]
        # get data normalization
        if hasattr(sacdh, 'twindow') and opts.ynormtwin_on:
            dnorm = dataNormWindow(sacdh.data, sacdh.time, sacdh.twindow)
        else:
            dnorm = dataNorm(sacdh.data)
        sacdh.dscalor = 1/dnorm * opts.ynorm/2 
    return gsac

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
    qualsort.initQual(gsac.saclist, opts.hdrsel, opts.qheaders)
    return gsac, opts


