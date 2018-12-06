#!/usr/bin/env python
#------------------------------------------------
# Filename: ttgui.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2018 Xiaoting Lou
#------------------------------------------------
"""
Python module for interactively measuring seismic wave travel times and quality control.

* Common pyqtgraph mouse interactions:
  ** http://www.pyqtgraph.org/documentation/mouse_interaction.html
  ** E.g., Right button drag:
     Dragging left/right scales horizontally; dragging up/down scales vertically.
  
* AIMBAT specific user interactions using mouse and keyboard:
  ** Key pressed event handler in pyqtgraph is redefined in prepplot.py
  ** Use mouse to change time window and press key 'w' to set <-- work on stack only
  ** Press key 't[0-9]' to set time picks like SAC PPK        <-- work on both stack and traces
  ** Mouse click on waveform to change trace selection status <-- work on trace only

* Trace plots:
  ** All traces are plotted in the same plotItem.
  ** Always plot time picks. Always plot time window as a fill.
  ** Normalization: can normalized within time window.
  
* Data 
  ** Define class SeisWaveItem in prepdata.py to hold sacDataHdrs and plotting itmes including
     waveform curve, time pick curves, and time window.
  ** Data is loaded to sacdh.datamem according to filter parameters in the headers.
     Original data in sacdh.data is not touched.


* A few components of Arnav Sankaran's Qt version was used.
  https://github.com/ASankaran/AIMBAT_Qt
  
:copyright:
    Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""


from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.parametertree import ParameterTree
import pyqtgraph as pg
import numpy as np
import sys, os

from pysmo.aimbat import ttconfig
from pysmo.aimbat import algiccs as iccs
from pysmo.aimbat import algmccc as mccc
from pysmo.aimbat import sacpickle as sacpkl
from pysmo.aimbat import prepdata  as pdata
from pysmo.aimbat import prepplot  as pplot



###################################################################################################
class mainGUI(object):
    def __init__(self, gsac, opts):
        # initialize Qt, once per application
        self.app = QtGui.QApplication(sys.argv)
        # A top-level widget to hold everything
        #self.window = QtGui.QWidget()
        self.window = pplot.KeyPressWidget()
        self.window.twhdrs = opts.pppara.twhdrs
        self.window.setWindowTitle('aimbat-qtpick')
        # Display the widget as a new window
        self.window.show() 
        self.layout = QtGui.QGridLayout(self.window)
        #
        self.gsac = gsac
        self.opts = opts
        self.initStack()
        self.setupData()
        self.setupPen()
        self.setupGUI()
        
    def setupData(self):
        'sort seismogram, set baselines and data norm after new stack'
        pdata.seisSort(self.gsac, self.opts)
        pdata.seisDataBaseline(self.gsac)
        pdata.sacDataNorm(self.gsac.stkdh, self.opts)
        stkdh = self.gsac.stkdh
        ystack = stkdh.data * stkdh.datnorm + stkdh.datbase
        self.yLimitStack =  pdata.axLimit([ystack.min(), ystack.max()], 0.1)
        
    def setupPen(self):
        pscode =  self.opts.pppara.pickstyles[0]
        if pscode == '-':
            pstyle = QtCore.Qt.SolidLine
        elif pscode == '--':
            pstyle = QtCore.Qt.DashLine
        elif pscode == ':':
            pstyle = QtCore.Qt.DotLine
        self.opts.pickpens = [pg.mkPen(c, width=2, style=pstyle) for c in self.opts.pickcolors]
        self.opts.cursorpen = pg.mkPen(width=1, style=QtCore.Qt.DashLine)
        self.opts.picknames = ['T'+str(i) for i in range(self.opts.pppara.npick)]
        self.opts.picknones = [None,] * self.opts.pppara.npick
        self.opts.oripen = pg.mkPen(width=2, style=QtCore.Qt.SolidLine, color=self.opts.colorwavedel[:3])
        self.opts.mempen = pg.mkPen(width=2, style=QtCore.Qt.SolidLine, color=self.opts.colorwave[:3])
        self.picklist = list(range(self.opts.pppara.npick))
        
    def setupGUI(self):
        resoRect = self.app.desktop().availableGeometry()
        self.window.resize(resoRect.width()*0.8, resoRect.height()*0.9)
        # stack and individual traces
        self.stackWidget = self.getStackGraphWidget(resoRect.width()*0.8, 180)
        self.traceWidget = self.getTraceGraphWidget(resoRect.width()*0.8, resoRect.height()-200 )
        self.useScrollArea = False
        if self.useScrollArea:
            self.stackScrollArea = QtGui.QScrollArea()
            self.traceScrollArea = QtGui.QScrollArea()
            self.stackScrollArea.setWidget(self.stackWidget)
            self.traceScrollArea.setWidget(self.traceWidget)
            self.addLayoutWidget(self.stackScrollArea, 0, 3, xSpan = 4, ySpan = 20)
            self.addLayoutWidget(self.traceScrollArea, 4, 3, xSpan = 14, ySpan = 20)
        else:
            self.addLayoutWidget(self.stackWidget, 0, 3, xSpan = 4, ySpan = 20)
            self.addLayoutWidget(self.traceWidget, 4, 3, xSpan = 14, ySpan = 20)
        self.addButtons()
        self.addCursorLine()
        self.addParaTree()
        xlabel = 'Time - T{:d} [s]'.format(self.opts.reltime)
        self.stackPlotItem.setLabel('bottom', text=xlabel)
        self.tracePlotItem.setLabel('bottom', text=xlabel)
        self.getXLimit()
        self.setXYRange()

    def addButtons(self):
        'Create and connect buttons'
        hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
        ipick = self.opts.mcpara.ipick
        wpick = self.opts.mcpara.wpick
        tccim = 'Align\nICCS {:s}-->{:s}'.format(hdrini.upper(), hdrmed.upper())
        tsync = 'Sync\n{:s} and Time Window'.format(hdrfin.upper())
        tccff = 'Refine\nICCS {:s}-->{:s}'.format(hdrfin.upper(), hdrfin.upper())
        tmccc = 'Finalize \nMCCC {:s}-->{:s}'.format(ipick.upper(), wpick.upper())
        ccimButton = QtGui.QPushButton(tccim)
        syncButton = QtGui.QPushButton(tsync)
        ccffButton = QtGui.QPushButton(tccff)
        mcccButton = QtGui.QPushButton(tmccc)
        saveButton = QtGui.QPushButton('Save')
        quitButton = QtGui.QPushButton('Quit')
        sac2Button = QtGui.QPushButton('Sac P2')
        tmapButton = QtGui.QPushButton('Map Delay Times')
        sortButton = QtGui.QPushButton('Sort\n by Name/Qual/Hdr')
        filtButton = QtGui.QPushButton('Filter\n on Stack/Traces')
        # connect:
        ccimButton.clicked.connect(self.ccimButtonClicked)
        syncButton.clicked.connect(self.syncButtonClicked)
        ccffButton.clicked.connect(self.ccffButtonClicked)
        mcccButton.clicked.connect(self.mcccButtonClicked)
        quitButton.clicked.connect(self.quitButtonClicked)
        saveButton.clicked.connect(self.saveButtonClicked)
        sortButton.clicked.connect(self.sortButtonClicked)
        sac2Button.clicked.connect(self.sac2ButtonClicked)
        filtButton.clicked.connect(self.filtButtonClicked)
        tmapButton.clicked.connect(self.tmapButtonClicked)
        # add to layout in two columns
        btns1 = [ccimButton, syncButton, ccffButton, mcccButton, sortButton]
        btns0 = [sac2Button, tmapButton, saveButton, quitButton, filtButton]
        for i in range(len(btns0)):
            self.addLayoutWidget(btns0[i], i, 0)
        for i in range(len(btns1)):
            self.addLayoutWidget(btns1[i], i, 1)
            
    def addParaTree(self):
        'Add parameter tree for filter and sort'
        self.ptreeItem = pplot.ParaTreeItem(self.opts.filterParameters)
        ptree = ParameterTree()
        ptree.setParameters(self.ptreeItem.paraTree, showTop=False)
        self.addLayoutWidget(ptree, 5, 0, -1, 2 )
        
    def addLayoutWidget(self, widget, xLoc, yLoc, xSpan = 1, ySpan = 1):
        self.layout.addWidget(widget, xLoc, yLoc, xSpan, ySpan)
        
    def getXLimit(self):
        hdrini = self.opts.qcpara.ichdrs[0]
        b = [ sacdh.b - sacdh.gethdr(hdrini) for sacdh in self.gsac.saclist]
        e = [ sacdh.e - sacdh.gethdr(hdrini) for sacdh in self.gsac.saclist]
        self.xLimit  = pdata.axLimit([min(b), max(e)],0.05)
        
    def setXYLimit(self):
        'Set X and Y axis limits that constrain the possible view ranges'
        xmin, xmax = self.xLimit
        symin, symax = self.yLimitStack
        tymin = -len(self.gsac.selist) 
        tymax =  len(self.gsac.delist) + 1
        self.tracePlotItem.setLimits(xMin=xmin, xMax=xmax, yMin=tymin, yMax=tymax)
        self.stackPlotItem.setLimits(xMin=xmin, xMax=xmax, yMin=symin, yMax=symax)
        
    def setXYRange(self):
        'Set X and Y axis ranges'
        self.setXYLimit()
        self.getXYRange()
        xrange0, xrange1 = self.xRange
        yrange0, yrange1 = self.yRange
        if self.useScrollArea:
            ssx = self.traceScrollArea.size().width()
            shx = self.traceScrollArea.sizeHint().width()
            ssy = self.traceScrollArea.size().height()
            shy = self.traceScrollArea.sizeHint().height()
            xrange1 = xrange0 + (xrange1-xrange0)*ssx/shx
            yrange0 = yrange1 - (yrange1-yrange0)*ssy/shy
        self.tracePlotItem.setYRange(yrange0, yrange1)
        self.tracePlotItem.setXRange(xrange0, xrange1)
        self.tracePlotItem.setYRange(yrange0, yrange1)
        
#        print('viewRange: ',self.tracePlotItem.viewRange())
        
    def getXYRange(self):
        'Get x and y ranges (relative to reference time)'
        self.xRange = self.opts.xlimit
        maxsel, maxdel = self.opts.maxnum
        nsel = min(maxsel, len(self.gsac.selist))
        ndel = min(maxdel, len(self.gsac.delist))
        self.yRange = -nsel, ndel+1
        
    def getStackGraphWidget(self, xSize, ySize):
        'Get graphics widget for stack'
        stackWidget = pg.GraphicsLayoutWidget()
        stackWidget.resize(xSize, ySize)
        stackWidget.ci.setSpacing(0)
        stackPlotItem = stackWidget.addPlot(title='Stack')
        stackPlotItem.titleLabel.font().setPointSize(20)
        stackPlotItem.addLegend(offset=[-1,1])
        stackPlotItem.setAutoVisible(y=True)
        stackWaveItem = pplot.SeisWaveItem(self.gsac.stkdh)
        self.addWaveStack(stackWaveItem, stackPlotItem, self.opts.colorwave)
        self.stackPlotItem = stackPlotItem
        self.stackWaveItem = stackWaveItem
        self.overrideAutoScaleButton(stackPlotItem)
        return stackWidget

    def getTraceGraphWidget(self, xSize, ySize):
        'Get graphics widget for traces'
        traceWidget = pg.GraphicsLayoutWidget()
        traceWidget.resize(xSize, ySize)
        traceWidget.ci.setSpacing(0)
        tracePlotItem = traceWidget.addPlot(title='Traces')
        tracePlotItem.titleLabel.font().setPointSize(20)
        tracePlotItem.setXLink(self.stackPlotItem)
        tracePlotItem.addLegend(offset=[-1,1])
        tracePlotItem.vb.sigXRangeChanged.connect(self.resetWaveLabelPos)
        # plot deselected and selected traces
        self.traceWaveItemList = []
        self.traceWaveformList = []
        clist  = [self.opts.colorwavedel,] * len(self.gsac.delist)
        clist += [self.opts.colorwave,   ] * len(self.gsac.selist)
        slist = self.gsac.delist + self.gsac.selist
        for isac, icol in zip (slist, clist):
            traceWaveItem = pplot.SeisWaveItem(isac)
            print('Plot trace ', isac.filename)
            self.addWaveTrace(traceWaveItem, tracePlotItem, icol)
            #connect waveCurve (plotDataItem) to mouse click events
            traceWaveItem.waveCurve.sigClicked.connect(self.waveClicked)
            self.traceWaveItemList.append(traceWaveItem)
            self.traceWaveformList.append(traceWaveItem.waveCurve)
        self.tracePlotItem = tracePlotItem
        self.overrideAutoScaleButton(tracePlotItem)
        return traceWidget

    def getLabelTrace(self, waveItem):
        'Get station label for each trace'
        sacdh = waveItem.sacdh
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
        waveItem.waveLabelText = slab

    def addLabelTrace(self, waveItem, plotItem, fillBrush):
        'Add station label for each trace'
        self.getLabelTrace(waveItem)
        sacdh = waveItem.sacdh
        waveLabel = pg.TextItem(waveItem.waveLabelText, color=fillBrush[:3], anchor=(0,0.5))
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        waveLabel.setFont(font)
        plotItem.addItem(waveLabel)
        yy = sacdh.datbase
        xx = sacdh.time[0] - sacdh.gethdr(self.opts.qcpara.ichdrs[0])
        ip = int(self.opts.qcpara.ichdrs[0][1])
        xx = sacdh.b - sacdh.thdrs[ip]
        waveLabel.setPos(xx, yy)
        waveItem.waveLabel = waveLabel
        
    def addWaveFill(self, waveItem, plotItem, fillBrush):
        'Add waveform fill for each trace'
        # plotDataItem:
        sacdh = waveItem.sacdh
        yb = sacdh.datbase
        xx = sacdh.time - sacdh.reftime
        yy = sacdh.datamem * sacdh.datnorm + sacdh.datbase
        waveItem.waveCurve = plotItem.plot(xx, yy, fillLevel=yb, fillBrush=fillBrush)
        # plotCurveItem set for mouse click to work
        waveItem.waveCurve.curve.setClickable(True)
    
    def addStackCurve(self, waveItem, plotItem):
        'Add original and filtered waveforms for a (stack) seismogram'
        sacdh = waveItem.sacdh
        xx = sacdh.time - sacdh.reftime
        yo = sacdh.data    * sacdh.datnorm + sacdh.datbase
        ym = sacdh.datamem * sacdh.datnorm + sacdh.datbase
        waveItem.waveCurveOri = plotItem.plot(xx, yo, name='Original', pen=self.opts.oripen)
        waveItem.waveCurveMem = plotItem.plot(xx, ym, name='Filtered', pen=self.opts.mempen)
        waveItem.waveCurveOri.curve.setClickable(False)
        waveItem.waveCurveMem.curve.setClickable(False)
        
    def addWaveStack(self, waveItem, plotItem, fillBrush):
        'Add waveform, time picks, and time window for stack'
        self.addWaveFill(waveItem, plotItem, fillBrush)
        self.addStackCurve(waveItem, plotItem)
        waveItem.waveCurve.curve.setClickable(False) # disable click
        self.addPick(waveItem, plotItem, self.opts.picknones)
        self.addWindStack(waveItem, plotItem)

    def addWaveTrace(self, waveItem, plotItem, fillBrush):
        'Add waveform, time picks, and time window for trace'
        self.addWaveFill(waveItem, plotItem, fillBrush)
        # plot pick legend only once
        if len(self.traceWaveItemList) == 0:
            pickNames = self.opts.picknames
        else:
            pickNames = self.opts.picknones
        self.addPick(waveItem, plotItem, pickNames)
        self.addWindTrace(waveItem, plotItem)
        self.addLabelTrace(waveItem, plotItem, fillBrush)

    def addWindStack(self, waveItem, plotItem):
        'Add an interactive time window for stack using LinearRegion for user to change'
        sacdh = waveItem.sacdh
        twin = tuple(np.array(sacdh.twindow) - sacdh.reftime)
        twinRegion = pg.LinearRegionItem(twin)
        twinRegion.setBrush(self.opts.colortwfill)
        twinRegion.setZValue(10)
        plotItem.addItem(twinRegion)
        # cannot update time window real time. Use button or key w.
        #twinRegion.sigRegionChanged.connect(self.twinRegionChanged)
        self.twinRegion = twinRegion
        waveItem.twinRegion = twinRegion
    
    def addWindTrace(self, waveItem, plotItem):
        'Add a fixed time winow for each trace'
        sacdh = waveItem.sacdh
        t0, t1 = tuple(np.array(sacdh.twindow) - sacdh.reftime)
        yy = [sacdh.datbase-0.5, sacdh.datbase+0.5]
        c0 = plotItem.plot([t0,t0], yy)
        c1 = plotItem.plot([t1,t1], yy)
        ff = pg.FillBetweenItem(c0, c1, brush=self.opts.colortwfill)
        plotItem.addItem(ff)
        waveItem.twinFill = ff
        waveItem.twinCurves = [c0, c1]

    def addPick(self, waveItem, plotItem, pickNames=[None,]*4):
        'Add time picks for a seismogram/waveItem'
        sacdh = waveItem.sacdh
        yp = [sacdh.datbase-0.5, sacdh.datbase+0.5]
        for i in range(self.opts.pppara.npick):
            th = sacdh.thdrs[i]
            xp = [th-sacdh.reftime, th-sacdh.reftime]
            tpick = plotItem.plot(xp, yp, pen=self.opts.pickpens[i], name=pickNames[i])
            waveItem.tpickCurves.append(tpick)
            
    def waveClicked(self, waveCurve):
        'Change seismogram selection status and color by mouse click'
        # find waveItem by waveform index in the list
        ind = self.traceWaveformList.index(waveCurve)
        sacdh = self.traceWaveItemList[ind].sacdh
        sacdh.selected = not sacdh.selected
        # for bytes!=str in py3
        if sacdh.selected:
            sacdh.sethdr(self.opts.hdrsel, 'True')
            brush = self.opts.colorwave
            print('Seismogram selected: {:s} '.format(sacdh.filename))
        else:
            sacdh.sethdr(self.opts.hdrsel, 'False')
            brush = self.opts.colorwavedel
            print('Seismogram deselected: {:s} '.format(sacdh.filename))
        waveCurve.curve.setBrush(brush)
        self.traceWaveItemList[ind].waveLabel.setColor(brush[:3])

    def addCursorLine(self):
        'Add an active vertical line for time pick'
        vCursorLine = pg.InfiniteLine(angle=90, movable=False, pen=self.opts.cursorpen)
        self.stackPlotItem.addItem(vCursorLine, ignoreBounds=True)
        #pg.SignalProxy(self.stackPlotItem.scene().sigMouseMoved, rateLimit=60, slot=mouseMoved)
        self.stackPlotItem.scene().sigMouseMoved.connect(self.stackMouseMoved)
        self.stackPlotItem.vCursorLine = vCursorLine
        # trace:
        vCursorLine = pg.InfiniteLine(angle=90, movable=False, pen=self.opts.cursorpen)
        self.tracePlotItem.addItem(vCursorLine, ignoreBounds=True)
        self.tracePlotItem.scene().sigMouseMoved.connect(self.traceMouseMoved)
        self.tracePlotItem.vCursorLine = vCursorLine
        # mouse position label:
        self.stackPlotItem.mouseLabel = pg.TextItem()
        self.stackPlotItem.addItem(self.stackPlotItem.mouseLabel)
        
    def updateMouseLabel(self):
        yt = self.tracePlotItem.viewRange()[1][1]
        xx = self.window.mousePoint[0]
        tt = 'T={:.1f}'.format(xx)
        self.stackPlotItem.mouseLabel.setPos(xx, yt)
        self.stackPlotItem.mouseLabel.setText(tt)

    def mouseMoved(self, event, plotItem):
        'Mouse moved events. Set mouse position and find waveItem by ybase'
        mousePoint = plotItem.vb.mapSceneToView(event)
        mpx, mpy = [mousePoint.x(), mousePoint.y()]
        #if plotItem.sceneBoundingRect().contains(event):
        #update cursor line for both stack and traces
        self.stackPlotItem.vCursorLine.setPos(mpx)
        self.tracePlotItem.vCursorLine.setPos(mpx)
        if plotItem is self.stackPlotItem:
            self.window.mouseOnStack = True
            self.window.waveItem = self.stackWaveItem
        else:
            self.window.mouseOnStack = False
            ind = -round(mpy) + len(self.gsac.delist)
            if ind >= 0 and ind < len(self.traceWaveItemList):
                self.window.waveItem = self.traceWaveItemList[ind]
        self.window.mousePoint = [mpx, mpy]
        self.updateMouseLabel()

    def stackMouseMoved(self, event):
        self.mouseMoved(event, self.stackPlotItem)
        
    def traceMouseMoved(self, event):
        self.mouseMoved(event, self.tracePlotItem)
        
    def getWindStack(self, hdr):
        """ Get time window twcorr (relative to hdr) from array stack, which is from last run. 
        """
        tw0, tw1 = self.gsac.stkdh.twindow
        t0 = self.gsac.stkdh.gethdr(hdr)
        if t0 == -12345.:
            print(('Header {0:s} not defined'.format(hdr)))
            return
        self.opts.ccpara.twcorr = [tw0-t0, tw1-t0]

    def getPickStack(self):
        """ Get time picks of stack
        """
        hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
        self.tini = self.gsac.stkdh.gethdr(hdrini)
        self.tmed = self.gsac.stkdh.gethdr(hdrmed)
        self.tfin = self.gsac.stkdh.gethdr(hdrfin)

    def syncPickTrace(self):
        """ 
        Sync final time pick hdrfin from array stack to all traces. 
        """
        self.getPickStack()
        hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
        tshift = self.tfin - self.tmed
        ifin = int(hdrfin[1])
        for sacdh in self.gsac.saclist:
            tfin = sacdh.gethdr(hdrmed) + tshift
            sacdh.sethdr(hdrfin, tfin)
            sacdh.thdrs[ifin] = tfin

    def syncWindTrace(self):
        """ 
        Sync time window relative to hdrfin from array stack to all traces. 
        Times saved to twhdrs are always absolute.
        """
        wh0, wh1 = self.opts.qcpara.twhdrs
        hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
        self.getWindStack(hdrfin)
        twfin = self.opts.ccpara.twcorr
        for sacdh in self.gsac.saclist:
            tfin = sacdh.gethdr(hdrfin)
            th0 = tfin + twfin[0]
            th1 = tfin + twfin[1]
            sacdh.sethdr(wh0, th0)
            sacdh.sethdr(wh1, th1)
            sacdh.twindow = [th0, th1]
            
    def resetWind(self, waveItemList):
        'Reset time window with new twindow, reftime, and/or datbases'
        wh0, wh1 = self.opts.qcpara.twhdrs
        for waveItem in waveItemList:
            yy = [waveItem.sacdh.datbase-0.5, waveItem.sacdh.datbase+0.5]
            th0 = waveItem.sacdh.twindow[0] - waveItem.sacdh.reftime
            th1 = waveItem.sacdh.twindow[1] - waveItem.sacdh.reftime
            waveItem.twinCurves[0].setData([th0,th0], yy)
            waveItem.twinCurves[1].setData([th1,th1], yy)
    
    def resetWindStack(self):
        'Reset time window (LinearRegion)for stack'
        wh0, wh1 = self.opts.qcpara.twhdrs
        waveItem = self.stackWaveItem
        th0 = waveItem.sacdh.twindow[0] - waveItem.sacdh.reftime
        th1 = waveItem.sacdh.twindow[1] - waveItem.sacdh.reftime
        waveItem.twinRegion.setRegion([th0, th1])

    def resetPick(self, waveItemList, ipicklist=[0,1,2,3]):
        'Reset time picks with new tpicks, reftime, and/or datbases'
        for waveItem in waveItemList:
            yy = [waveItem.sacdh.datbase-0.5, waveItem.sacdh.datbase+0.5]
            for ipick in ipicklist:
                tpick = waveItem.sacdh.thdrs[ipick] - waveItem.sacdh.reftime
                waveItem.tpickCurves[ipick].setData([tpick, tpick], yy)

    def resetWave(self, waveItemList):
        'Reset waveCurve with new reftime and/or datbases'
        wh0, wh1 = self.opts.qcpara.twhdrs
        for waveItem in waveItemList:
            sacdh = waveItem.sacdh
            xx = sacdh.time - sacdh.reftime
            yy = sacdh.datamem * sacdh.datnorm + sacdh.datbase
            waveItem.waveCurve.setData(xx, yy)
            waveItem.waveCurve.setFillLevel(sacdh.datbase)
            if sacdh.selected:
                fbrush = self.opts.colorwave
            else:
                fbrush = self.opts.colorwavedel
            waveItem.waveCurve.setFillBrush(fbrush)
            if waveItem is not self.stackWaveItem:
                waveItem.waveLabel.setColor(fbrush[:3])
                xw = sacdh.b - sacdh.gethdr(self.opts.qcpara.ichdrs[0])
                yw = sacdh.datbase
                waveItem.waveLabel.setPos(xw, yw)
                #update text of trace label as well for changing in qfactors
                self.getLabelTrace(waveItem)
                waveItem.waveLabel.setText(waveItem.waveLabelText)
    
    def resetWaveLabelPos(self, event):
        for waveItem in self.traceWaveItemList:
            yw = waveItem.waveLabel.pos()[1]
            xw = self.tracePlotItem.viewRange()[0][0]
            waveItem.waveLabel.setPos(xw, yw)
            
    def resetAllPlots(self):
        print('--> Reset all plots')
        self.setupData()
        self.resetTraceWaveItemList()
        self.resetStackPlot()
        self.resetTracePlot()
        xlabel = 'Time - T{:d} [s]'.format(self.opts.reltime)
        self.stackPlotItem.setLabel('bottom', text=xlabel)
        self.tracePlotItem.setLabel('bottom', text=xlabel)
        
    def resetStackCurve(self, waveItem):
        'Reset filtered waveforms for a (stack) seismogram'
        sacdh = waveItem.sacdh
        xx = sacdh.time - sacdh.reftime
        yo = sacdh.data    * sacdh.datnorm + sacdh.datbase
        ym = sacdh.datamem * sacdh.datnorm + sacdh.datbase
        waveItem.waveCurveMem.setData(xx, ym)
        waveItem.waveCurveOri.setData(xx, yo)
        
    def resetStackPlot(self):
        self.resetStackCurve(self.stackWaveItem)
        self.resetWave([self.stackWaveItem])
        self.resetPick([self.stackWaveItem],   self.picklist)
        self.resetWindStack()
        
    def resetTracePlot(self):
        self.resetWave(self.traceWaveItemList)
        self.resetWind(self.traceWaveItemList)
        self.resetPick(self.traceWaveItemList, self.picklist)

    def initStack(self):
        'Create stack by ICCS if not existing'
        gsac = self.gsac
        opts = self.opts
        if not hasattr(gsac, 'stkdh'):
            if opts.filemode == 'sac' and os.path.isfile(opts.fstack):
                gsac.stkdh = pdata.prepStack(opts)
            else:
                hdrini, hdrmed, hdrfin = opts.qcpara.ichdrs
                # set cross-correlation input and output headers
                opts.ccpara.cchdrs = [hdrini, hdrmed]
                opts.ccpara.twcorr = opts.twcorr
                # check data coverage
                opts.ipick = hdrini
                iccs.checkCoverage(gsac, opts) 
                gsac.selist = gsac.saclist
                self.ccStack()

    def ccStack(self):
        """ 
        Call iccs.ccWeightStack which uses opts.ccpara for cross-correlation parameters.
        Change reference time pick to the input pick before ICCS and to the output pick afterwards.
        """
        wpick = self.opts.ccpara.cchdrs[1]
        wpint = int(wpick[1]) # integer number of the time pick header.
        stkdh, stkdata, quas = iccs.ccWeightStack(self.gsac.selist, self.opts)
        stkdh.selected = True
        stkdh.sethdr(self.opts.qcpara.hdrsel, 'True')
        stkdh.reftime = stkdh.gethdr(wpick)
        if self.opts.reltime != wpint:
            out = '\n--> change opts.reltime from %i to %i'
            print(out % (self.opts.reltime, wpint))
        self.opts.reltime = wpint
        pdata.seisTimeRefr(self.gsac.saclist, self.opts) # update reftime for all traces
        self.gsac.stkdh = stkdh
        if hasattr(self, 'stackWaveItem'):
            self.stackWaveItem.sacdh = stkdh
        
    def ccimButtonClicked(self):
        """ 
        Run iccs with time window from array stack. Time picks: hdrini, hdrmed.
        Align: T0 --> T1
        """
        hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
        self.opts.ccpara.cchdrs = hdrini, hdrmed

        self.getWindStack(self.opts.ccpara.cchdrs[0])
        self.getPickStack()
        self.ccStack()
        self.resetAllPlots()

    def syncButtonClicked(self):
        """ 
        Sync final time pick and time window from array stack to each trace and update current page.
        """
        hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
        ifin = int(hdrfin[1])
        wh0, wh1 = self.opts.qcpara.twhdrs
        if self.gsac.stkdh.gethdr(hdrfin) == -12345.:
            print('*** hfinal %s is not defined. Pick at array stack first! ***' % hdrfin)
            return
        self.syncPickTrace()
        self.syncWindTrace()
        self.resetWind(self.traceWaveItemList)
        self.resetPick(self.traceWaveItemList, [ifin,])
        print('--> Sync final time picks and time window... You can now click Refine button to refine final picks.')

    def ccffButtonClicked(self):
        """ 
        Run iccs with time window from array stack. Time picks: hdrfin, hdrfin.
        Refine: T2 --> T2
        """
        hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
        if self.gsac.stkdh.gethdr(hdrfin) == -12345.:
            print('*** hfinal %s is not defined. Sync first! ***' % hdrfin)
            return
        self.opts.ccpara.cchdrs = hdrfin, hdrfin
        self.getWindStack(self.opts.ccpara.cchdrs[0])
        self.getPickStack()
        self.ccStack()
        self.gsac.stkdh.sethdr(hdrini, self.tini)
        self.gsac.stkdh.sethdr(hdrmed, self.tmed)
        self.resetAllPlots()

    def mcccButtonClicked(self):
        """
        Run MCCC with time window from array stack. Time picks: ipick, wpick.
        MCCC: T2 --> T3 
        No new stack is created.
        """
        self.getWindStack(self.opts.mcpara.ipick)
        taperwindow = sacpkl.taperWindow(self.opts.ccpara.twcorr, self.opts.mcpara.taperwidth)
        self.opts.mcpara.timewindow = self.opts.ccpara.twcorr
        self.opts.mcpara.taperwindow = taperwindow
        evline, mcname = mccc.eventListName(self.gsac.event, self.opts.mcpara.phase)
        self.opts.mcpara.evline = evline
        self.opts.mcpara.mcname = mcname
        self.opts.mcpara.kevnm = self.gsac.kevnm

        solution, solist_LonLat, delay_times = mccc.mccc(self.gsac, self.opts.mcpara)
        self.gsac.solist_LonLat = solist_LonLat
        self.gsac.delay_times = delay_times
        wpint = int(self.opts.mcpara.wpick[1])
        if self.opts.reltime != wpint:
            out = '\n--> change opts.reltime from %i to %i'
            print(out % (self.opts.reltime, wpint))
        self.opts.reltime = wpint
        pdata.seisTimeRefr(self.gsac.saclist, self.opts) # update reftime for all traces
        self.resetAllPlots()
        

    def saveButtonClicked(self):
        'Save SAC headers'
        sacpkl.saveData(self.gsac, self.opts)
        

    def quitButtonClicked(self):
        self.app.closeAllWindows()

    def filtButtonClicked(self):
        print('Filter with parameters and change sac header')
        if self.ptreeItem.onStack:
            saclist = [self.gsac.stkdh,]
        else:
            saclist = self.gsac.saclist
        for sacdh in saclist:
            pdata.setFilterPara(sacdh, self.opts.pppara, self.opts.filterParameters)
        if self.opts.filterParameters['apply']:
            pdata.seisApplyFilter(saclist, self.opts.filterParameters)
        else:
            pdata.seisUnApplyFilter(saclist)
        if self.ptreeItem.onStack:
            self.resetStackPlot()
        else:
            self.resetTracePlot()
        
    def sortButtonClicked(self):
        self.opts.sortby = self.ptreeItem.sortby
        print('Sort seismograms by: ',self.opts.sortby)
        self.setupData()
        self.resetTracePlot()

    def resetTraceWaveItemList(self):
        'Reset traceWaveItemList after sorting'
        newlist = self.gsac.delist + self.gsac.selist
        oldlist = [ twi.sacdh  for twi in self.traceWaveItemList]
        inds = [ oldlist.index(sacdh)  for sacdh in newlist ]
        self.traceWaveItemList = [ self.traceWaveItemList[i]  for i in inds]
        self.traceWaveformList = [ twi.waveCurve  for twi in self.traceWaveItemList ]
            
    def sac2ButtonClicked(self):
        resoRect = self.app.desktop().availableGeometry()
        resoRect.setWidth(resoRect.width()*0.5)
        resoRect.setHeight(resoRect.height()*0.7)
        hdrList = list(self.opts.qcpara.ichdrs) + [self.opts.mcpara.wpick]
        selTraceWaveItemList = [ item  for item in self.traceWaveItemList  if item.sacdh.selected]
        self.sacp2Window = sacp2GUI(selTraceWaveItemList, hdrList, resoRect)


    def tmapButtonClicked(self):
        self.usegmt = False
        if self.usegmt:
            from stationmapping import StationMapper
            mapper = StationMapper(self.gsac)
            mapper.start()
        else:
            import plotutils as putil
            lalo = np.array(self.gsac.solist_LonLat)
            lo = lalo[:,0]
            la = lalo[:,1]
            dt = np.array(self.gsac.delay_times)
            if self.opts.phase == 'P':
                self.opts.vminmax = [-1, 1]
            else:
                self.opts.vminmax = [-3, 3]
            self.opts.savefig = True
            putil.plotDelay(lo, la, dt, self.opts)
        

    def overrideAutoScaleButton(self, plot):
        plot.autoBtn.clicked.disconnect()
        plot.autoBtn.clicked.connect(lambda: self.setXYRange())

    def autoScalePlot(self):
        self.setXYRange()


###################################################################################################
class sacp2GUI(object):
    """
    Plot each seismogram in the given waveItemList in SAC P2 overlay style.
    Relative time picks are given in hdrList.
    """
    def __init__(self, waveItemList, hdrList, resoRect):
        self.hdrList = hdrList
        sacp2Window = QtGui.QWidget()
        sacp2Window.setWindowTitle('SAC P2')
        sacp2Window.show()
        sacp2Layout = QtGui.QGridLayout(sacp2Window)
        sacp2Widget = pg.GraphicsLayoutWidget()
        sacp2Window.resize(resoRect.width(), resoRect.height())
        # create plotItems for each header in hdrList
        self.plotItemList = []
        zeropen = pg.mkPen(width=1, style=QtCore.Qt.DashLine)
        for i in range(len(hdrList)):
            plotItem = sacp2Widget.addPlot()
            self.plotItemList.append(plotItem)
            sacp2Widget.nextRow()
#            plotItem.hideAxis('left')
            xlabel = 'Time - {:s} [s]'.format(self.hdrList[i].upper())
            plotItem.setLabel('bottom', text=xlabel)
            vline = pg.InfiniteLine(angle=90, movable=False, pen=zeropen)
            plotItem.addItem(vline, ignorebounds=True)
        # link x axis
        for i in range(1, len(hdrList)):
            self.plotItemList[i].setXLink(self.plotItemList[0])
        # plot 
        for waveItem in waveItemList:
            self.addWave(waveItem)
        sacp2Layout.addWidget(sacp2Widget, 0, 0, 1, 1)
        self.sacp2Window = sacp2Window
        self.sacp2Widget = sacp2Widget
        
    def addWave(self, waveItem):
        'Add waveform relative to time picks'
        sacdh = waveItem.sacdh
        yy = sacdh.datamem
        for i in range(len(self.plotItemList)):
            xx = sacdh.time - sacdh.gethdr(self.hdrList[i])
            waveItem.waveCurve = self.plotItemList[i].plot(xx, yy)
            waveItem.waveCurve.curve.setClickable(True)
            waveItem.waveCurve.curve.opts['name'] = sacdh.filename
            waveItem.waveCurve.curve.sigClicked.connect(self.mouseClickEvents)
            
    def mouseClickEvents(self, event):
        print('Clicked seismogram: ', event.name())

###################################################################################################




def getOptions():
    """ Parse arguments and options. """
    parser = ttconfig.getParser()
    maxsel = 37
    maxdel = 3
    maxnum = maxsel, maxdel
    twcorr = -15, 15
    sortby = '1'
    fill = 1
    reltime = 0
    xlimit = -40, 40
    parser.set_defaults(xlimit=xlimit)
    parser.set_defaults(twcorr=twcorr)
    parser.set_defaults(reltime=reltime)
    parser.set_defaults(maxnum=maxnum)
    parser.set_defaults(sortby=sortby)
    parser.set_defaults(fill=fill)
    parser.add_option('-b', '--boundlines', action="store_true", dest='boundlines_on',
        help='Plot bounding lines to separate seismograms.')
    parser.add_option('-n', '--netsta', action="store_true", dest='nlab_on',
        help='Label seismogram by net.sta code instead of SAC file name.')
    parser.add_option('-m', '--maxnum',  dest='maxnum', type='int', nargs=2,
        help='Maximum number of selected and deleted seismograms to plot. Defaults: {0:d} and {1:d}.'.format(maxsel, maxdel))
    parser.add_option('-p', '--phase',  dest='phase', type='str',
        help='Seismic phase name: P/S .')
    parser.add_option('-s', '--sortby', type='str', dest='sortby',
        help='Sort seismograms by i (file indices), or 0/1/2/3 (quality factor all/ccc/snr/coh), or t (time pick diff), or a given header (az/baz/dist..). Append - for decrease order, otherwise increase. Default is {:s}.'.format(sortby))
    parser.add_option('-t', '--twcorr', dest='twcorr', type='float', nargs=2,
        help='Time window for cross-correlation. Default is [{:.1f}, {:.1f}] s'.format(twcorr[0],twcorr[1]))
    parser.add_option('-g', '--savefig', action="store_true", dest='savefig',
        help='Save figure instead of showing.')
    opts, files = parser.parse_args(sys.argv[1:])
    if len(files) == 0:
        print(parser.usage)
        sys.exit()
    return opts, files

def getDataOpts():
    'Get SAC Data and Options'
    opts, ifiles = getOptions()
    gsac, opts = pdata.paraDataOpts(opts, ifiles)
    # more options:
    opts.upylim_on = False
    opts.twin_on = True
    opts.sort_on = True
    opts.pick_on = True
    opts.zero_on = False
    opts.nlab_on = True
    opts.ynormtwin_on = True
    opts.labelqual = True
    # prep data:
    pplot.convertColors(opts, opts.pppara)
    gsac = pdata.prepData(gsac, opts)
    return gsac, opts

def main():
    gsac, opts = getDataOpts()
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')
    gui = mainGUI(gsac, opts)
    ### Start Qt event loop unless running in interactive mode or using pyside.
    if sys.flags.interactive != 1 or not hasattr(QtCore, 'PYQT_VERSION'):
        #pg.QtGui.QApplication.exec_()
        gui.app.exec_()


if __name__ == '__main__':
#    main()
    gsac, opts = getDataOpts()
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')
    gui = mainGUI(gsac, opts)
    ### Start Qt event loop unless running in interactive mode or using pyside.
    if sys.flags.interactive != 1 or not hasattr(QtCore, 'PYQT_VERSION'):
        #pg.QtGui.QApplication.exec_()
        gui.app.exec_()