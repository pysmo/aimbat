#!/usr/bin/env python
#------------------------------------------------
# Filename: qualsort.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009 Xiaoting Lou
#------------------------------------------------
"""

Python module for selecting and sorting seismograms by quality factors and other header variables.
 
:copyright:
    Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""

from numpy import array, argsort, mean, sum
import sys

def initQual(saclist, hdrsel, qheaders):
    """ 
    Set initial values for selection status and quality factors.
    """
    for sacdh in saclist:
        sel = sacdh.gethdr(hdrsel)
        if sel == '-1234567':
            sacdh.sethdr(hdrsel, 'True')
            sacdh.selected = True
        elif sel[0] == 'T' or sel[0] == b'T':  # for bytes in py3
            sacdh.selected = True
        else:
            sacdh.selected = False
        for hdr in qheaders:
            if sacdh.gethdr(hdr) == -12345.0:
                sacdh.sethdr(hdr, 0.0) 
    return

def sortQual(saclist, qheaders, qweights, increase=True):
    """ 
    Sort quality factors by weighted averaging.
    Return sorted sacdh list and means of quality factors.
    """
    qvalues = []
    for i in range(len(saclist)):
        sacdh = saclist[i]
        qvalues.append([sacdh.gethdr(hdr) for hdr in qheaders])
    qvalues = array(qvalues)
    qweights = array(qweights)
    qsum = sum(qvalues*qweights, 1)
    indsort = argsort(qsum)
    qmeans = mean(qvalues, 0)
    if not increase:
        indsort = indsort[::-1]
        qmeans = qmeans[::-1]
    sortlist = [ saclist[i] for i in indsort ]
    return sortlist, qmeans

def seleSeis(saclist):
    """ 
    Select seismograms. 
    Return sacdh lists of selected and deleted seismograms.
    
    selelist: selected seismograms
    delelist: deleted seismograms, user doe snot want them
    """
    indsele = []
    inddele = []
    for i in range(len(saclist)):
        sacdh = saclist[i]
        if sacdh.selected:
            indsele.append(i)
        else:
            inddele.append(i)
    selelist = [ saclist[i] for i in indsele ]
    delelist = [ saclist[i] for i in inddele ]
    return selelist, delelist

def sortSeisQual(saclist, qheaders, qweights, qfactors, increase=True):
    """ 
    Select and sort seismograms by quality factors. 
    """
    selelist, delelist = seleSeis(saclist)
    if len(delelist) > 1:
        sordelist, qmeand = sortQual(delelist, qheaders, qweights, increase)
    else:
        sordelist = delelist
    if len(selelist) > 0:
        sorselist, qmeans = sortQual(selelist, qheaders, qweights, increase)
    else:
        print('Zero sacdh selected. Exit')
        sys.exit()
    out1 = '  Average '
    out2 = '  Weighted average quality: '
    for i in range(len(qweights)):
        qf = qfactors[i]
        #qw = qweights[i]
        qm = qmeans[i]
        out1 += '%s=%.2f, ' % (qf, qm)
        out2 += '%s*1/3+' % qf
    out1 = out1[:-2]
    out2 = out2[:-1] + ' = %.2f' % mean(qmeans)
    print(out1)
    print(out2)
    return sorselist, sordelist


def sortSeisHeaderDiff(saclist, hdr0, hdr1, increase=True):
    """ 
    Sort saclist by header value difference (hdr1-hdr0) in increase/decrease order.
    Limited to t_n, user_n and kuser_n headers.
    """
    if increase:
        print('Sort by header diff ({0:s}-{1:s}) in increase order.'.format(hdr1, hdr0))
    else:
        print('Sort by header diff ({0:s}-{1:s}) in decrease order.'.format(hdr1, hdr0))
    selelist, delelist = seleSeis(saclist)
    sortlist = []
    for slist in selelist, delelist:
        if len(slist) > 1:
            val = [ sacdh.gethdr(hdr1)-sacdh.gethdr(hdr0) for sacdh in slist ]
            if increase:
                indsort = argsort(val)
            else:
                indsort = argsort(val)[::-1]
            sorlist = [ slist[i] for i in indsort ]
        else:
            sorlist = []
        sortlist.append(sorlist)
    return sortlist


def hdrtype(sacdh, hdr):
    'Indentify type of a header'
    if hdr[0] == 't' or hdr[:4] == 'user' or hdr[:5] == 'kuser':
        htype = 'array'
    elif hdr in sacdh.__dict__:
        htype = 'other'
    else:
        print('{:s} is not a valid header for {:s}. Exit..'.format(hdr, sacdh.filename))
        sys.exit()
    return htype
        

def sortSeisHeader(saclist, hdr, increase=True):
    """ Sort saclist by a header value. """
    if increase:
        print('Sort by header {0:s} in increase order.'.format(hdr))
    else:
        print('Sort by header {0:s} in decrease order.'.format(hdr))
    selelist, delelist = seleSeis(saclist)
    htype = hdrtype(selelist[0], hdr)
    sortlist = []
    for slist in selelist, delelist:
        if len(slist) > 1:
            if htype == 'array':
                val = [ sacdh.gethdr(hdr) for sacdh in slist ]   # for t_n/user_n
            else: 
                val = [ sacdh.__dict__[hdr] for sacdh in slist ] # for az/baz/dist...
            if increase:
                indsort = argsort(val)
            else:
                indsort = argsort(val)[::-1]
            sorlist = [ slist[i] for i in indsort ]
        else:
            sorlist = []
        sortlist.append(sorlist)
    return sortlist


def getOptions():
    """ Parse arguments and options. """
    usage = "Usage: %prog [options] <sacfile(s) or a picklefile>"
    parser = OptionParser(usage=usage)
    opts, files = parser.parse_args(sys.argv[1:])
    return opts, files


# for testing
if __name__ == '__main__':
    from ttconfig import QCConfig
    from sacpickle import loadData
    from optparse import OptionParser

    opts, ifiles = getOptions()
    qcpara = QCConfig()
    qheaders = qcpara.qheaders
    qfactors = qcpara.qfactors
    qweights = qcpara.qweights
    hdrsel = qcpara.hdrsel
    opts.srate = -1
    gsac = loadData(ifiles, opts, qcpara)
    initQual(gsac.saclist, hdrsel, qheaders)
    sorselist, sordelist = sortSeisQual(gsac.saclist, qheaders, qweights, qfactors)

