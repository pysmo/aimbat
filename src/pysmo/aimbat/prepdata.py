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
from scipy import signal

def filtData(gsac, opts, pppara):
    """
    Create time and data (original and filtered in memory) arrays for plotting.
    """
    
    # set default filter parameters
    filterParameters = {}
    filterParameters['apply'] = True
    filterParameters['advance'] = False
    filterParameters['band'] = 'bandpass'
    filterParameters['lowFreq'] = 0.05
    filterParameters['highFreq'] = 0.3
    filterParameters['order'] = 2
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
        
    # Use linspace instead of arange to keep len(time) == npts.
    # Arange give an extra point for large window.
    #self.time = arange(b, b+npts*delta, delta)
    
    for sacdh in gsac.saclist:
        b, npts, delta = sacdh.b, sacdh.npts, sacdh.delta
        sacdh.time = np.linspace(b, b+(npts-1)*delta, npts)
        d = sacdh.data.copy()
        # filter time signal d:
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




