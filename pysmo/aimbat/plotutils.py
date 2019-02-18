#!/usr/bin/env python
#------------------------------------------------
# Filename: plotutils.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009 Xiaoting Lou
#------------------------------------------------
"""
Python module for plotting seismograms:
    functions for axes and legend control, SpanSelector, and multiple-page navigation.

:copyright:
    Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""

from numpy import sign
import matplotlib.pyplot as plt
from matplotlib.widgets import SpanSelector
from matplotlib._pylab_helpers import Gcf
import os


def pickLegend(ax, npick, pickcolors, pickstyles, left=True):
    """ 
    Plot only legend box for time picks.
    """
    tpk = ax.get_xlim()[0] - 12345
    cols = pickcolors
    lss = pickstyles
    ncol = len(cols)
    for i in range(npick):
        ipk = 't' + str(i)
        ia = int(i%ncol)
        ib = int(i/ncol)
        col = cols[ia]
        ls = lss[ib]
        ax.axvline(x=tpk,color=col,ls=ls,lw=1.5,label=ipk.upper())
    if left:
        ax.legend(bbox_to_anchor=(-.027, 1), loc=1, borderaxespad=0., shadow=True, fancybox=True, handlelength=3)
    else:
        ax.legend(bbox_to_anchor=(1.02, 0), loc=3, borderaxespad=0., shadow=True, fancybox=True, handlelength=3)


class TimeSelector(SpanSelector):
    """ 
    To disable SpanSelector when pan, zoom or other interactive/navigation modes are active.
    Also disable it when event is out of axes, which is needed to avoid error interfering with pick_event.
    """
    def ignore(self, event):
        if event.inaxes != self.ax:
            return True
        elif 'zoom' in Gcf.get_active().toolbar.mode:
            return True
        elif event.name == 'pick_event':
            return True
        return False

def dataNorm(d, w=0.05):
    """ 
    Calculate normalization factor for d, which can be multi-dimensional arrays.
    Extra white space is added.
    """
    dmin, dmax = d.min(), d.max()
    dnorm = max(-dmin, dmax) * (1+w)
    return dnorm

def axLimit(minmax, w=0.05):
    """ 
    Calculate axis limit with white space (default 5%) from given min/max values.
    """
    ymin, ymax = minmax
    dy = ymax - ymin
    ylim = [ymin-w*dy, ymax+w*dy]
    return ylim

def indexBaseTick(na, nb, pagesize, pna):
    """ 
    Indexing for page navigation with two lists of length na and nb.

    Example:
        list b (nb=5)    list a (na=11)
        [ 0, 1, 2, 3, 4] [0,  1, 2, 3, 4, 5, 6, 7, 8,  9, 10] <-- yindex
        [ 5, 4, 3, 2, 1] [-1,-2,-3,-4,-5,-6,-7,-8,-9,-10,-11] <-- ybases
        [-5,-4,-3,-2,-1] [1,  2, 3, 4, 5, 6, 7, 8, 9, 10, 11] <-- yticks
       --page -1] [----page 0----] [---page 1---] [---page 2--- 
                 [pnb=2] [pna=3 ]               

        yindex for na and nb:
        {-1: [[], [0, 1, 2]],
         0: [[0, 1, 2], [3, 4]],
         1: [[3, 4, 5, 6, 7], []],
         2: [[8, 9, 10, 11, 12], []]}

        yybase:
        {-1: [[], [5, 4, 3]],
         0: [[-1, -2, -3], [2, 1]],
         1: [[-4, -5, -6, -7, -8], []],
         2: [[-9, -10, -11, -12, -13], []]}

        yticks:
        {-1: [[], [-5, -4, -3]],
         0: [[1, 2, 3], [-2, -1]],
         1: [[4, 5, 6, 7, 8], []],
         2: [[9, 10, 11, 12, 13], []]}
    """
    #indlista = list(range(na))
    #indlistb = list(range(nb))
    pnb = pagesize - pna
    # number of pages for list a and b
    ma = na - pna
    mb = nb - pnb
    npagea, npageb = 0, 0
    if ma > 0: npagea = ma//pagesize + sign(ma%pagesize)
    if mb > 0: npageb = mb//pagesize + sign(mb%pagesize)
    ipages = list(range(-npageb, npagea+1))
    ### yindex for page 0:
    yindex = {}
    ybases = {}
    yticks = {}
    ia1 = min(pna, na)
    ib0 = max(0, nb-pnb)
    inda = list(range(ia1))
    indb = list(range(ib0, nb))
    yindex[0] = [inda, indb]
    # positive page:
    for ipage in range(1, npagea+1):
        i1 = pna + ipage * pagesize
        i0 = i1 - pagesize
        inda = list(range(i0, min(i1, na)))
        yindex[ipage] = [inda, []]
    # negative page:
    for ipage in range(-npageb, 0):
        i1 = ib0 + ipage * pagesize + pagesize
        i0 = max(0, i1-pagesize)
        indb = list(range(i0, i1))
        yindex[ipage] = [[], indb]
    for ipage in range(-npageb, npagea+1):
        #print 'page ', ipage, yindex[ipage]
        ybases[ipage] = [ [], [] ]
        yticks[ipage] = [ [], [] ]
    ### ybases and yticks
    for ipage in range(0, npagea+1):
        ybases[ipage][0] = [ -1-ind for ind in yindex[ipage][0] ]
        yticks[ipage][0] = [  1+ind for ind in yindex[ipage][0] ]
    for ipage in range(-npageb, 1):
        ybases[ipage][1] = [ nb-ind for ind in yindex[ipage][1] ]
        yticks[ipage][1] = [ ind-nb for ind in yindex[ipage][1] ]
    return ipages, yindex, ybases, yticks




def getAxes(opts):
    """ Get axes for pickphase """
    fig = plt.figure(figsize=(13, 11))
    plt.rcParams['legend.fontsize'] = 11
    if opts.sort_on:
        rectseis = [0.1, 0.06, 0.65, 0.85]
    else:
        rectseis = [0.1, 0.06, 0.75, 0.85]
    axpp = fig.add_axes(rectseis)
    axs = {}
    axs['Seis'] = axpp
    dx = 0.07
    x0 = rectseis[0] + rectseis[2] + 0.01
    xq = x0 - dx*1
    xs = x0 - dx*2
    xn = x0 - dx*3
    xp = x0 - dx*4
#    xl = x0 - dx*5
    rectprev = [xp, 0.93, 0.06, 0.04]
    rectnext = [xn, 0.93, 0.06, 0.04]
    rectsave = [xs, 0.93, 0.06, 0.04]
    rectquit = [xq, 0.93, 0.06, 0.04]
#    rectlast = [xl, 0.93, 0.06, 0.04]
    axs['Prev'] = fig.add_axes(rectprev)
    axs['Next'] = fig.add_axes(rectnext)
#    axs['Last'] = fig.add_axes(rectlast)
    axs['Save'] = fig.add_axes(rectsave)
    axs['Quit'] = fig.add_axes(rectquit)
    return axs


def plotDelay(stalos, stalas, dtimes, opts):
    fig, ax = plt.subplots()
    ckey = 'RdBu_r'
    cmap = plt.get_cmap(ckey)
    ss = ax.scatter(stalos, stalas, c=dtimes, cmap=cmap, marker='^', vmin=opts.vminmax[0], vmax=opts.vminmax[1])
    cbar = fig.colorbar(ss)
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Longitude')
    fmt = 'png'
    if opts.savefig:
        fignm = opts.mcpara.mcname+'.'+fmt
        plt.savefig(fignm, format=fmt, dpi=300)
        os.system('open '+fignm)
    else:
        plt.show()
    return fig
