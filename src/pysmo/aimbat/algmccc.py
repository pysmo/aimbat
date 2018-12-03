#!/usr/bin/env python
#------------------------------------------------
# Filename: algmccc.py
#   Author: Xiaoting Lou, John VanDecar
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009 Xiaoting Lou, John VanDecar
#------------------------------------------------
"""
Python module for the MCCC (Multi-Channel Cross-Correlation) algorithm (VanDecar and Cross, 1990).
Code transcribed from the original MCCC 3.0 fortran version using the same function names:
    corread, corrmax, corrcff, correrr, corrmat, corrnow, corrwgt, corrite


:copyright:
    Xiaoting Lou, John VanDecar

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""


from numpy import array, mean, dot, zeros, log, transpose, concatenate, exp, sum, std, shape, sqrt, argsort, identity 
import os, sys
from time import strftime, tzname
from optparse import OptionParser
from pysmo.aimbat import ttconfig
from pysmo.aimbat import qualsort
from pysmo.aimbat import sacpickle as sacpkl
from pysmo.aimbat.prepdata import findPhase


def getOptions():
    """ 
    Parse arguments and options from command line. 
    No default value is given here because it will override values from configuration file.
    """
    usage = "Usage: %prog [options] <sacfile(s) or a picklefile>"
    parser = OptionParser(usage=usage)
    parser.add_option('-S', '--srate',  dest='srate', type='float',
        help='Sampling rate to load SAC data. Default is None, use the original rate of first file.')
    parser.add_option('-W', '--window',  dest='window', type='float',
        help='Use a correlation window length in seconds.')
    parser.add_option('-I', '--inset',  dest='inset', type='float',
        help='Use a time length of inset seconds from initial pick time to start of correlation window.')
    parser.add_option('-T', '--taper',  dest='taper', type='float',
        help='Apply a Hanning taper with width of taper seconds. Half of taper extends beyond both sides of window.')
    parser.add_option('-s', '--shift',  dest='shift', type='int',
        help='Shift in number of samples in cross-correlation.')
    parser.add_option('-i', '--ipick',  dest='ipick', type='str',
        help='SAC header variable to read initial time pick.')
    parser.add_option('-w', '--wpick',  dest='wpick', type='str',
        help='SAC header variable to write MCCC time pick.')
    parser.add_option('-p', '--phase',  dest='phase', type='str',
        help='Seismic phase name: P/S .')
    parser.add_option('-l', '--lsqr',  dest='lsqr', type='str',
        help='LSQR method to solve eqs: nowe, lnco, lnre.')
    parser.add_option('-o', '--ofilename',  dest='ofilename', type='str',
        help='Output file name. Default is $evdate.mc$phase')
    parser.add_option('-a', '--allseis', action="store_true", dest='allseis_on',
        help='Use all seismograms. Default to use selected ones.')
    opts, files = parser.parse_args(sys.argv[1:])
    if len(files) == 0:
        print(parser.usage)
        sys.exit()
    return opts, files

def rcdef():
    """ Default values for the inherited .mcccrc file of MCCC 3.0 """
    ls = os.linesep
    lines = []
    lines.append('% .mcccrc : optional file to set MCCC default parameters' + ls)
    lines.append('% MCCC first looks for this in the local and then home directory' + ls)
    lines.append('% if not found in either, the variables default to values shown in ( ).' + ls)
    lines.append('t2        % sac variable from which to read initial picks (t0)' + ls)
    lines.append('3.0       % window length in seconds (3.0)' + ls)
    lines.append('1.0       % inset length in seconds (1.0)' + ls)
    lines.append('1.0       % taper length in seconds (1.0)' + ls)
    lines.append('1.0       % 1st level shift length in seconds (1.0)' + ls)
    lines.append('0.1       % 2nd level shift length in seconds (0.1)' + ls)
    lines.append('0.05      % 3rd level shift length in seconds (0.05)' + ls)
    lines.append('100.0     % sample rate for interpolation (100.0)' + ls)
    lines.append('BU        % filter design type (BU)               * used ONLY with -f option' + ls)
    lines.append('0.3       % transition bandwidth in seconds (0.3) * used ONLY with -f option' + ls)
    lines.append('30.0      % attenuation factor in decibles (30.0) * used ONLY with -f option' + ls)
    lines.append('2         % number of poles for filter use (2)    * used ONLY with -f option' + ls)
    return lines

def rcread(rcfile='.mcccrc'):
    """ Read .mcccrc file and return ipick, time window and taper window.
    """
    lines = open(rcfile).readlines()
    ipick = lines[3][:2]
    win = float(lines[4].split()[0])
    ins = float(lines[5].split()[0])
    tap = float(lines[6].split()[0])
    sh0 = float(lines[7].split()[0])
    sh1 = float(lines[8].split()[0])
    sh2 = float(lines[9].split()[0])
    #sh = sh0+sh1+sh2
    #tw0 = -(ins + tap/2)
    #tw1 = win - ins + tap/2
    return ipick, [-ins, win-ins], tap

def rcwrite(ipick, timewindow, taperwindow, rcfile='.mcccrc'):
    """ Write to .mcccrc file. Convert timewindow --> window, inset, taper.
    """
    tw0, tw1 = timewindow
    tap = taperwindow
    win = tw1 - tw0
    ins = -tw0
    out = 'Write to {:s}: ipick={:s}, timewindow={:.2f} s , taperwindow={:.2f} s'
    print(out.format(rcfile, ipick, win, tap))
    #ls = os.linesep
    if os.path.isfile(rcfile):
        lines = open(rcfile).readlines()
    else:
        lines = rcdef()
    lines[3] = ipick + lines[3][2:]
    lines[4] = '{:*.3f}'.format(win) + lines[4][8:]
    lines[5] = '{:*.3f}'.format(ins) + lines[5][8:]
    lines[6] = '{:*.3f}'.format(tap) + lines[6][8:]
    oo = open(rcfile, 'w')
    oo.writelines(lines)
    oo.close()


def corread(saclist, ipick, timewindow, taperwindow, tapertype):
    """ Read data within timewindow+taperwindow (same length for each trace) for cross-correlation.
    """
    tw = timewindow[1] - timewindow[0]
    taperwidth = taperwindow/(taperwindow+tw)
    reftimes = array([ sacdh.gethdr(ipick) for sacdh in saclist])
    if -12345.0 in reftimes:
        print ('Not all seismograms has ipick={:s} set. Exit.'.format(ipick))
        sys.exit()
        #return
    nstart, ntotal = sacpkl.windowIndex(saclist, reftimes, timewindow, taperwindow)
    windata = sacpkl.windowData(saclist, nstart, ntotal, taperwidth, tapertype)
    return windata, reftimes

def corrmax(datai, timei, dataj, timej, mcpara):
    """ 
    Calculate cross-correlation derived relative delay times by calling one of the xcorr functions.
            dt_ij = t_i - t_j - tau_max
    where t_i and t_j are initial time picks for the i-th and j-th traces,
    and tau_max is the time lag at maximum correlation
    """
    shift = mcpara.shift
    delta = mcpara.delta
    xcorr = mcpara.xcorr
    delay, ccmax, ccpol = xcorr(datai, dataj, shift)
    return timei - timej - delay*delta, ccmax

def corrcff_fish(ccmatrix):
    """ 
    Calculate mean and standard deviation of correlation coefficients
    using Fisher's transform:
            z = 0.5 * ln((1+r)/(1-r))
    Input: ccmatrix is the matrix of correlation coefficients.
    Output: ccmean is transformed back but not ccstd.

    Problem: zero division if correlation coefficient is 1.
    """
    fish = 0.5*log((1+ccmatrix)/(1-ccmatrix))
    fish += transpose(fish)
    nsta = len(ccmatrix)
    ccmean, ccstd = zeros(nsta), zeros(nsta)
    for i in range(nsta):
        z = concatenate((fish[i,0:i], fish[i,i+1:nsta]))
        mz = mean(z)
        ccmean[i] = (exp(2*mz)-1)/(exp(2*mz)+1)
        ccstd[i] = std(z, ddof=1)
    return ccmean, ccstd

def corrcff(ccmatrix):
    """ Calculate mean and standard deviation of correlation coefficients.
    """
    fish = ccmatrix + transpose(ccmatrix)
    nsta = len(ccmatrix)
    ccmean, ccstd = zeros(nsta), zeros(nsta)
    for i in range(nsta):
        z = concatenate((fish[i,0:i], fish[i,i+1:nsta]))
        ccmean[i] = mean(z)
        ccstd[i]  = std(z, ddof=1)
    return ccmean, ccstd

def correrr(dtmatrix, invmodel):
    """ 
    Calculate the rms misfit between cross correlated derived relative delay times
    and least-squares solution:
        res_ij = dt_ij - (t_i - t_j)
    """
    nsta = len(dtmatrix)
    resmatrix = zeros((nsta,nsta))
    for i in range(nsta):
        for j in range(i+1,nsta):
            resmatrix[i, j] = dtmatrix[i,j] - (invmodel[i] - invmodel[j])
    resmatrix -= transpose(resmatrix)
    rms = sqrt(sum(resmatrix**2,0)/(nsta-2))
    return rms, resmatrix

def corrmat(windata, reftimes, mcpara):
    """ 
    Build matrices of cross-correlation derived relative delay times for least-squares solution.
            A * t = dt
    invmatrix A: sparse n*(n-1)/2+1 by n coefficient matrix including zero mean constraint
    invdata  dt: cross-correlation derived relative delay times between every pair of stations
    invmodel  t: optimized relative delay times for each station
    """
    nsta = len(windata)
    nrow = nsta*(nsta-1)//2 + 1
    invdata = zeros(nrow)
    invmatrix = zeros((nrow,nsta))
    ccmatrix = zeros((nsta,nsta))
    dtmatrix = zeros((nsta,nsta))
    k = 0
    for i in range(nsta):
        datai, timei = windata[i], reftimes[i]
        for j in range(i+1,nsta):
            dataj, timej = windata[j], reftimes[j]
            delay, ccmax = corrmax(datai, timei, dataj, timej, mcpara)
            invdata[k] = delay
            invmatrix[k][i] = 1
            invmatrix[k][j] = -1
            k += 1
            ccmatrix[i][j] = ccmax
            dtmatrix[i][j] = delay
    invmatrix[k][:] = 1
    invdata[k] = 0
    return invmatrix, invdata, ccmatrix, dtmatrix

def corrnow(invmatrix, invdata):
    """ 
    Solve A * t = dt by lease-squares without weighting:
            t = inv(A'A) * A' * dt = 1/n * A' * dt, where A'A = nI
    """
    nsta = shape(invmatrix)[1]
    invmodel = dot(transpose(invmatrix), invdata)
    invmodel /= nsta
    return invmodel

def corrwgt(invmatrix, invdata, ccmatrix, resmatrix, wgtscheme='correlation', exwt=1000.0):
    """ 
    Solve A * t = dt by weighted least-squares:
            t = inv(A'WA) * A' * W * dt
    W: n*(n-1)/2+1 by n*(n-1)/2+1 diagonal weighting matrix
    exwt: weight for the extra equation of zero-meaning constraint
    """
    from scipy.lib.lapack.flapack import dposv
    nrow, nsta = shape(invmatrix)
    if wgtscheme == 'correlation':
        w = ccmatrix
    elif wgtscheme == 'residual':
        w = resmatrix
    wgt = [abs(w[i,j]) for i in range(nsta) for j in range(i+1,nsta)]
    wgt.append(exwt)
    wgt = identity(nrow)*array(wgt)
    atw = dot(transpose(invmatrix), wgt)
    atwa = dot(atw, invmatrix)
    atwt = dot(atw, invdata)
    c, x, info = dposv(atwa, atwt)
    return x

def WriteFileWithDelay(mcpara, solist, solution, outvar, outcc, t0_times, delay_times, itmean):
    ofilename = mcpara.mcname
    kevnm = mcpara.kevnm
    delta = mcpara.delta
    lsqr = mcpara.lsqr
    nsta = len(solist)
    stalist = [ sacdh.netsta for sacdh in solist ]
    filelist = [ sacdh.filename.split('/')[-1] for sacdh in solist ]
    shift, tw, tap = mcpara.shift, mcpara.timewindow, mcpara.taperwindow

    # write mc file (with delay times)
    ofile = open(ofilename, 'w')
    tzone = tzname[0]
    tdate = strftime("%a, %d %b %Y %H:%M:%S") 
    line0 = 'MCCC processed: %s at: %s %s \n' % (kevnm, tdate, tzone)
    line1 = 'station, mccc delay,    std,    cc coeff,  cc std,   pol   , t0_times  , delay_times\n'
    ofile.write( line0 )
    ofile.write( line1 )
    fmt = ' {0:<9s} {1:9.4f} {2:9.4f} {3:>9.4f} {4:>9.4f} {5:4d}  {6:<s}  {7:9.4f}  {8:9.4f}\n'

    selist_LonLat = zeros(shape=(len(solist),2))
    nsta = len(solist)
    for i in range(nsta):
        dt, err, cc, ccstd = solution[i]
        selist_LonLat[i] = [solist[i].stlo,solist[i].stla]
        ofile.write( fmt.format(stalist[i], dt, err, cc, ccstd, 0, filelist[i], t0_times[i], delay_times[i]) )

    ofile.write( 'Mean_arrival_time:  {0:9.4f} \n'.format(itmean) )
    if lsqr == 'nowe':
        ofile.write('No weighting of equations. \n')
    elif lsqr == 'lnco':
        ofile.write('LAPACK solution with weighting by corr. coef. \n')
    elif lsqr == 'lnre':
        ofile.write('LAPACK solution with weighting by residuals. \n')
    fmt = 'Window: %6.2f   Inset: %6.2f  Shift: %6.2f \n' 
    ofile.write(fmt % (tw[1]-tw[0]-tap, -tw[0]-tap/2., shift*delta))
    fmt = 'Variance: %7.5f   Coefficient: %7.5f  Sample rate: %8.3f \n'
    ofile.write(fmt % (outvar, outcc, 1./delta))
    ofile.write('Taper: %6.2f \n' % tap)

    # write phase and event
    ofile.write( 'Phase: {0:8s} \n'.format(mcpara.phase) )
    ofile.write( mcpara.evline + '\n' )
    ofile.close()    

    return selist_LonLat, delay_times

def WriteFileOriginal(mcpara, solist, solution, outvar, outcc, itmean):
    ofilename = "original"+mcpara.mcname
    kevnm = mcpara.kevnm
    delta = mcpara.delta
    lsqr = mcpara.lsqr
    nsta = len(solist)
    stalist = [ sacdh.netsta for sacdh in solist ]
    filelist = [ sacdh.filename.split('/')[-1] for sacdh in solist ]
    shift, tw, tap = mcpara.shift, mcpara.timewindow, mcpara.taperwindow

    # write mc file (with delay times)
    ofile = open(ofilename, 'w')
    tzone = tzname[0]
    tdate = strftime("%a, %d %b %Y %H:%M:%S") 
    line0 = 'MCCC processed: %s at: %s %s \n' % (kevnm, tdate, tzone)
    line1 = 'station, mccc delay,    std,    cc coeff,  cc std,   pol\n'
    ofile.write( line0 )
    ofile.write( line1 )
    fmt = ' {0:<9s} {1:9.4f} {2:9.4f} {3:>9.4f} {4:>9.4f} {5:4d}  {6:<s}\n'

    selist_LonLat = zeros(shape=(len(solist),2))
    nsta = len(solist)
    for i in range(nsta):
        dt, err, cc, ccstd = solution[i]
        selist_LonLat[i] = [solist[i].stlo,solist[i].stla]
        ofile.write( fmt.format(stalist[i], dt, err, cc, ccstd, 0, filelist[i]))

    ofile.write( 'Mean_arrival_time:  {0:9.4f} \n'.format(itmean) )
    if lsqr == 'nowe':
        ofile.write('No weighting of equations. \n')
    elif lsqr == 'lnco':
        ofile.write('LAPACK solution with weighting by corr. coef. \n')
    elif lsqr == 'lnre':
        ofile.write('LAPACK solution with weighting by residuals. \n')
    fmt = 'Window: %6.2f   Inset: %6.2f  Shift: %6.2f \n' 
    ofile.write(fmt % (tw[1]-tw[0]-tap, -tw[0]-tap/2., shift*delta))
    fmt = 'Variance: %7.5f   Coefficient: %7.5f  Sample rate: %8.3f \n'
    ofile.write(fmt % (outvar, outcc, 1./delta))
    ofile.write('Taper: %6.2f \n' % tap)

    # write phase and event
    ofile.write( 'Phase: {0:8s} \n'.format(mcpara.phase) )
    ofile.write( mcpara.evline + '\n' )
    ofile.close()    

def corrite(solist, mcpara, reftimes, solution, outvar, outcc):
    """ Write output file, set output time picks.
    """
    nsta = len(solist)
    # set wpick    
    wpick = mcpara.wpick
    itmean = mean(reftimes)
    for i in range(nsta):
        wt = itmean + solution[i,0]
        solist[i].sethdr(wpick, wt)
    t0_times = [sacdh.gethdr('t0') for sacdh in solist]
    delay_times = [(solution[i,0]-(t0_times[i]-itmean)) for i in range(nsta)]

    selist_LonLat, delay_times = WriteFileWithDelay(mcpara, solist, solution, outvar, outcc, t0_times, delay_times, itmean)
    WriteFileOriginal(mcpara, solist, solution, outvar, outcc, itmean)
    return selist_LonLat, delay_times

def mccc(gsac, mcpara):
    """ Run MCCC. 
    """
    selist = gsac.selist
    delist = gsac.delist
    # sort sacdh list by net.sta
    stalist = [ sacdh.netsta for sacdh in selist ]
    stainds = argsort(stalist)
    solist = [ selist[i] for i in stainds ]
    nsta = len(solist)
    ipick = mcpara.ipick
    wpick = mcpara.wpick
    timewindow = mcpara.timewindow
    taperwindow = mcpara.taperwindow
    tapertype = mcpara.tapertype
    out = 'Run MCCC: ipick={0:s} wpick={1:s} timewindow=[{2:.3f}, {3:.3f}] taperwindow={4:.3f} s '
    print(out.format(ipick, wpick, timewindow[0], timewindow[1], taperwindow))
    out = 'Cross-correlation module.function: {:s}.{:s} with a shift of {:d} samples.'
    print(out.format(mcpara.xcorr_modu, mcpara.xcorr_func, mcpara.shift))
    print('Input: {0:d} traces. Output file: {1:s} '.format(nsta, mcpara.mcname))
    # read data
    windata, reftimes = corread(solist, ipick, timewindow, taperwindow, tapertype)
    invmatrix, invdata, ccmatrix, dtmatrix = corrmat(windata, reftimes, mcpara)
    ccmean, ccstd = corrcff(ccmatrix)
    lsqr = mcpara.lsqr
    exwt = mcpara.exwt
    # solve by no weight
    invmodel = corrnow(invmatrix, invdata)
    rms, resmatrix = correrr(dtmatrix, invmodel)
    if lsqr == 'lnco':
        wgtscheme = 'correlation'
        invmodel = corrwgt(invmatrix, invdata, ccmatrix, resmatrix, wgtscheme, exwt)
        print('--> LSQR: LAPACK, weighted by correlation')
    elif lsqr == 'lnre':
        wgtscheme = 'residual'
        invmodel = corrwgt(invmatrix, invdata, ccmatrix, resmatrix, wgtscheme, exwt)
        print('--> LSQR: LAPACK, weighted by residual')
    elif lsqr == 'nowe':
        print('--> LSQR: no weighting')
    solution = transpose(array((invmodel, rms, ccmean, ccstd)))
    outvar = sqrt(sum(resmatrix**2)/2/(nsta*(nsta-1)/2))
    outcc = mean(ccmean)

    selist_LonLat, delay_times = corrite(solist, mcpara, reftimes, solution, outvar, outcc)

    # set wpick as ipick for deleted ones and array stack
    for sacdh in delist:
        sacdh.sethdr(wpick, sacdh.gethdr(ipick))
    stkdh = gsac.stkdh
    stkdh.sethdr(wpick, stkdh.gethdr(ipick))

    return solution, selist_LonLat, delay_times


def eventListName(evlist='event.list', phase='S', isol='PDE'):
    """ 
    Read evlist (either event.list file or gsac.event list) for hypocenter and origin time.
    Create output filename.
    """
    eventfmt  = '{0:<6s} {1:4d} {2:2d} {3:2d} {4:2d} {5:2d} {6:5.2f} '
    eventfmt += '{7:9.3f} {8:9.3f} {9:6.1f} {10:4.1f} {11:4.1f} '
    fnamefmt  = '{0!s:0>4}{1!s:0>2}{2!s:0>2}.{3!s:0>2}{4!s:0>2}{5!s:0>4}.mc{6:s}'
    if type(evlist) == type(''):
        evhypo = open(evlist).readline().split()
        elat, elon, dum, edep = [ float(v) for v in evhypo[:4] ]
        sec, mb, mw = [ float(v) for v in evhypo[8:11] ]
        iyr, jday, ihr, imin = [ int(v) for v in evhypo[4:8] ]
        imon, iday = [ int(v) for v in evhypo[13:15] ]
    else:
        iyr, imon, iday, ihr, imin, sec, elat, elon, edep, mw = evlist
        mb = 0
    isec = int(round(sec*100))
    evline = eventfmt.format(isol, iyr, imon, iday, ihr, imin, sec, elat, elon, edep, mb, mw)
    mcname = fnamefmt.format(iyr, imon, iday, ihr, imin, isec, phase.lower() )
    return evline, mcname

def getWindow(stkdh, ipick, twhdrs, taperwidth=0.1):
    """ Get timewindow and taperwindow from gsac.stkdh """    
    tw0, tw1 = twhdrs
    t0 = stkdh.gethdr(ipick)
    th0 = stkdh.gethdr(tw0) - t0
    th1 = stkdh.gethdr(tw1) - t0
    timewindow = [th0, th1]
    taperwindow = sacpkl.taperWindow(timewindow, taperwidth)
    return timewindow, taperwindow

def getParams(gsac, mcpara, opts=None):
    """ Get parameters for running MCCC.
        Hierarchy: default config < gsac < .mcccrc < command line options
    """
    nsta = len(gsac.saclist)
    if nsta < 5:
        print ('\n Less than five stations - stop')
        sys.exit()    
    # get window from gsac.stkdh
    if 'stkdh' in gsac.__dict__:
        timewindow, taperwindow = getWindow(gsac.stkdh, mcpara.ipick, mcpara.twhdrs, mcpara.taperwidth)
        mcpara.timewindow = timewindow
        mcpara.taperwindow = taperwindow

    # use options saved in gsac
    gdict = gsac.__dict__
    odict = opts.__dict__
    mdict = mcpara.__dict__
    for key in ['phase', 'ipick', 'wpick', 'timewindow', 'taperwindow', 'taperwidth']:
        if key in gdict:
            mdict[key] = gdict[key]
    # read rcfile (.mcccrc) if there is any
    rcfile = mcpara.rcfile
    if os.path.isfile(rcfile):
        ipick, timewindow, taperwindow = rcread(rcfile)
        wpick = ipick[0] + str(int(ipick[1])+1)
        mcpara.ipick = ipick
        mcpara.wpick = wpick
        mcpara.timewindow = timewindow
        mcpara.taperwindow = taperwindow
        tw = timewindow[1] - timewindow[0]
        mcpara.taperwidth = taperwindow/(tw+taperwindow)
    # command line options override config and rc file
    if opts is not None:
        for key in list(odict.keys()):
            if odict[key] is not None:
                mdict[key] = odict[key]
    # check if params are complete
    if 'phase' not in mdict:
        print ('\n No phase name given - stop')
        sys.exit()
    if 'timewindow' not in mdict:
        if 'window' in mdict and 'inset' in mdict:
            win, ins = mdict['window'], mdict['inset']
            mcpara.timewindow = [-ins, win-ins]
            if 'taper' in mdict:
                mcpara.taperwindow = mdict['taper']
            else:
                mcpara.taperwindow = sacpkl.taperWindow(mcpara.timewindow, mcpara.taperwidth)
        else:
            print ('No window and inset length give - stop')
            sys.exit()
    # get event info from either event.list or gsac
    if not os.path.isfile(mcpara.evlist):
        mcpara.evlist = gsac.event
    evline, mcname = eventListName(mcpara.evlist, mcpara.phase)
    mcpara.evline = evline
    mcpara.mcname = mcname
    mcpara.kevnm = gsac.kevnm
    if mcpara.ofilename != 'mc':
        mcpara.mcname = mcpara.ofilename
    gsac.mcname = mcpara.mcname
    
def main():
    opts, ifiles = getOptions()
    mcpara = ttconfig.MCConfig()
    gsac = sacpkl.loadData(ifiles, opts, mcpara)

    if opts.phase is None:
        phase = findPhase(ifiles[0])
        print ('Found phase to be: ' + phase + '\n')
        mcpara.phase = phase

    opts.fstack = mcpara.fstack
    if opts.filemode == 'sac' and os.path.isfile(opts.fstack):
        print ('Read array stack file: ' + opts.fstack )
        gsac.stkdh = sacpkl.SacDataHdrs(opts.fstack, opts.delta)

    getParams(gsac, mcpara, opts)
    if opts.allseis_on:
        solution = mccc(gsac, mcpara)
        gsac.selist, gsac.delist = gsac.saclist, []
    else:
        qualsort.initQual(gsac.saclist, mcpara.hdrsel, [])
        gsac.selist, gsac.delist = qualsort.seleSeis(gsac.saclist)
        solution = mccc(gsac, mcpara)
    sacpkl.saveData(gsac, opts)



if __name__ == '__main__':
    main()

