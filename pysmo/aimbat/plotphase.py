#!/usr/bin/env python
#------------------------------------------------
# Filename: plotphase.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009 Xiaoting Lou
#------------------------------------------------
"""
Python module for plotting multiple seismograms in one axes. 
    Plot only: no data/attributes of SAC files are changed.

Keyboard and mouse actions:
    Click mouse to select a span to zoom in seismograms.
    Press the 'z' key to go back to last window span.

Requried options: 
    One of azim_on, bazim_on, dist_on, index_on, zero_on must be chosen. Default is index_on.
    Correspong to:  paz, pbaz, prs, p1 and p2. Default: p1
These functions can be acheived by scripts created for each mode.

Optional options:
    pick_on, color_on, stack_on, std_on

Program structure:
    SingleSeisGather
        ||                 
    SingleSeis       + baseIndex + baseZero + baseDist + baseAzim + baseBAzim
                          |           |          |           |          |
                          V           V          V           V          V
                        sacp1       sacp2      sacprs     sacpaz      sacpbaz

:copyright:
    Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""


import sys, copy
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import transforms
from matplotlib.font_manager import FontProperties

from pysmo.aimbat import ttconfig
from pysmo.aimbat import sacpickle as sacpkl
from pysmo.aimbat import plotutils as putil


def getOptions():
    """ Parse arguments and options. """
    parser = ttconfig.getParser()
    parser.add_option('-a', '--azim', action="store_true", dest='azim_on',
        help='Set baseline of seismograms as azimuth.')
    parser.add_option('-b', '--bazim', action="store_true", dest='bazim_on',
        help='Set baseline of seismograms as backazimuth.')
    parser.add_option('-d', '--dist', action="store_true", dest='dist_on',
        help='Set baseline of seismograms as epicentral distance in degree.')
    parser.add_option('-D', '--distkm', action="store_true", dest='distkm_on',
        help='Set baseline of seismograms as epicentral distance in km.')
    parser.add_option('-i', '--index', action="store_true", dest='index_on',
        help='Set baseline of seismograms as file indices (SAC P1 style).')
    parser.add_option('-z', '--zero', action="store_true", dest='zero_on',
        help='Set baseline of seismograms as zeros (SAC P2 style).')
    parser.add_option('-m', '--stack_mean', action="store_true", dest='stack_on',
        help='Plot mean stack of seismograms.')
    parser.add_option('-s', '--stack_std', action="store_true", dest='std_on',
        help='Plot std of mean stack of seismograms with color fill.')
    parser.add_option('-C', '--color', action="store_true", dest='color_on',
        help='Use random colors.')
    opts, files = parser.parse_args(sys.argv[1:])
    if len(files) == 0:
        print(parser.usage)
        sys.exit()
    return opts, files

class SingleSeis:
    """ 
    Plot a single seismogram with given attributes.
    """
    def __init__(self, sacdh, opts, axss, ybase, color='b', linew=1, alpha=1):
        self.sacdh = sacdh
        self.opts = opts
        self.axss = axss
        self.ybase = ybase
        self.color = color
        self.linew = linew
        self.alpha = alpha
        self.makeTime()
        self.plotWave()
        self.connect()

    def makeTime(self):
        """ 
        Create array x as time series and get reference time.
        """
        sacdh = self.sacdh
        b, npts, delta = sacdh.b, sacdh.npts, sacdh.delta
        self.time = np.linspace(b, b+(npts-1)*delta, npts)
        reltime = self.opts.reltime
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
            
    def plotWave(self):
        """
        Plot wiggled or filled waveform, which is normalized (if not stacking) and shifted to ybase.
        Fill both plus and negative side of signal but with different transparency.
            If opts.fill == 0: no fill.
            If opts.fill >  0: alpha of negative side is a quarter of plus side.
            If opts.fill <  0: alpha of plus side is a quarter of negative side.
        """
        # get x, y
        opts = self.opts
        ybase = self.ybase
        x = self.time - self.sacdh.reftime
        d = self.sacdh.data
        axss = self.axss
        if self.opts.ynorm > 0:
            dnorm = putil.dataNorm(d)
            dnorm = 1/dnorm*self.opts.ynorm*.5
        else:
            dnorm = 1
        y = d * dnorm
        # plot
        line, = axss.plot(x, y+ybase, ls='-', color=self.color, lw=self.linew, alpha=self.alpha, picker=5)
        self.lines = [line,]
        if opts.fill == 0:
            axss.axhline(y=ybase, color='k', ls=':')
            self.wvfills = []
        else:
            f = opts.fill
            fplus, fnega, = [], []
            for i in range(len(x)):
                if f*y[i] > 0:
                    fplus.append(True)
                    fnega.append(False)
                else:
                    fplus.append(False)
                    fnega.append(True)
            wvfillplus = axss.fill_between(x, ybase, y+ybase, where=fplus, color=self.color, alpha=self.alpha*0.6)
            wvfillnega = axss.fill_between(x, ybase, y+ybase, where=fnega, color=self.color, alpha=self.alpha*0.2)
            self.wvfills = [wvfillplus, wvfillnega]

    def onpick(self, event):
        if not len(event.ind): return True
        pick = False
        for line in self.lines:
            if event.artist == line:
                pick = True
        if not pick: return True
        try:
            print('Seismogram picked: {:s} '.format(self.sacdh.filename))
        except AttributeError:
            print('Not a SAC file')

    def connect(self):
        self.cidpick = self.axss.figure.canvas.mpl_connect('pick_event', self.onpick)

    def disconnect(self):
        self.axss.figure.canvas.mpl_disconnect(self.cidpick)

    def plotPicks(self):
        """ 
        Plot time picks. Not called by default.
        Only works for baseIndex mode because axvline is not used to plot time picks.
        """
        sacdh = self.sacdh
        axss = self.axss
        pppara = self.opts.pppara
        npick = pppara.npick
        cols = pppara.pickcolors
        ncol = len(cols)
        lss = pppara.pickstyles
        thdrs = np.array(sacdh.thdrs) - sacdh.reftime
        timepicks = [None]*npick
        for i in range(npick):
            tpk = thdrs[i]
            ia = i%ncol
            ib = i/ncol
            col = cols[ia]
            ls = lss[ib]
            xx = [tpk, tpk]
            yy = [self.ybase-.5, self.ybase+.5]
            timepicks[i] = axss.plot(xx, yy, color=col,ls=ls,lw=1.5)
        self.timepicks = timepicks


class SingleSeisGather():
    """ 
    Plot a group of seismograms.
    """
    def __init__(self, saclist, opts, axss):
        self.saclist = saclist
        self.opts = opts
        self.axss = axss
        self.nseis = len(saclist)
        self.stackcolor = 'r'
        self.stackbase = 0
        self.stacklinew = 2
        self.getPlot()
        self.getYLimit()
        # choose a type of y base:
        if opts.zero_on:
            self.baseZero()
        elif opts.azim_on:
            self.baseAzim()
        elif opts.bazim_on:
            self.baseBAzim()
        elif opts.dist_on:
            self.baseDist()
        elif opts.distkm_on:
            self.baseDistkm()
        else:
            self.baseIndex()
        # plot
        self.plotSeis()
        if opts.stack_on:
            self.plotStack()
        if opts.pick_on:
            self.plotPicks()
        self.plotSpan()
        self.connect()

    def baseIndex(self):
        """ 
        Set baseline of seismograms as file indices.
        """
        self.getIndex()
        if self.opts.stack_on:
            self.yzoom = [-self.nseis-1, 1]
        self.labelStation()
        yticks = self.ybases
        ylabs = list(range(1 , self.nseis+1))
        self.axss.set_yticks(yticks)
        self.axss.set_yticklabels(ylabs)
        self.axss.set_ylabel('Trace Number')

    def baseZero(self):
        """ 
        Set baseline of seismograms as zeros (stack all).
        Do not normalize seismogram by setting opts.ynorm<0.
        """
        self.getZero()
        anorm = 1./np.clip(self.nseis/50, 2, 10)
        self.alphas *= anorm
        self.opts.ynorm = -1
        #self.axss.ticklabel_format(style='sci', scilimits=(0,0), axis='y')
        formatter = plt.ScalarFormatter(useMathText=True)
        formatter.set_powerlimits((0, 0))
        self.axss.yaxis.set_major_formatter(formatter)

    def baseDist(self):
        """ 
        Set baseline of seismograms as epicentral distance in degree.
        """
        self.getDist(True)
        self.labelStation()
        self.axss.set_ylabel('Distance ['+ r'$\degree$' + ']')

    def baseDistkm(self):
        """ 
        Set baseline of seismograms as epicentral distance in km.
        """
        self.getDist(False)
        self.labelStation()
        self.axss.set_ylabel('Distance [km]')

    def baseAzim(self):
        """ 
        Set baseline of seismograms as azimuth.
        """
        self.getAzim()
        self.labelStation()
        self.axss.set_ylabel('Azimuth ['+ r'$\degree$' + ']')

    def baseBAzim(self):
        """ 
        Set baseline of seismograms as back azimuth.
        """
        self.getBAzim()
        self.labelStation()
        self.axss.set_ylabel('Backazimuth ['+ r'$\degree$' + ']')

    def plotSeis(self):
        """ 
        Plot wiggles or filled waveforms.
        """
        opts = self.opts
        axss = self.axss
        saclist = self.saclist
        nseis = self.nseis
        sss = []
        for i in range(nseis):
            ss = SingleSeis(saclist[i], opts, axss, self.ybases[i], self.colors[i], self.linews[i], self.alphas[i])
            sss.append(ss)
        self.sss = sss
        self.getXLimit()
        axss.set_xlim(self.xzoom[0])
        axss.set_ylim(self.yzoom)
        reltime = self.opts.reltime
        if reltime >= 0:
            axss.set_xlabel('Time - T%d [s]' % reltime)
        else:
            axss.set_xlabel('Time [s]')
        # plot time zero lines and set axis limit
        axss.axvline(x=0, color='k', ls=':')
        if not self.opts.xlimit is None:
            axss.set_xlim(self.opts.xlimit)

    def labelStation(self):
        """
        Label stations at y axis on the right.
        The xcoords of the transform are axes, and the yscoords are data.
        """
        axss = self.axss
        stations = [ sacdh.netsta for sacdh in self.saclist ]
        trans = transforms.blended_transform_factory(axss.transAxes, axss.transData)
        font = FontProperties()
        font.set_family('monospace')
        for i in range(self.nseis):
            axss.text(1.02, self.ybases[i], stations[i], transform=trans, va='center', 
                color=self.colors[i], fontproperties=font)
        if self.opts.stack_on:
            axss.text(1.02, self.stackbase, 'Stack', transform=trans, va='center',
                color=self.stackcolor, fontproperties=font)


    def plotStack(self):
        """ 
        Calculate mean stack from all traces and plot it. 
        No taper window is added in.
        """
        saclist = self.saclist
        mm = self.bmax, self.emin
        twplot = putil.axLimit(mm, -0.01)
        twp = twplot[1] - twplot[0]
        taperwindow = 0
        reftimes = [ sacdh.reftime for sacdh in saclist ]
        nstart, ntotal = putil.windowIndex(saclist, reftimes, twplot, taperwindow)
        datacut = putil.windowData(saclist, nstart, ntotal, taperwindow/twp)
        datamean = np.mean(datacut, 0)
        # copy a sacdh object for stack
        stackdh = copy.copy(saclist[0])
        stackdh.b = twplot[0] - taperwindow*0.5
        stackdh.npts = len(datamean)
        stackdh.data = datamean
        stackdh.thdrs = [0.,]*10
        stackdh.filename = 'meanstack.sac'
        self.sstack = SingleSeis(stackdh, self.opts, self.axss, self.stackbase, self.stackcolor, self.stacklinew)
        # plot 1-std range from mean stack
        if self.opts.zero_on and self.opts.std_on:
            datastd = np.std(datacut, 0)
            stda = copy.copy(stackdh)
            stdb = copy.copy(stackdh)
            stda.data = datamean + datastd
            stdb.data = datamean - datastd
            stda.thdrs = [0,]*10
            stdb.thdrs = [0,]*10
            stda.filename = 'stackstdplus.sac'
            stda.filename = 'stackstdnega.sac'
            self.sstda = SingleSeis(stda, self.opts, self.axss, self.stackbase, self.stackcolor, self.stacklinew/2.)
            self.sstdb = SingleSeis(stdb, self.opts, self.axss, self.stackbase, self.stackcolor, self.stacklinew/2.)
            self.stdfill = self.axss.fill_between(self.sstack.time, stda.data, stdb.data, color=self.stackcolor, alpha=.25)

    def getXLimit(self):
        """ Get x limit (relative to reference time) """
        sss = self.sss
        b = [ ss.time[0]  - ss.sacdh.reftime for ss in sss ]
        e = [ ss.time[-1] - ss.sacdh.reftime for ss in sss ]
        self.bmin = min(b) 
        self.bmax = max(b)
        self.emin = min(e) 
        self.emax = max(e)
        mm = self.bmin, self.emax
        xxlim = putil.axLimit(mm)
        self.xzoom = [xxlim,]

    def getYLimit(self):
        """ Get y limit    """
        saclist = self.saclist
        #delta = saclist[0].delta
        data = np.array([ [min(sacdh.data), max(sacdh.data) ] for sacdh in saclist ])
        self.dmin = data[:,0].min()
        self.dmax = data[:,1].max() 

    def getPlot(self):
        """ Get plotting attributes """
        self.linews = np.ones(self.nseis)
        self.alphas = np.ones(self.nseis)
        if self.opts.color_on:
            self.colors = np.random.rand(self.nseis, 3)
        else:
            self.colors = [self.opts.pppara.colorwave,] * self.nseis

    def getIndex(self):
        """ Get file indices as ybases for waveforms. """
        self.ybases = -np.arange(self.nseis) - 1
        self.yzoom = [-self.nseis-1, 0]

    def getZero(self):
        """ Get zeros as ybases for waveforms. """
        self.ybases = np.zeros(self.nseis)
        mm = self.dmin, self.dmax
        self.yzoom = putil.axLimit(mm)

    def getDist(self, degree=True):
        """ Get epicentral distances in degree/km as ybases for waveforms. """
        if degree:
            dists = [ sacdh.gcarc for sacdh in self.saclist ]
        else:
            dists = [ sacdh.dist  for sacdh in self.saclist ]
        self.ybases = dists
        mm = min(dists), max(dists)
        self.yzoom = putil.axLimit(mm, 0.1)
        if self.opts.stack_on:
            self.stackbase = (mm[1]+self.yzoom[1])/2
            self.yzoom[1] += (self.yzoom[1]-mm[1])/2

    def getAzim(self):
        """ Get azimuth as ybases for waveforms. """
        azims = [ sacdh.az for sacdh in self.saclist ]
        self.ybases = azims
        mm = min(azims), max(azims)
        self.yzoom = putil.axLimit(mm, 0.1)
        if self.opts.stack_on:
            self.stackbase = (mm[1]+self.yzoom[1])/2
            self.yzoom[1] += (self.yzoom[1]-mm[1])/2

    def getBAzim(self):
        """ Get back azimuth as ybases for waveforms. """
        bazims = [ sacdh.baz for sacdh in self.saclist ]
        self.ybases = bazims
        mm = min(bazims), max(bazims)
        self.yzoom = putil.axLimit(mm, 0.1)
        if self.opts.stack_on:
            self.stackbase = (mm[1]+self.yzoom[1])/2
            self.yzoom[1] += (self.yzoom[1]-mm[1])/2

    def plotSpan(self):
        """ Create a SpanSelector on axss. """
        axss = self.axss
        def on_select(xmin, xmax):
            'Mouse event: select span.'
            print ('span selected: {0:6.1f} {1:6.1f}'.format(xmin, xmax))
            xxlim = (xmin, xmax)
            axss.set_xlim(xxlim)
            self.xzoom.append(xxlim)
            axss.figure.canvas.draw()
        pppara = self.opts.pppara
        a, col = pppara.alphatwsele, pppara.colortwsele
        mspan = pppara.minspan * self.opts.delta
        self.span = putil.TimeSelector(axss, on_select, 'horizontal', minspan=mspan, useblit=False,
            rectprops=dict(alpha=a, facecolor=col))

    def on_zoom(self, event):
        """ Zoom back to previous xlim when event is in event.inaxes. """
        evkey = event.key
        axss = self.axss
        if not axss.contains(event)[0] or evkey is None: return
        xzoom = self.xzoom
        if evkey.lower() == 'z' and len(xzoom) > 1:
            del xzoom[-1]
            axss.set_xlim(xzoom[-1])
            print('Zoom back to: {:6.1f} {:6.1f}'.format(tuple(xzoom[-1])) )
            axss.figure.canvas.draw()

    def connect(self):
        self.cidpress = self.axss.figure.canvas.mpl_connect('key_press_event', self.on_zoom)

    def disconnect(self):
        self.axss.figure.canvas.mpl_disconnect(self.cidpress)
        self.span.visible = False

    def plotPicks(self):
        for ss in self.sss:
            ss.plotPicks()
        pppara = self.opts.pppara
        putil.pickLegend(self.axss, pppara.npick, pppara.pickcolors, pppara.pickstyles)


def dopts(opts):
    ' Default options '
    for key in ['pick_on', 'stack_on', 'std_on', 'color_on']:
        if not key in opts.__dict__.keys():
            opts.__dict__[key] = False
    return opts


def sacp1(saclist, opts, axss):
    ' SAC P1 style of plotting. '
    opts = dopts(opts)
    opts.index_on = True
    opts.zero_on = False
    opts.dist_on = False
    opts.azim_on = False
    ssg = SingleSeisGather(saclist, opts, axss)
    return ssg
    
def sacp2(saclist, opts, axss):
    ' SAC P2 style of plotting. '
    opts = dopts(opts)
    opts.index_on = False
    opts.zero_on = True
    opts.dist_on = False
    opts.azim_on = False
    opts.bazim_on = False
    opts.fill = 0
    ssg = SingleSeisGather(saclist, opts, axss)
    return ssg

def sacprs(saclist, opts, axss):
    ' SAC PRS style of plotting: record section. '
    opts = dopts(opts)
    opts.index_on = False
    opts.zero_on = False
    if opts.distkm_on: 
        opts.dist_on = False
    else:
        opts.dist_on = True
    opts.azim_on = False
    opts.bazim_on = False
    ssg = SingleSeisGather(saclist, opts, axss)
    return ssg

def sacpaz(saclist, opts, axss):
    ' SAC plotting along azimuth.    '
    opts = dopts(opts)
    opts.index_on = False
    opts.zero_on = False
    opts.dist_on = False
    opts.azim_on = True
    opts.bazim_on = False
    ssg = SingleSeisGather(saclist, opts, axss)
    return ssg

def sacpbaz(saclist, opts, axss):
    ' SAC plotting along backazimuth.    '
    opts = dopts(opts)
    opts.index_on = False
    opts.zero_on = False
    opts.dist_on = False
    opts.bazim_on = True
    ssg = SingleSeisGather(saclist, opts, axss)
    return ssg

def splitAxesH(fig, rect=[0.1,0.1,0.6,0.6], n=2, hspace=0, axshare=False):
    """ 
    Split an axes to multiple (n,1,i) horizontal axes.    
    Share x-axis if axshare is True.
    """
    x0, y0, dx, dy = rect
    dyi = dy/n
    if axshare:
        i = 0
        ax0 = fig.add_axes([x0,y0+dy-(i+1)*dyi,dx,dyi*(1-hspace)])
        axs = [ax0] + [ fig.add_axes([x0,y0+dy-(i+1)*dyi,dx,dyi*(1-hspace)], sharex=ax0) for i in range(1,n) ]
    else:
        axs = [ fig.add_axes([x0,y0+dy-(i+1)*dyi,dx,dyi*(1-hspace)]) for i in range(n) ]
    return axs

def getAxes(opts):
    'Get axes for plotting'
    fig = plt.figure(figsize=opts.pppara.figsize)
    plt.rcParams['legend.fontsize'] = 11
    axss = fig.add_axes(opts.pppara.rectseis)
    return axss

def getDataOpts():
    'Get SAC Data and Options'
    opts, ifiles = getOptions()
    pppara = ttconfig.PPConfig()
    gsac = sacpkl.loadData(ifiles, opts, pppara)
    opts.pppara = pppara
    return gsac, opts

def sacp1_standalone():
    gsac, opts = getDataOpts()
    axss = getAxes(opts)
    ssg = sacp1(gsac.saclist, opts, axss)
    plt.show()

def sacp2_standalone():
    gsac, opts = getDataOpts()
    axss = getAxes(opts)
    ssg = sacp2(gsac.saclist, opts, axss)
    plt.show()

def sacpaz_standalone():
    gsac, opts = getDataOpts()
    axss = getAxes(opts)
    ssg = sacpaz(gsac.saclist, opts, axss)
    plt.show()

def sacpbaz_standalone():
    gsac, opts = getDataOpts()
    axss = getAxes(opts)
    ssg = sacpbaz(gsac.saclist, opts, axss)
    plt.show()

def sacplot_standalone():
    gsac, opts = getDataOpts()
    axss = getAxes(opts)
    ssg = SingleSeisGather(gsac.saclist, opts, axss)
    plt.show()

def sacprs_standalone():
    gsac, opts = getDataOpts()
    axss = getAxes(opts)
    ssg = sacprs(gsac.saclist, opts, axss)
    plt.show()


def main():
    gsac, opts = getDataOpts()
    axss = getAxes(opts)
    SingleSeisGather(gsac.saclist, opts, axss)


if __name__ == "__main__":
    main()
    plt.show()
