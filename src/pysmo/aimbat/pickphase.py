#!/usr/bin/env python
#------------------------------------------------
# Filename: pickphase.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009 Xiaoting Lou
#------------------------------------------------
"""

Python module for plot and pick phase (SAC PPK) on seismograms in one axes.

Differences from plotphase.py:
  * User interaction: set time picks and time window
  * Plot: always plot time picks
  * Plot: always use integer numbers (plot within +/-0.5) as ybases, 
        but not dist/az/baz (even when sorted by d/a/b)
  * Plot: can plot seismograms in multiple pages (page navigation).
  * Normalization: can normalize within time window

Keyboard and mouse actions:
  * Click mouse to select a span to zoom in seismograms.
  * Press 'z' to go back to last window span.
  * Press 'w' to save the current xlimit as time window.
  * Press 't[0-9]' to set time picks like SAC PPK.

Program structure:
    PickPhaseMenu
        ||
    PickPhase  Button Front + Button Prev + Button Next + Button Last + Button Save + Button Quit


:copyright:
    Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""

import sys
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Button
from matplotlib import transforms
from matplotlib.font_manager import FontProperties
from tkinter import messagebox

from pysmo.aimbat import ttconfig
from pysmo.aimbat import qualsort
from pysmo.aimbat import sacpickle as sacpkl
from pysmo.aimbat import plotutils as putil
from pysmo.aimbat import prepdata  as pdata
from pysmo.aimbat import filtering as ftr


def getOptions():
    """ Parse arguments and options. """
    parser = ttconfig.getParser()
    maxsel = 25
    maxdel = 5
    maxnum = maxsel, maxdel
    sortby = 'i'
    parser.set_defaults(maxnum=maxnum)
    parser.set_defaults(sortby=sortby)
    parser.add_option('-b', '--boundlines', action="store_true", dest='boundlines_on',
        help='Plot bounding lines to separate seismograms.')
    parser.add_option('-n', '--netsta', action="store_true", dest='nlab_on',
        help='Label seismogram by net.sta code instead of SAC file name.')
    parser.add_option('-m', '--maxnum',  dest='maxnum', type='int', nargs=2,
        help='Maximum number of selected and deleted seismograms to plot. Defaults: {0:d} and {1:d}.'.format(maxsel, maxdel))
    parser.add_option('-s', '--sortby', type='str', dest='sortby',
        help='Sort seismograms by i (file indices), or 0/1/2/3 (quality factor all/ccc/snr/coh), or a given header (az/baz/dist..). Append - for decrease order, otherwise increase. Default is {:s}.'.format(sortby))
    opts, files = parser.parse_args(sys.argv[1:])
    if len(files) == 0:
        print(parser.usage)
        sys.exit()
    return opts, files

# ############################################################################### #
#                                                                                 #
#                                  CLASS: PickPhase                               #
#                                                                                 #
# ############################################################################### #

class PickPhase:
    """ 
    Plot one single seismogram with given attributes.
    See self.on_press for options on setting time picks and time window.
    """
    def __init__(self, sacdh, opts, axpp, ybase, color='b', linew=1, alpha=1):
        self.sacdh = sacdh
        self.opts = opts
        self.axpp = axpp
        self.ybase = ybase
        self.color = color
        self.linew = linew
        self.alpha = alpha
        self.makeTime()
        if opts.twin_on:
            self.plotWindow()
        self.plotWave()
        self.connect()

    def makeTime(self):
        """ 
        Create array x as time series and get reference time.
        """
        sacdh = self.sacdh
        self.time = sacdh.time
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
        opts = self.opts
        ybase = self.ybase
        x = self.time - self.sacdh.reftime
        d = self.sacdh.data

        if hasattr(self, 'twindow') and opts.ynormtwin_on:
            dnorm = pdata.dataNormWindow(d, self.time, self.twindow)
        else:
            dnorm = pdata.dataNorm(d)
        dnorm = 1/dnorm * opts.ynorm/2
        
        yori = dnorm * d 
        ymem = dnorm * self.sacdh.datamem
        # plot
        self.ynorm = [dnorm,]
        axpp = self.axpp
        line1, = axpp.plot(x, ymem+ybase, ls='-', color=self.color, lw=self.linew, alpha=self.alpha, picker=5)
        self.lines = [line1, ]
        if opts.fill == 0:
            axpp.axhline(y=ybase, color='k', ls=':')
            self.wvfills = []
        else:
            f = opts.fill
            fplus, fnega, = [], []
            for i in range(len(x)):
                if f*ymem[i] > 0:
                    fplus.append(True)
                    fnega.append(False)
                else:
                    fplus.append(False)
                    fnega.append(True)
            wvfillplus = axpp.fill_between(x, ybase, ymem+ybase, where=fplus, color=self.color, alpha=self.alpha*0.6)
            wvfillnega = axpp.fill_between(x, ybase, ymem+ybase, where=fnega, color=self.color, alpha=self.alpha*0.2)
            self.wvfills = [wvfillplus, wvfillnega]
        self.labelStation()

    def labelStation(self):
        """ label the seismogram with file name or net.sta 
        """
        axpp = self.axpp
        sacdh = self.sacdh
        if self.opts.nlab_on:
            slab = '{0:<8s}'.format(sacdh.netsta)
        else:
            slab = sacdh.filename.split('/')[-1]
        if self.opts.labelqual:
            hdrcc, hdrsn, hdrco = self.opts.qheaders[:3]
            cc = sacdh.gethdr(hdrcc)
            sn = sacdh.gethdr(hdrsn)
            co = sacdh.gethdr(hdrco)
            slab += 'qual={0:4.2f}/{1:.1f}/{2:4.2f}'.format(cc, sn, co)
        trans = transforms.blended_transform_factory(axpp.transAxes, axpp.transData)
        font = FontProperties()
        font.set_family('monospace')
        self.stalabel = axpp.text(1.025, self.ybase, slab, transform=trans, va='center', 
            color=self.color, fontproperties=font)
    
    def on_pick(self, event):
        """ Click a seismogram to show file name.
        """
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
        self.sacdh.selected = not self.sacdh.selected
        # for bytes!=str in py3
        if self.sacdh.selected:
            self.sacdh.sethdr(self.opts.hdrsel, 'True')
        else:
            self.sacdh.sethdr(self.opts.hdrsel, b'False   ')
        self.changeColor()

    def changeColor(self):
        """ Change color of a seismogram based on selection status. 
        """
        if self.sacdh.selected:
            col = self.opts.pppara.colorwave
        else:
            col = self.opts.pppara.colorwavedel
        plt.setp(self.stalabel, color=col)
        plt.setp(self.lines[0], color=col)
        if self.wvfills != []:
            plt.setp(self.wvfills[0], color=col)
            plt.setp(self.wvfills[1], color=col)
        self.axpp.figure.canvas.draw()

    def changeBase(self, newbase):
        """ Change ybase of a seismogram.
        """
        plt.setp(self.lines[0], ydata=newbase)

    def plotWindow(self):
        """ Plot time window (xmin,xmax) with color fill. 
        """
        axpp = self.axpp
        sacdh = self.sacdh
        twh0, twh1 = self.opts.pppara.twhdrs
        self.twhdrs = twh0, twh1
        tw0 = sacdh.gethdr(twh0)
        tw1 = sacdh.gethdr(twh1)    
        if tw0 == -12345.0:
            tw0 = self.x[0]
        if tw1 == -12345.0:
            tw1 = self.x[-1]
        self.twindow = [tw0, tw1]
        tw0 -= sacdh.reftime 
        tw1 -= sacdh.reftime
        #ymin, ymax = axpp.get_ylim()
        ymin, ymax = self.ybase-0.5, self.ybase+0.5
        pppara = self.opts.pppara
        a, col = pppara.alphatwfill, pppara.colortwfill
        self.twfill, = axpp.fill([tw0,tw1,tw1,tw0], 
            [ymin,ymin,ymax,ymax], col, alpha=a, edgecolor=col)

    def resetWindow(self):
        """ Reset time window when a span is selected.
        """
        tw, reftime = self.twindow, self.sacdh.reftime
        tw0 = tw[0] - reftime
        tw1 = tw[1] - reftime
        xypoly = self.twfill.get_xy()
        xypoly[0:5,0] = np.ones(5)*tw0
        xypoly[1:3,0] = np.ones(2)*tw1
        self.twfill.set_xy(xypoly)

    def plotPicks(self):
        """ Plot time picks at ybase +/- 0.5
        """
        sacdh = self.sacdh
        axpp = self.axpp
        pppara = self.opts.pppara
        npick = pppara.npick
        cols = pppara.pickcolors
        ncol = len(cols)
        lss = pppara.pickstyles
        thdrs = np.array(sacdh.thdrs) - sacdh.reftime
        timepicks = [None]*npick
        for i in range(npick):
            tpk = thdrs[i]
            ia = int(i%ncol)
            ib = int(i/ncol)
            col = cols[ia]
            ls = lss[ib]
            xx = [tpk, tpk]
            yy = [self.ybase-.5, self.ybase+.5]
            timepicks[i], = axpp.plot(xx, yy, color=col,ls=ls,lw=1.5)
        self.timepicks = timepicks

    def on_press(self, event):
        """ 
        Key press event. Valid only if axpp contains event (within 0.5 from ybase).
        Options:
        --------
        (1) t + digits 0-9: set a time pick in SAC header.
        (2) w: set the current xlim() as time window.
        """
        evkey = event.key
        axpp = self.axpp
        contains, attr = axpp.contains(event)
        if not contains or evkey is None: return
        if abs(event.ydata-self.ybase) > 0.5: return
        opts = self.opts
        sacdh = self.sacdh
        twin_on = opts.twin_on
        reftime = sacdh.reftime
        evkey0 = self.evkeys[1]
        self.evkeys = evkey0 + evkey
        if evkey.lower() == 'w' and twin_on:
            twh0, twh1 = self.twhdrs
            xxlim = axpp.get_xlim()
            tw0 = xxlim[0] + reftime
            tw1 = xxlim[1] + reftime
            sacdh.sethdr(twh0, tw0)
            sacdh.sethdr(twh1, tw1)
            self.twindow = [tw0, tw1]
            out = 'File {:s}: set time window to {:s} and {:s}: {:6.1f} - {:6.1f} s'
            print(out.format(sacdh.filename, twh0, twh1, tw0, tw1))
            self.resetWindow()
        elif evkey0.lower() == 't' and evkey.isdigit() and opts.pick_on:
            timepicks = self.timepicks
            ipk = 't' + evkey
            ipick = int(evkey)
            tpk = event.xdata
            atpk = tpk + reftime
            sacdh.thdrs[ipick] = atpk
            out = 'File {:s}: pick phase {:s} = {:6.1f} s, absolute = {:6.1f} s. '
            print(out.format(sacdh.filename, ipk, tpk, atpk))
            timepicks[ipick].set_xdata(tpk)
        axpp.figure.canvas.draw()

    def updateY(self, xxlim):
        """ Update ynorm for wave wiggle from given xlim.
        """
        x = self.time - self.sacdh.reftime
        d = self.sacdh.data
        dnorm = pdata.dataNormWindow(d, x, xxlim)
        dnorm = 1/dnorm * self.opts.ynorm/2
        self.ynorm.append(dnorm)
        plt.setp(self.lines[0], ydata=self.ybase+dnorm*d)
        plt.setp(self.lines[1], ydata=self.ybase+dnorm*self.sacdh.datamem)

    def connect(self):
        self.cidpick = self.axpp.figure.canvas.mpl_connect('pick_event', self.on_pick)
        self.cidpress = self.axpp.figure.canvas.mpl_connect('key_press_event', self.on_press)
        self.evkeys = 'xx'

    def disconnect(self):
        self.axpp.figure.canvas.mpl_disconnect(self.cidpick)
        self.axpp.figure.canvas.mpl_disconnect(self.cidpress)

    def disconnectPick(self):
        self.axpp.figure.canvas.mpl_disconnect(self.cidpick)

# ############################################################################### #
#                                                                                 #
#                                  CLASS: PickPhase                               #
#                                                                                 #
# ############################################################################### #

# ############################################################################### #
#                                                                                 #
#                               CLASS: PickPhaseMenu                              #
#                                                                                 #
# ############################################################################### #

class PickPhaseMenu():
    """ 
    Plot a group of seismogram gathers. 
    Set up axes attributes.
    Create Button Save to save SAC headers to files.
    """
    def __init__(self, gsac, opts, axs):
        self.gsac = gsac
        self.opts = opts
        self.axs = axs
        self.axpp = axs['Seis']
        self.initIndex()
        self.plotSeis()
        self.plotSpan()
        self.connect()
        pppara = opts.pppara
        putil.pickLegend(self.axpp, pppara.npick, pppara.pickcolors, pppara.pickstyles)
    
    def plotSeis(self):    
        self.plotWave()
        self.setLimits()
        self.setLabels()
        if self.opts.pick_on:
            self.plotPicks()
        self.labelSelection()

    def initIndex(self):
        """ Initialize indices for page navigation. 
        """
        opts = self.opts
        #axs = self.axs
        selist = self.gsac.selist
        delist = self.gsac.delist
        nsel = len(selist)
        ndel = len(delist)
        maxsel, maxdel = opts.maxnum
        pagesize = maxsel + maxdel
        aipages, ayindex, aybases, ayticks = putil.indexBaseTick(nsel, ndel, pagesize, maxsel)
        self.aipages = aipages
        self.ayindex = ayindex
        self.aybases = aybases
        self.ayticks = ayticks
        self.sedelist = [selist, delist]
        self.ipage = 0

    def plotWave(self):
        """ Plot waveforms for this page. 
        """
        opts = self.opts
        axpp = self.axpp
        ipage = self.ipage
        ayindex, aybases, ayticks = self.ayindex, self.aybases, self.ayticks
        sedelist = self.sedelist
        plists = [ [ sedelist[j][k] for k in ayindex[ipage][j] ] for j in range(2) ]
        pbases = [ [ k              for k in aybases[ipage][j] ] for j in range(2) ]
        pticks = [ [ k              for k in ayticks[ipage][j] ] for j in range(2) ]
        npsel = len(pbases[0])
        npdel = len(pbases[1])
        nsede = [npsel, npdel]
        # get colors from sacdh.selected
        colsel = opts.pppara.colorwave
        coldel = opts.pppara.colorwavedel
        colors = [[None,] * npsel , [None,] * npdel]
        for j in range(2):
            for k in range(nsede[j]):
                if plists[j][k].selected:
                    colors[j][k] = colsel
                else:
                    colors[j][k] = coldel
        # plot
        pps = []
        for j in range(2):
            nsd = nsede[j]
            for k in range(nsd):
                #linews = np.ones(nsd)
                #alphas = np.ones(nsd)
                pp = PickPhase(plists[j][k], opts, axpp, pbases[j][k], colors[j][k])
                pps.append(pp)
        self.pps = pps
        self.ybases = pbases[0] + pbases[1]
        self.yticks = pticks[0] + pticks[1]
        abases = pbases[1]+pbases[0]
        self.azylim = abases[-1]-1, abases[0]+1

    def replot(self, ipage):
        """    Finish plotting of current page and move to prev/next.
        """
        self.ipage = ipage
        if not self.ipage in self.aipages:
            print ('End of page.')
            return
        self.finish()
        self.plotSeis()

    def on_select(self, xmin, xmax):
        """ Mouse event: select span. """
        if self.span.visible:
            print('span selected: {:6.1f} {:6.1f} '.format(xmin, xmax))
            xxlim = (xmin, xmax)
            self.axpp.set_xlim(xxlim)
            self.xzoom.append(xxlim)
            if self.opts.upylim_on:
                print ('upylim')
                for pp in self.pps: pp.updateY(xxlim)
            self.axpp.figure.canvas.draw()

    # change window size in seismograms plot here
    def plotSpan(self):
        """ Create a SpanSelector for zoom in and zoom out.
        """
        pppara = self.opts.pppara
        a, col = pppara.alphatwsele, pppara.colortwsele
        mspan = pppara.minspan * self.opts.delta
        self.span = putil.TimeSelector(self.axpp, self.on_select, 'horizontal', minspan=mspan, useblit=False,
            rectprops=dict(alpha=a, facecolor=col))

    def on_zoom(self, event):
        """ Zoom back to previous xlim when event is in event.inaxes.
        """
        evkey = event.key
        axpp = self.axpp
        if not axpp.contains(event)[0] or evkey is None: return
        xzoom = self.xzoom
        if evkey.lower() == 'z' and len(xzoom) > 1:
            del xzoom[-1]
            axpp.set_xlim(xzoom[-1])
            print('Zoom back to: {:6.1f} {:6.1f} '.format(xzoom[-1][0], xzoom[-1][1]))
            if self.opts.upylim_on:
                for pp in self.pps:
                    del pp.ynorm[-1]
                    plt.setp(pp.lines[0], ydata=pp.ybase+pp.sacdh.data*pp.ynorm[-1])
                    plt.setp(pp.lines[1], ydata=pp.ybase+pp.sacdh.datamem*pp.ynorm[-1])
            axpp.figure.canvas.draw()

    def plotPicks(self):
        for pp in self.pps:
            pp.plotPicks()
        #pppara = self.opts.pppara

    def setLabels(self):
        """ Set axes labels and page label"""
        axpp = self.axpp
        axpp.set_yticks(self.ybases)
        axpp.set_yticklabels(self.yticks)
        axpp.set_ylabel('Trace Number')
        axpp.axhline(y=0, lw=2, color='r')
        if self.opts.boundlines_on:
            for yy in range(self.azylim[0], self.azylim[1]):
                axpp.axhline(y=yy+0.5, color='black')
        reltime = self.opts.reltime
        if reltime >= 0:
            axpp.set_xlabel('Time - T%d [s]' % reltime)
        else:
            axpp.set_xlabel('Time [s]')
        trans = transforms.blended_transform_factory(axpp.transAxes, axpp.transAxes)
        page = 'Page {0:d} of [{1:d},{2:d}]'.format(self.ipage, self.aipages[0], self.aipages[-1])
        self.pagelabel = axpp.text(1, -0.02, page, transform=trans, va='top', ha='right')

    def setLimits(self):
        """ Set axes limits    """
        axpp = self.axpp
        self.getXLimit()
        axpp.set_xlim(self.xzoom[0])
        axpp.set_ylim(self.azylim)
        # plot time zero lines and set axis limit
        axpp.axvline(x=0, color='k', ls=':')
        if not self.opts.xlimit is None:
            axpp.set_xlim(self.opts.xlimit)

    def labelSelection(self):
        """ Label selection status with transform (transAxes, transData).
        """
        axpp = self.axpp
        trans = transforms.blended_transform_factory(axpp.transAxes, axpp.transData)
        colsel = self.opts.pppara.colorwave
        coldel = self.opts.pppara.colorwavedel
        axpp.annotate('Selected', xy=(1.015, self.azylim[0]), xycoords=trans, xytext=(1.03, -0.17),
            size=10, va='top', color=colsel,
            bbox=dict(boxstyle="round,pad=.2", fc='w', ec=(1,.5,.5)),  
            arrowprops=dict(arrowstyle="->",connectionstyle="angle,angleA=0,angleB=-90,rad=20",color=colsel, lw=2),)
        axpp.annotate('Deselected', xy=(1.015, self.azylim[1]), xycoords=trans, xytext=(1.03, 0.17),
            size=10, va='bottom', color=coldel,
            bbox=dict(boxstyle="round,pad=.2", fc='w', ec=(1,.5,.5)),  
            arrowprops=dict(arrowstyle="->",connectionstyle="angle,angleA=0,angleB=-90,rad=20",color=coldel, lw=2),)

    def getXLimit(self):
        """ Get x limit (relative to reference time) """
        pps = self.pps
        b = [ pp.time[0]  - pp.sacdh.reftime for pp in pps ]
        e = [ pp.time[-1] - pp.sacdh.reftime for pp in pps ]
        #npts = [ len(pp.time) for pp in pps ]
        self.bmin = min(b) 
        self.bmax = max(b)
        self.emin = min(e) 
        self.emax = max(e)
        mm = self.bmin, self.emax
        xxlim = putil.axLimit(mm)
        self.xzoom = [xxlim,]

    def getYLimit(self):
        """ Get y limit """
        saclist = self.gsac.saclist
        #delta = saclist[0].delta
        data = np.array([ [min(sacdh.data), max(sacdh.data) ] for sacdh in saclist ])
        self.dmin = data[:,0].min()
        self.dmax = data[:,1].max() 

    def fron(self, event):
        self.bnfron.label.set_text('Wait...')
        self.axpp.get_figure().canvas.draw()

        self.replot(0)
        self.bnfron.label.set_text('Front')
        self.axpp.get_figure().canvas.draw()

    # zoom back to original screen size
    def zoba(self, event):
        self.bnzoba.label.set_text('Wait...')
        self.axpp.get_figure().canvas.draw()

        self.replot(self.ipage)
        
        self.bnzoba.label.set_text('Zoom\nBack')
        self.axpp.get_figure().canvas.draw()

    def prev(self, event):
        self.bnprev.label.set_text('Wait...')
        self.axpp.get_figure().canvas.draw()

        self.replot(self.ipage-1)
        self.bnprev.label.set_text('Prev')
        self.axpp.get_figure().canvas.draw()

    def next(self, event):
        self.bnnext.label.set_text('Wait...')
        self.axpp.get_figure().canvas.draw()

        self.replot(self.ipage+1)
        self.bnnext.label.set_text('Next')
        self.axpp.get_figure().canvas.draw()

    def last(self, event):
        self.bnlast.label.set_text('Wait...')
        self.axpp.get_figure().canvas.draw()

        self.replot(self.aipages[-1])
        self.bnlast.label.set_text('Last')
        self.axpp.get_figure().canvas.draw()

    # ---------------------------- SAVE HEADERS FILES ------------------------------- #

    """save headers only"""
    def shdo(self, event):
        sacpkl.saveData(self.gsac, self.opts)

    """save headers and override data with filtered data
       @lowFreq -> user6
       @highFreq -> user7
       @band -> kuser1
       @order -> kuser2, need to convert to integer form alphanumeric
    """
    def shfp(self, event):
        # write params to file
        for sacdh in self.gsac.saclist: 
            sacdh.user6 = self.opts.filterParameters['lowFreq']
            sacdh.user7 = self.opts.filterParameters['highFreq']
            sacdh.kuser1 = self.opts.filterParameters['band']
            sacdh.kuser2 = self.opts.filterParameters['order']
        if 'stkdh' in self.gsac.__dict__:
            self.gsac.stkdh.user6 = self.opts.filterParameters['lowFreq']
            self.gsac.stkdh.user7 = self.opts.filterParameters['highFreq']
            self.gsac.stkdh.kuser1 = self.opts.filterParameters['band']
            self.gsac.stkdh.kuser2 = self.opts.filterParameters['order']

        # save
        sacpkl.saveData(self.gsac, self.opts)

    """save headers and override"""
    def shod(self, event):
        shouldRun = messagebox.askokcancel("Will Override Files!","This will override the data in your files with the filtered data. \nAre you sure?")
        if shouldRun: 
            for sacdh in self.gsac.saclist: 
                sacdh.data = ftr.filtering_time_signal(sacdh.data, self.opts.delta, self.opts.filterParameters['lowFreq'], self.opts.filterParameters['highFreq'], self.opts.filterParameters['band'], self.opts.filterParameters['order'])
            if 'stkdh' in self.gsac.__dict__:
                self.gsac.stkdh.data = ftr.filtering_time_signal(self.gsac.stkdh.data, self.opts.delta, self.opts.filterParameters['lowFreq'], self.opts.filterParameters['highFreq'], self.opts.filterParameters['band'], self.opts.filterParameters['order'])
            sacpkl.saveData(self.gsac, self.opts)


    # ---------------------------- SAVE HEADERS FILES ------------------------------- #

    def quit(self, event):
        self.finish()
        self.disconnect(event.canvas)
        plt.close('all')

    def connect(self):
        self.axfron = self.axs['Fron']
        self.axprev = self.axs['Prev']
        self.axnext = self.axs['Next']
        self.axlast = self.axs['Last']
        self.axzoba = self.axs['Zoba']
        self.axshdo = self.axs['Shdo']
        self.axshfp = self.axs['Shfp']
        self.axshod = self.axs['Shod']
        self.axquit = self.axs['Quit']

        self.bnfron = Button(self.axfron, 'Front')
        self.bnprev = Button(self.axprev, 'Prev')
        self.bnnext = Button(self.axnext, 'Next')
        self.bnlast = Button(self.axlast, 'Last')
        self.bnzoba = Button(self.axzoba, 'Zoom \n Back')
        self.bnshdo = Button(self.axshdo, 'Save')
        self.bnshfp = Button(self.axshfp, 'Save \n Params')
        self.bnshod = Button(self.axshod, 'Save \n Override')
        self.bnquit = Button(self.axquit, 'Quit')

        self.cidfron = self.bnfron.on_clicked(self.fron)
        self.cidprev = self.bnprev.on_clicked(self.prev)
        self.cidnext = self.bnnext.on_clicked(self.next)
        self.cidlast = self.bnlast.on_clicked(self.last)
        self.cidzoba = self.bnzoba.on_clicked(self.zoba)
        self.cidshdo = self.bnshdo.on_clicked(self.shdo)
        self.cidshfp = self.bnshfp.on_clicked(self.shfp)
        self.cidshod = self.bnshod.on_clicked(self.shod)
        self.cidquit = self.bnquit.on_clicked(self.quit)

        self.cidpress = self.axpp.figure.canvas.mpl_connect('key_press_event', self.on_zoom)

    def disconnect(self, canvas):
        self.bnfron.disconnect(self.cidfron)
        self.bnprev.disconnect(self.cidprev)
        self.bnnext.disconnect(self.cidnext)
        self.bnlast.disconnect(self.cidlast)
        self.bnzoba.disconnect(self.cidzoba)
        self.bnshdo.disconnect(self.cidshdo)
        self.bnshfp.disconnect(self.cidshfp)
        self.bnshod.disconnect(self.cidshod)

        self.axfron.cla()
        self.axprev.cla()
        self.axnext.cla()
        self.axlast.cla()
        self.axzoba.cla()
        self.axshdo.cla()
        self.axshfp.cla()
        self.axshod.cla()
        self.axquit.cla()

        canvas.mpl_disconnect(self.cidpress)
        self.span.visible = False

    def finish(self):
        for pp in self.pps:    
            pp.disconnect()
        self.axpp.cla()

# ############################################################################### #
#                                                                                 #
#                               CLASS: PickPhaseMenu                              #
#                                                                                 #
# ############################################################################### #

# ############################################################################### #
#                                                                                 #
#                                    SortSeis                                     #
#                                                                                 #
# ############################################################################### #

def sortSeis(gsac, opts):
    'Sort seismograms by file indices, quality factors, or a given header'
    sortby = opts.sortby
    # determine increase/decrease order
    if sortby[-1] == '-':
        sortincrease = False
        sortby = sortby[:-1]
    else:
        sortincrease = True
    opts.labelqual = False
    # sort 
    if sortby == 'i':  # by file indices
        gsac.selist, gsac.delist = qualsort.seleSeis(gsac.saclist)
    elif sortby.isdigit() or sortby in opts.qheaders + ['all',]: # by quality factors
        opts.labelqual = True
        if sortby == '1' or sortby == 'ccc':
            opts.qweights = [1, 0, 0]
        elif sortby == '2' or sortby == 'snr':
            opts.qweights = [0, 1, 0]
        elif sortby == '3' or sortby == 'coh':
            opts.qweights = [0, 0, 1]
        gsac.selist, gsac.delist = qualsort.sortSeisQual(gsac.saclist, opts.qheaders, opts.qweights, opts.qfactors, sortincrease)
    else:  # by a given header
        gsac.selist, gsac.delist = qualsort.sortSeisHeader(gsac.saclist, sortby, sortincrease)
    return

# ############################################################################### #
#                                                                                 #
#                                    SortSeis                                     #
#                                                                                 #
# ############################################################################### #

def getAxes(opts):
    'Get axes for plotting'
    fig = plt.figure(figsize=(13, 11))
    plt.rcParams['legend.fontsize'] = 11
    if opts.labelqual:
        rectseis = [0.1, 0.06, 0.65, 0.85]
    else:
        rectseis = [0.1, 0.06, 0.75, 0.85]
    axpp = fig.add_axes(rectseis)
    axs = {}
    axs['Seis'] = axpp
    dx = 0.07
    x0 = rectseis[0] + rectseis[2] + 0.01

    xfron = x0 - dx*1
    xprev = x0 - dx*2
    xnext = x0 - dx*3
    xlast = x0 - dx*4
    xzoba = x0 - dx*5
    xshdo = x0 - dx*6
    xshfp = x0 - dx*7
    xshod = x0 - dx*8
    xquit = x0 - dx*9

    rectfron = [xfron, 0.93, 0.06, 0.04]
    rectprev = [xprev, 0.93, 0.06, 0.04]
    rectnext = [xnext, 0.93, 0.06, 0.04]
    rectlast = [xlast, 0.93, 0.06, 0.04]
    rectzoba = [xzoba, 0.93, 0.06, 0.04]
    rectshdo = [xshdo, 0.93, 0.06, 0.04]
    rectshfp = [xshfp, 0.93, 0.06, 0.04]
    rectshod = [xshod, 0.93, 0.06, 0.04]
    rectquit = [xquit, 0.93, 0.06, 0.04]

    axs['Fron'] = fig.add_axes(rectfron)
    axs['Prev'] = fig.add_axes(rectprev)
    axs['Next'] = fig.add_axes(rectnext)
    axs['Last'] = fig.add_axes(rectlast)
    axs['Zoba'] = fig.add_axes(rectzoba)
    axs['Shdo'] = fig.add_axes(rectshdo)
    axs['Shfp'] = fig.add_axes(rectshfp)
    axs['Shod'] = fig.add_axes(rectshod)
    axs['Quit'] = fig.add_axes(rectquit)

    return axs


            
def getDataOpts():
    'Get SAC Data and Options'
    opts, ifiles = getOptions()
    pppara = ttconfig.PPConfig()
    gsac = sacpkl.loadData(ifiles, opts, pppara)
    opts.pppara = pppara
    opts.qheaders = pppara.qheaders
    opts.qfactors = pppara.qfactors
    opts.qweights = pppara.qweights
    opts.hdrsel = pppara.hdrsel
    opts.pick_on = True
    gsac = pdata.prepData(gsac, opts)
    qualsort.initQual(gsac.saclist, opts.hdrsel, opts.qheaders)
    sortSeis(gsac, opts)
    return gsac, opts

def sacppk_standalone():
    gsac, opts = getDataOpts()
    axs = getAxes(opts)
    ppm = PickPhaseMenu(gsac, opts, axs)
    plt.show()


def main():
    gsac, opts = getDataOpts()
    axs = getAxes(opts)
    PickPhaseMenu(gsac, opts, axs)





if __name__ == "__main__":
    main()
    plt.show()
