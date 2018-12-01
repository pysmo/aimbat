#!/usr/bin/env python
#------------------------------------------------
# Filename: algiccs.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009 Xiaoting Lou
#------------------------------------------------
"""
Python module for the ICCS (iterative cross-correlation and stack) algorithm.

:copyright:
    Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""

from numpy import array, ones, zeros, sqrt, dot, corrcoef, mean, transpose, linspace
from numpy import linalg as LA
import os, sys, copy
from optparse import OptionParser
from pysmo.aimbat import ttconfig
from pysmo.aimbat import qualsort
from pysmo.aimbat import sacpickle as sacpkl


def getOptions():
    """ Parse arguments and options. """
    usage = "Usage: %prog [options] <sacfile(s) or a picklefile>"
    parser = OptionParser(usage=usage)
    twcorr = -15, 15
    ipick = 't0'
    wpick = 't1'
    minccc = 0.5
    minsnr = 0.5
    mincoh = 0.0
    minqual = minccc, minsnr, mincoh    
    minnsel = 5
    parser.set_defaults(twcorr=twcorr)
    parser.set_defaults(ipick=ipick)
    parser.set_defaults(wpick=wpick)
    parser.set_defaults(minqual=minqual)
    parser.set_defaults(minnsel=minnsel)
    parser.add_option('-S', '--srate',  dest='srate', type='float',
        help='Sampling rate to load SAC data. Default is None, use the original rate of first files.')
    parser.add_option('-i', '--ipick',  dest='ipick', type='str',
        help='SAC header variable to read input time pick.')
    parser.add_option('-w', '--wpick',  dest='wpick', type='str',
        help='SAC header variable to write output time pick.')
    parser.add_option('-t', '--twcorr', dest='twcorr', type='float', nargs=2,
        help='Time window for cross-correlation. Default is [{:.1f}, {:.1f}] s.'.format(twcorr[0],twcorr[1]))
    parser.add_option('-f', '--fstack',  dest='fstack', type='str',
        help='SAC file name to save final array stack.')
    parser.add_option('-p', '--plotiter', action="store_true", dest='plotiter',
        help='Plot array stack of each iteration.')
    parser.add_option('-a', '--auto_on', action="store_true", dest='auto_on',
        help='Run ICCS and select/delete seismograms automatically.')
    parser.add_option('-A', '--auto_on_all', action="store_true", dest='auto_on_all',
        help='Run ICCS with -a option but initially use all seismograms.')
    parser.add_option('-q', '--minqual',  dest='minqual', type='float', nargs=3,
        help='Minimum quality factor (ccc,snr,coh) for auto selection. Defaults are {:.2f} {:.2f} {:.2f}.'.format(minccc, minsnr, mincoh))
    parser.add_option('-n', '--minnsel',  dest='minnsel', type='int',
        help='Minimum number of selected seismograms for auto selection. Default is {:d}.'.format(minnsel))
    opts, files = parser.parse_args(sys.argv[1:])
    if len(files) == 0:
        print(parser.usage)
        sys.exit()
    return opts, files

def corrmax(datai, dataj, delta, xcorr, shift):
    """ Calculate time lag at maximum cross correlation between two time series.
    """
    delay, ccmax, ccpol = xcorr(datai, dataj, shift)
    return delay*delta, ccmax, ccpol

def meanStack(data, taperwidth, tapertype):
    """ Calculate array stack by averaging without weighting.
    """
    sdata = mean(data, 0)
    sdata = sacpkl.taper(sdata, taperwidth, tapertype)
    return sdata

def weightStack(data, wgts, taperwidth, tapertype):
    """ Calculate array stack by averaging with weighting.
    """
    sdata = mean(transpose(data) * wgts, 1)
    sdata = sacpkl.taper(sdata, taperwidth, tapertype)
    return sdata


def normWeightStack(data, wgts, taperwidth, tapertype):
    """ Calculate array stack by averaging with weighting and normalization.
    """
    mdata = [ d/max(d)  for d in data ]
    sdata = mean(transpose(mdata) * wgts, 1)
    sdata = sacpkl.taper(sdata, taperwidth, tapertype)
    return sdata

def ccWeightStack(saclist, opts):
    """ 
    Align seismograms by the iterative cross-correlation and stack algorithm.

    Parameters
    ----------
    opts.delta : sample time interval
    opts.ccpara : a class instance for ICCS parameters 
        * qqhdrs : SAC headers to save quality factors: ccc, snr, coh
        * maxiter :    maximum number of iteration
        * converg :    convergence critrion
        * cchdrs : inputand output picks of cross-correlation
        * twcorr : time window for cross-correlation
    """
    ccpara = opts.ccpara
    delta = opts.delta
    maxiter = ccpara.maxiter
    convtype = ccpara.convtype
    convepsi = ccpara.convepsi
    taperwidth = ccpara.taperwidth
    tapertype = ccpara.tapertype
    xcorr = ccpara.xcorr
    shift = ccpara.shift
    twhdrs = ccpara.twhdrs
    qqhdrs = ccpara.qheaders
    cchdrs = ccpara.cchdrs
    twcorr = ccpara.twcorr
    hdrccc, hdrsnr, hdrcoh, = qqhdrs[:3]
    cchdr0, cchdr1 = cchdrs
    if convtype == 'coef':
        convergence = coConverg
    elif convtype == 'resi':
        convergence = reConverg
    else:
        print('Unknown convergence criterion: {:s}. Exit.'.format(convtype))
        sys.exit()
    
    out = '\n--> Run ICCS at window [{0:5.1f}, {1:5.1f}] wrt {2:s}. Write to header: {3:s}'
    print(out.format(twcorr[0], twcorr[1], cchdr0, cchdr1))
    print('    Convergence criterion: {:s}'.format(convtype))
    if ccpara.stackwgt == 'coef':
        wgtcoef = True
    else:
        wgtcoef = False
    taperwindow = sacpkl.taperWindow(twcorr, taperwidth)
    # get initial time picks
    tinis = array([ sacdh.gethdr(cchdr0) for sacdh in saclist])
    tfins = tinis.copy()
    nseis = len(saclist)
    ccc = zeros(nseis)
    snr = zeros(nseis)
    coh = zeros(nseis)
    wgts = ones(nseis)
    stkdata = []
    datatype = 'datamem'
    for it in range(maxiter):
        # recut data and update array stack
        nstart, ntotal = sacpkl.windowIndex(saclist, tfins, twcorr, taperwindow)
        windata = sacpkl.windowData(saclist, nstart, ntotal, taperwidth, tapertype, datatype)
        sdata = normWeightStack(windata, wgts, taperwidth, tapertype)
        stkdata.append(sdata)
        if it == 0:
            print ('=== Iteration {0:d} : epsilon'.format(it))
        else:
            conv = convergence(stkdata[it], stkdata[it-1])
            print ('=== Iteration {0:d} : {1:8.6f}'.format(it, conv))
            if conv <= convepsi:
                print ('    Array stack converged... Done. Mean corrcoef={0:.3f}'.format(mean(ccc)))
                break
        # Find time lag at peak correlation between each trace and the array stack.
        # Calculate cross correlation coefficient, signal/noise ratio and temporal coherence
        sdatanorm = sdata/LA.norm(sdata)
        for i in range(nseis):
            datai = windata[i]
            delay, ccmax, ccpol = corrmax(sdata, datai, delta, xcorr, shift)
            tfins[i] += delay
            sacdh = saclist[i]
            sacdh.sethdr(cchdr1, tfins[i])
            if wgtcoef:    # update weight only when stackwgt == coef
                wgts[i] = ccpol * ccmax
            ccc[i] = ccmax
            sacdh.sethdr(hdrccc, ccc[i])
            snr[i] = snratio(datai, delta, twcorr)
            sacdh.sethdr(hdrsnr, snr[i])
            coh[i] = coherence(datai*ccpol, sdatanorm)
            sacdh.sethdr(hdrcoh, coh[i])
    # get maximum time window for plot (excluding taperwindow)
    bb, ee = [], []
    for i in range(nseis):
        sacdh = saclist[i]
        b = sacdh.b - tfins[i]
        e = b + (sacdh.npts-1)* delta
        bb.append(b+delta)
        ee.append(e-delta)
    b = max(bb)
    e = min(ee)
    d = (e-b)*taperwidth/2
    twplot = [b+d, e-d]
    # calculate final stack at twplot, save to a sacdh object: stkdh
    # set time picks of stkdh as mean of tinis and tfins
    taperwindow = sacpkl.taperWindow(twplot, taperwidth)
    nstart, ntotal = sacpkl.windowIndex(saclist, tfins, twplot, taperwindow)
    windata = sacpkl.windowData(saclist, nstart, ntotal, taperwidth, tapertype, datatype)
    sdatamem = normWeightStack(windata, wgts, taperwidth, tapertype)
    # also create stack from original data
    datatype = 'data'
    windata = sacpkl.windowData(saclist, nstart, ntotal, taperwidth, tapertype, datatype)
    sdata  = normWeightStack(windata, wgts, taperwidth, tapertype)
    tinimean = mean(tinis)
    tfinmean = mean(tfins)
    stkdh = copy.copy(saclist[0])
    stkdh.thdrs = [-12345.,] * 10
    stkdh.users = [-12345.,] * 10
    stkdh.kusers = ['-1234567',] * 3
    stkdh.b = twplot[0] - taperwindow*0.5 + tfinmean
    stkdh.npts = len(sdata)
    stkdh.data = sdata
    stkdh.sethdr(cchdr0, tinimean)
    stkdh.sethdr(cchdr1, tfinmean)
    stkdh.knetwk = 'Array'
    stkdh.kstnm = 'Stack'
    stkdh.netsta = 'Array.Stack'
    stkdh.gcarc = -1
    stkdh.dist = -1
    stkdh.baz = -1
    stkdh.az = -1
    stkdh.stla = 0
    stkdh.stlo = 0
    stkdh.stel = 0
    stkdh.delta = delta
    stkdh.e = stkdh.b + (stkdh.npts-1)*delta
    stkdh.time = linspace(stkdh.b, stkdh.b+(stkdh.npts-1)*stkdh.delta, stkdh.npts)
    stkdh.datamem = sdatamem
    # set time window
    stkdh.sethdr(twhdrs[0], twcorr[0]+tfinmean)
    stkdh.sethdr(twhdrs[1], twcorr[1]+tfinmean)
    stkdh.twindow = twcorr[0]+tfinmean, twcorr[1]+tfinmean
    if opts.fstack is None:
        stkdh.filename = ccpara.fstack
    else:
        stkdh.filename = opts.fstack
    for sacdh, tfin in zip(saclist, tfins):
        sacdh.sethdr(twhdrs[0], tfin+twcorr[0])
        sacdh.sethdr(twhdrs[1], tfin+twcorr[1])
        sacdh.twindow = tfin+twcorr[0], tfin+twcorr[1] 
    quas = array([ ccc, snr, coh ])
    return stkdh, stkdata, quas

def coConverg(stack0, stack1):
    """ 
    Calcuate criterion of convergence by correlation coefficient.
    stack0 and stack1 are current stack and stack from last iteration.
    """
    return 1 - corrcoef(stack0, stack1)[0][1]

def reConverg(stack0, stack1):
    """ 
    Calcuate criterion of convergence by change of stack.
    stack0 and stack1 are current stack and stack from last iteration.
    """
    return LA.norm(stack0-stack1,1)/LA.norm(stack0,2)/len(stack0)

def snratio(data, delta, timewindow):
    """ 
    Calculate signal/noise ratio within the given time window.
    Time window is relative, such as [-10, 20], to the onset of the arrival.
    """
    tw0, tw1 = timewindow
    nn = int(round(-tw0/delta))
    yn = data[:nn]
    ys = data[nn:]
    ns = len(ys)
    rr = LA.norm(ys)/LA.norm(yn)*sqrt(nn)/sqrt(ns)
    if LA.norm(yn) == 0:
        print ('snr', LA.norm(yn))
    ### the same as:
    #rr = sqrt(sum(square(ys))/sum(square(yn))*nn/ns)
    # shoud signal be the whole time seris?
    #yw = data[:]
    #nw = len(yw)
    #rw = sqrt(sum(square(yw))/sum(square(yn))*nn/nw)
    return rr

def coherence(datai, datas):
    """ 
    Calculate time domain coherence.
    Coherence is 1 - sin of the angle made by two vectors: di and ds.
    Di is data vector, and ds is the unit vector of array stack.
    res(di) = di - (di . ds) ds 
    coh(di) = 1 - res(di) / ||di||
    """
    return 1 - LA.norm(datai - dot(datai, datas)*datas)/LA.norm(datai)


def plotiter(stkdata):
    import matplotlib.pyplot as plt
    plt.figure()
    for i in range(len(stkdata)):
        plt.plot(stkdata[i], label='iter'+str(i))
    plt.legend()
    plt.show()

def autoiccs(gsac, opts):
    """ Run ICCS and delete low quality seismograms automatically.
    """
    saclist = gsac.saclist
    hdrsel = opts.ccpara.hdrsel
    minqual = opts.minqual
    minnsel = opts.minnsel
    minccc, minsnr, mincoh = minqual
    
    selist, delist = qualsort.seleSeis(saclist)
    print ('\n*** Run ICCS until all low quality seismograms removed: Min_ccc={0:.2f} Min_snr={1:.1f} Min_coh={2:.2f} *** '.format(minccc,minsnr,mincoh))
    rerun = True
    while rerun and len(selist) >= minnsel:
        stkdh, stkdata, quas = ccWeightStack(selist, opts)
        tquas = transpose(quas)
        indsel, inddel = [], []
        for i in range(len(selist)):
            sacdh = selist[i]
            ccc, snr, coh = tquas[i]
            if ccc < minccc or snr < minsnr or coh < mincoh:
                inddel.append(i)
                sacdh.sethdr(hdrsel, 'False')
                sacdh.selected = False
                print ('--> Seismogram: {0:s} quality factors {1:.2f} {2:.2f} {3:.2f} < min. Deleted. '.format(sacdh.filename, ccc, snr, coh))
            else:
                indsel.append(i)
        if len(inddel) > 0:
            selist = [ selist[i] for i in indsel ]
        else:
            rerun = False
            gsac.stkdh = stkdh
    gsac.selist = selist
    nsel = len(selist)
    print ('\nDone selecting seismograms: {0:d} out of {1:d} selected.'.format(nsel, len(saclist)))

    save = input('Save to file? [y/n] \n')
    if save[0].lower() == 'y':
        if opts.filemode == 'sac':
            for sacdh in saclist: sacdh.writeHdrs()
            gsac.stkdh.savesac()
        elif opts.filemode == 'pkl':
            print (' Saving gsac to pickle file...')
            sacpkl.writePickle(gsac, opts.pklfile, opts.zipmode)
            if opts.zipmode is not None:
                pklfile = opts.pklfile + '.' + opts.zipmode
            else:
                pklfile = opts.pklfile
            if nsel < minnsel: 
                os.rename(pklfile, 'deleted.'+pklfile)
                print ('  Less than {:d} seismograms selected. Remove pkl.'.format(minnsel))



def checkCoverage(gsac, opts, textra=0.0):
    """ Check if each seismogram has enough samples around the time window relative to ipick.
    """
    ipick = opts.ipick
    tw0, tw1 = opts.twcorr
    saclist = gsac.saclist
    nsac = len(saclist)
    indsel, inddel = [], []
    for i in range(nsac):
        sacdh = saclist[i]
        t0 = sacdh.gethdr(ipick)
        b = sacdh.b
        e = b + (sacdh.npts-1)*sacdh.delta
        if b-textra > t0+tw0 or e+textra < t0+tw1:
            inddel.append(i)
            print ('Seismogram {0:s} does not have enough sample. Deleted.'.format(sacdh.filename))
        elif LA.norm(sacdh.data) == 0.0:
            inddel.append(i)
            print ('Seismogram {0:s} has zero L2 norm. Deleted.'.format(sacdh.filename))
        else:
            indsel.append(i)
    if inddel != []:
        gsac.saclist = [ saclist[i] for i in indsel ]
        #print ('Updating gsac pickle file..')
        #writePickle(gsac, opts.pklfile, opts.zipmode)


def main():
    opts, ifiles = getOptions()
    ccpara = ttconfig.CCConfig()
    gsac = sacpkl.loadData(ifiles, opts, ccpara)
    opts.ccpara = ccpara
    ccpara.twcorr = opts.twcorr
    ccpara.cchdrs = [opts.ipick, opts.wpick]
    # check data coverage, initialize quality factors
    checkCoverage(gsac, opts) 
    qualsort.initQual(gsac.saclist, opts.ccpara.hdrsel, opts.ccpara.qheaders)

    if opts.auto_on:
        autoiccs(gsac, opts)
    elif opts.auto_on_all:
        print ('Selecting all seismograms..')
        hdrsel = opts.ccpara.hdrsel
        for sacdh in gsac.saclist:
            sacdh.selected = True
            sacdh.sethdr(hdrsel, 'True')
        autoiccs(gsac, opts)
    else:
        stkdh, stkdata, quas = ccWeightStack(gsac.saclist, opts)
        gsac.stkdh = stkdh
        sacpkl.saveData(gsac, opts)
    if opts.plotiter:
        plotiter(stkdata)

if __name__ == "__main__":
    main()
