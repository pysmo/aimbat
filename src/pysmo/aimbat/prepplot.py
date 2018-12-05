#!/usr/bin/env python
#------------------------------------------------
# Filename: prepplot.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2018 Xiaoting Lou
#------------------------------------------------
"""
Python module for preparing plots on Qt GUI.

:copyright:
    Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""


from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.parametertree import Parameter
import pyqtgraph.parametertree.parameterTypes as pTypes


class SeisWaveItem(object):
    """ 
    An seismogram item including sacdh and its plotting items
    """
    def __init__(self, sacdh):
        self.sacdh = sacdh
        self.waveCurve = None
        self.twinRegion = None
        self.tpickCurves = []
        
    def getXY(self):
        sacdh = self.sacdh
        self.x = sacdh.time - sacdh.reftime
        self.y = sacdh.datamem * sacdh.datnorm + sacdh.datbase

###################################################################################################

class KeyPressWidget(QtGui.QWidget):
    """
    Redefine key press event handler
    """
    def __init__(self):
        super(KeyPressWidget, self).__init__()
        self.show()
        self.waveItem = None
        self.twhdrs = [None, None]
        self.twvals = [None, None]
        self.evkeys = [-1, -1]
        self.mouseOnStack = False
        self.mousePoint = [None, None]
        
    def keyPressEvent(self, event):
        # keys are ints: W-->87 T-->84  0-->48 9-->57
        evkey = event.key()
        evkey0 = self.evkeys[1]
        self.evkeys = [evkey0, evkey]
        ipick = evkey - QtCore.Qt.Key_0
        waveItem = self.waveItem
        # set time window on stack only.
        if evkey == QtCore.Qt.Key_W and self.mouseOnStack:
            setTimeWindow(waveItem.sacdh, self.twhdrs, waveItem.twinRegion.getRegion())
        # set time pick at current mouse position on either stack or trace.
        elif evkey0 == QtCore.Qt.Key_T and ipick >= 0 and ipick < len(waveItem.tpickCurves):
            rpick = self.mousePoint[0]
            setTimePick(waveItem.sacdh, ipick, rpick)
            # update timepick curves
            xp = [rpick, rpick]
            yp = [waveItem.sacdh.datbase-0.5, waveItem.sacdh.datbase+0.5]
            waveItem.tpickCurves[ipick].setData(xp, yp)
        elif evkey == QtCore.Qt.Key_Q:
            print('Quit application. Bye')
            QtGui.QApplication.instance().closeAllWindows()
        event.accept()

def setTimeWindow(sacdh, twhdrs, twvals):
    'Set time window'
    twh0, twh1 = twhdrs
    twv0, twv1 = twvals
    twa0, twa1 = twv0+sacdh.reftime, twv1+sacdh.reftime
    sacdh.sethdr(twh0, twa0)
    sacdh.sethdr(twh1, twa1)
    sacdh.twindow = [twa0, twa1]
    out = 'File {:s}: set time window to {:s} and {:s}: {:6.1f} to {:6.1f} s, abs {:6.1f} to {:6.1f} s'
    print((out.format(sacdh.filename, twh0, twh1, twv0, twv1,twa0, twa1)))
    return

def setTimePick(sacdh, ipick, rpick):
    'Set time pick '
    # ipick is index, rpick relative time
    apick = rpick + sacdh.reftime
    sacdh.thdrs[ipick] = apick
    out = 'File {:s}: set time pick t{:d} = {:6.1f} s, absolute = {:6.1f} s. '
    print(out.format(sacdh.filename, ipick, rpick, apick))
    return

###################################################################################################

class RadioParameter(pTypes.GroupParameter):
    """
    This parameter generates four exclusive child parameters, like radio buttons.
    Set an unique value (sortby) for sorting seismograms in prepdata.seisSort().
    Sort by:
        'i':        File indices
        '0/1/2/3':  Quality factors All/CCC/SNR/COH
        Header:     GCARC, DIST, AZ, BAZ, STLA, STLO, B, E, NPTS
        HeaderDiff: T1-T0, T2-T0...
    Default to sort in increase order. Append '-' to sort in decrease order.
    """
    def __init__(self, **opts):
        opts['type'] = 'bool'
        opts['value'] = True
        pTypes.GroupParameter.__init__(self, **opts)
        
        dicta = {'name': 'Filename', 'type': 'list', 'values': 
            {"N/A": 0, "Filename": 1}, 'value': 0}
        dictb = {'name': 'Quality', 'type': 'list', 'values': 
            {"N/A": 0, "CCC": 1, "SNR": 2, "COH": 3, "All":4}, 'value': 1}
        dictc = {'name': 'Header', 'type': 'list', 'values':
            {"N/A": 0, "GCARC": 1, "DIST": 2, "AZ": 3, "BAZ": 4, "STLA": 5, "STLO": 6, "B": 7, "E": 8, "NPTS": 9
            }, 'value': 0}
        dictf = {'name': 'HeaderDiff', 'type': 'list', 'values':
            {"N/A": 0, "T1-T0": 10, "T2-T0": 20, "T3-T0": 30, "T2-T1": 21, "T3-T1": 31,"T3-T2": 32,  
            }, 'value': 0}
        dictd = {'name': 'Sort_Increase', 'type': 'bool', 'value': True, 'tip': "This is a checkbox"}
        dicte = {'name': 'Confirm_Sort_Parameters', 'type': 'action'}
        dictbChild = {'name': 'QualityWeights', 'type': 'group', 'children': [
            {'name': 'cccWeight', 'type': 'float', 'value': 1},
                {'name': 'snrWeight', 'type': 'float', 'value': 0},
                {'name': 'cohWeight', 'type': 'float', 'value': 0},
            ]}
        self.addChild(dicta)
        self.addChild(dictb)
        self.addChild(dictc)
        self.addChild(dictf)
        self.addChild(dictd)
        self.addChild(dicte)
        self.a = self.param('Filename')
        self.b = self.param('Quality')
#        self.b.addChild(dictbChild)
        self.c = self.param('Header')
        self.f = self.param('HeaderDiff')
        self.d = self.param('Sort_Increase')
        self.a.sigValueChanged.connect(self.aChanged)
        self.b.sigValueChanged.connect(self.bChanged)
        self.c.sigValueChanged.connect(self.cChanged)
        self.f.sigValueChanged.connect(self.fChanged)
        self.d.sigValueChanged.connect(self.dChanged)
        self.hdict = dictc['values']
        self.sortby = 1
        self.increase = True

    def aChanged(self):
        if self.a.value() != 0:
            self.b.setValue(0)
            self.c.setValue(0)
            self.f.setValue(0)
            self.sortby = 'i'

    def bChanged(self):
        bv = self.b.value()
        if bv != 0:
            self.a.setValue(0)
            self.c.setValue(0)
            self.f.setValue(0)
            if bv == 4:
                self.sortby = 0
            else:
                self.sortby = bv

    def cChanged(self):
        cv = self.c.value()
        if cv != 0:
            self.b.setValue(0)
            self.a.setValue(0)
            self.f.setValue(0)
            self.sortby = list(self.hdict.keys())[list(self.hdict.values()).index(cv)]
                
    def dChanged(self):
        self.increase = self.d.value()

    def fChanged(self):
        fv = self.f.value()
        if fv != 0:
            self.b.setValue(0)
            self.a.setValue(0)
            self.c.setValue(0)
            self.sortby = 't'+str(fv)

class ParaTreeItem(object):
    """
    Parameter tree including sort and filter parameters.
    Tree changed event only updates sort (sortby, increase) and filter para dict,
      but does not trigger any sort and filter actions.
    """
    # Value changing in the tree is not finalized until the action confirm button is clicked.
    def __init__(self, dictFiltPara=None):
        self.dictFiltPara = dictFiltPara
        self.bandDict = {"bandpass": 0, "lowpass": 1, "highpass": 2}
        self.filtDict = {'name': 'Filter', 'type': 'group', 'children': [
            {'name': 'band', 'type': 'list', 'values': self.bandDict, 'value': 0},
            {'name': 'order', 'type': 'int', 'value': 2},
            {'name': 'lowFreq', 'type': 'float', 'value': 0.02, 'step': 0.1, 'suffix': ' Hz'},
            {'name': 'highFreq', 'type': 'float', 'value': 2.0, 'step': 0.1, 'suffix': ' Hz'},
            {'name': 'reversepass', 'type': 'bool', 'value': False, 'tip': "This is a checkbox"},
            {'name': 'seis', 'type': 'list', 'values': {"Stack": 0, "Trace": 1}, 'value': 0},
            {'name': 'apply', 'type': 'bool', 'value': False, 'tip': "This is a checkbox"},
            {'name': 'Confirm_Filt_Parameters', 'type': 'action'},
            ]}
        self.filtKeys = ['lowFreq', 'highFreq', 'order', 'apply', 'reversepass']
        self.params = [
            RadioParameter(name='Sort'),
            self.filtDict,
            ]
        ## Create tree of Parameter objects
        self.paraTree = Parameter.create(name='params', type='group', children=self.params)
        self.paraTree.sigTreeStateChanged.connect(self.treeChanged)
        self.paraSort = self.paraTree.children()[0]
        self.paraFilt = self.paraTree.children()[1]
        self.onStack = True
        # get parameters for action:
        self.getSortPara()
        self.setFiltTree()
        self.getFiltPara()
            
    def setFiltTree(self):
        'Set initial filter parameter in the tree'
        #if self.dictFiltPara is not None:
        if self.dictFiltPara is None:
            self.dictFiltPara = {}
        else:
            for key in self.filtKeys:
                if key in self.dictFiltPara:
                    val = self.dictFiltPara[key]
                    self.paraFilt.param(key).setValue(val)
            # name band/low/high pass to integer 0/1/2
            if 'band' in self.dictFiltPara:
                bint = self.bandDict[self.dictFiltPara['band']]
                self.paraFilt.param('band').setValue(bint)

    def getSortPara(self):
        self.sortby  = str(self.paraSort.sortby)
        if not self.paraSort.increase:
            self.sortby += '-'
    
    def getFiltPara(self):
        for key in self.filtKeys:
            self.dictFiltPara[key] = self.paraFilt[key]
        # integer 0/1/2 to name band/low/high pass
        bint = self.paraFilt['band']
        self.dictFiltPara['band'] = list(self.bandDict.keys())[list(self.bandDict.values()).index(bint)]
    
    def treeChanged(self, param, changes):
        for param, change, data in changes:
            path = self.paraTree.childPath(param)
            if path is not None:
                childName = '.'.join(path)
            else:
                childName = param.name()
            if childName == 'Sort.Confirm_Sort_Parameters' and change=='activated':
                self.getSortPara()
                print('--> Next: Click the Sort Button to apply sorting by: ', self.sortby)
            elif childName == 'Filter.Confirm_Filt_Parameters' and change=='activated':
                self.getFiltPara()
                if self.paraFilt['apply']:
                    action = 'Apply'
                else:
                    action = 'Remove'
                if self.paraFilt['seis'] == 0:
                    seis = 'Stack'
                    self.onStack = True
                elif self.paraFilt['seis'] == 1:
                    seis = 'Trace'
                    self.onStack = False
                print('--> Next: Click the Filter Button to {:s} filter on {:s}: '.format(action, seis))
                print(self.dictFiltPara)

def valueChanging(param, value):
    print("Value changing (not finalized): %s %s" % (param, value))

###################################################################################################

def convertColors(opts, pppara):
    'Convert color names to RGBA codes for pg'
    opts.colorwave = convertToRGBA(pppara.colorwave, alpha=pppara.alphawave*100)
    opts.colorwavedel = convertToRGBA(pppara.colorwavedel, alpha=pppara.alphawave*100)
    opts.colortwfill = convertToRGBA(pppara.colortwfill, alpha=pppara.alphatwfill*100)
    opts.colortwsele = convertToRGBA(pppara.colortwsele, alpha=pppara.alphatwsele*100)
    opts.pickcolors = [ convertToRGB(c) for c in pppara.pickcolors ]
    return



###################################################################################################

#------------------------------------------------
# Modified from Arnav Sankaran's utils.py in 2016
#    Email: arnavsankaran@gmail.com
# Copyright (c) 2016 Arnav Sankaran
#------------------------------------------------
def convertToRGBA(color, alpha):
    colors = {
        'b': (0, 0, 255, alpha),
        'g': (0, 255, 0, alpha),
        'r': (255, 0, 0, alpha),
        'c': (0, 255, 255, alpha),
        'm': (255, 0, 255, alpha),
        'y': (255, 255, 0, alpha),
        'k': (0, 0, 0, alpha),
        'w': (255, 255, 255, alpha),
        'd': (150, 150, 150, alpha),
        'l': (200, 200, 200, alpha),
        's': (100, 100, 150, alpha),
    }
    colors = colorAlias(colors)
    colors['gray'] = (128, 128, 128, alpha)
    return colors[color]

def convertToRGB(color):
    colors = {
        'b': (0, 0, 255),
        'g': (0, 255, 0),
        'r': (255, 0, 0),
        'c': (0, 255, 255),
        'm': (255, 0, 255),
        'y': (255, 255, 0),
        'k': (0, 0, 0),
        'w': (255, 255, 255),
        'd': (150, 150, 150),
        'l': (200, 200, 200),
        's': (100, 100, 150),
    }
    colors = colorAlias(colors)
    colors['gray'] = (128, 128, 128)
    return colors[color]

def colorAlias(colors):
    alias = {
            'b': 'blue',
            'g': 'green',
            'r': 'red',
            'c': 'cyan',
            'm': 'mangeta',
            'y': 'yellow',
            'k': 'black',
            'w': 'white',
            'd': 'darkgray',
            'l': 'lightgray',
            's': 'slate',
            }
    for key, val in alias.items():
        colors[val] = colors[key]
    return colors