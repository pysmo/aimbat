#!/usr/bin/env python
#------------------------------------------------
# Filename: xcorr.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009 Xiaoting Lou
#------------------------------------------------
"""
Python module to calculate cross-correlation function of two time series with the same length.
      c(k) = sum_i  x(i) * y(i+k)
           where k is the time shift of y relative to x.
Delay time, correlation coefficient, and polarity at maximum correlation are returned.

Added suport to correlation polarity to allow negative correlation maximum.
Output ccpol=1 if positive or ccpol=-1 if negative. xlou 03/2011


:copyright:
    Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""

from numpy import correlate, dot, argmax, argmin, sqrt

def _xcorr(x, y, cmode='full'):
    """ 
    Cross-correlation of two 1-D arrays using 'full' or 'same' mode.
        c[k] = sum_i x[i]*y[i+k]
    Full mode: indices of array c --> j=0:nx+ny-2 <-- k=ny-1:-nx+1:-1 (j=ny-1-k)
    Return time shift of y relative to x at maximum correlation and polarity.
    """
    cc = correlate(x, y, cmode)
    imax = argmax(cc)
    imin = argmin(cc)
    ccmax = cc[imax]
    ccmin = cc[imin]
    if ccmax >= -ccmin:
        ccpol = 1
        delay = len(y)-1-imax
        ccmax =  ccmax / sqrt(dot(x,x)*dot(y,y))
    else:
        ccpol = -1
        delay = len(y)-1-imin
        ccmax = -ccmin / sqrt(dot(x,x)*dot(y,y))
    if cmode == 'same':
        delay -= (len(y)-1)/2
    return delay, ccmax, ccpol

def _xcorr_polarity(x, y, cmode='full'):
    """ 
    Cross-correlation of two 1-D arrays using 'full' or 'same' mode.
        c[k] = sum_i x[i]*y[i+k]
    Full mode: indices of array c --> j=0:nx+ny-2 <-- k=ny-1:-nx+1:-1 (j=ny-1-k)
        It does not correct the polarity, meaning it does only calculate the maximum
        value of cross correlaton, not including minimum, which is different from
        _xcorr
    Return time shift of y relative to x at maximum correlation and polarity.
    """
    cc = correlate(x, y, cmode)
    imax = argmax(cc)
    ccmax = cc[imax]
    ccpol = 1
    delay = len(y)-1-imax
    ccmax =  ccmax / sqrt(dot(x,x)*dot(y,y))
    if cmode == 'same':
        delay -= (len(y)-1)/2
    return delay, ccmax, ccpol

def xcorr_full(x, y, shift=1):
    """ 
    Cross-correlation of two 1-D arrays using 'full' mode.
    Argument shift=1 is here only in order to make the same number of arguments for all xcorr functions.
    """
    return _xcorr(x, y, 'full')

def xcorr_full_polarity(x, y, shift=1):
    """ 
    Cross-correlation of two 1-D arrays using 'full' mode.
    Argument shift=1 is here only in order to make the same number of arguments for all xcorr functions.
    Not correct the polarity
    """
    return _xcorr_polarity(x, y, 'full')

def xcorr_same(x, y):
    """ 
    Cross-correlation of two 1-D arrays using 'same' mode.
    """
    return _xcorr(x, y, 'same')

def xcorr_select(x, y, lags):
    """ 
    Cross-correlation of two time series of the same length 
    for selected lag(shift) times
    """
    n = len(x)
    cc = []
    for k in lags:
        if k >= 0:
            cc.append(dot(x[0:n-k], y[k:n]))
        else:
            cc.append(dot(x[-k:n], y[0:n+k]))
    imax = argmax(cc)
    imin = argmin(cc)
    ccmax = cc[imax]
    ccmin = cc[imin]
    if ccmax >= -ccmin:
        ccpol = 1
        delay = lags[imax]
        ccmax =  ccmax / sqrt(dot(x,x)*dot(y,y))
    else:
        ccpol = -1
        delay = lags[imin]
        ccmax = -ccmin / sqrt(dot(x,x)*dot(y,y))
    return delay, ccmax, ccpol

def xcorr_fast(x, y, shift=10):
    """ 
    Fast cross-correlation of two time series of the same length.
    One level of coarse shift by downsampling the signal.
    """
    sx = x[::shift]
    sy = y[::shift]
    delay, ccmax, ccpol = _xcorr(sx, sy, 'same')
    lags = list(range(delay-shift, delay+shift+1, 1))
    delay, ccmax, ccpol = xcorr_select(x, y, lags)
    return delay, ccmax, ccpol

def xcorr_faster(x, y, shift=10):
    """ 
    Faster cross-correlation only for time lags around zero.
    """
    lags = list(range(-shift, shift+1, 1))
    delay, ccmax, ccpol = xcorr_select(x, y, lags)
    return delay, ccmax, ccpol

def xcorr_select_polarity(x, y, lags):
    """ 
    Cross-correlation of two time series of the same length 
    for selected lag(shift) times
    Do not correct polarity
    """
    n = len(x)
    cc = []
    for k in lags:
        if k >= 0:
            cc.append(dot(x[0:n-k], y[k:n]))
        else:
            cc.append(dot(x[-k:n], y[0:n+k]))
    imax = argmax(cc)
    ccmax = cc[imax]
    ccpol = 1
    delay = lags[imax]
    ccmax =  ccmax / sqrt(dot(x,x)*dot(y,y))
    return delay, ccmax, ccpol

def xcorr_fast_polarity(x, y, shift=10):
    """ 
    Fast cross-correlation of two time series of the same length.
    One level of coarse shift by downsampling the signal.
    Do not correct polarity
    """
    sx = x[::shift]
    sy = y[::shift]
    delay, ccmax, ccpol = _xcorr(sx, sy, 'same')
    lags = list(range(delay-shift, delay+shift+1, 1))
    delay, ccmax, ccpol = xcorr_select_polarity(x, y, lags)
    return delay, ccmax, ccpol

def xcorr_faster_polarity(x, y, shift=10):
    """ 
    Faster cross-correlation only for time lags around zero.
    Do not correct polarity
    """
    lags = list(range(-shift, shift+1, 1))
    delay, ccmax, ccpol = xcorr_select_polarity(x, y, lags)
    return delay, ccmax, ccpol