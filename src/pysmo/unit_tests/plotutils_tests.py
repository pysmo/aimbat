import unittest
import sys, os, matplotlib
import matplotlib.pyplot as py
from pysmo.aimbat.plotutils import TimeSelector
from pysmo.aimbat.qualctrl import getOptions, getDataOpts, sortSeis, getAxes, PickPhaseMenuMore
from pysmo.aimbat.pickphase import PickPhaseMenu, PickPhase

test_filename = '20120109.04071467.bhz.pkl'

# ############################################################################### #
#                                     MODELS                                      #
# ############################################################################### #

class plotutilsModel(unittest.TestCase):

    def test_getOptions(self):
    	pass

# ############################################################################### #
#                                     MODELS                                      #
# ############################################################################### #






# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #
        
class plotutilsView(unittest.TestCase):

    def test_timeSelector_ignore(self):
        sys.argv[1:] = [test_filename]
        gsac, opts = getDataOpts()
        opts.labelqual = True
        axs = getAxes(opts)
        ppm = PickPhaseMenu(gsac, opts, axs)

        # event1= matplotlib.backend_bases.MouseEvent('button_press_event', ppm.axs['Fstk'].figure.canvas, 511,869)
        # event1.xydata=(-5.00913306168,1.09354304636)
        # event1.inaxes=ppm.axs['Fstk']

        # event2= matplotlib.backend_bases.MouseEvent('button_press_event', ppm.axs['Fstk'].figure.canvas, 511,869)
        # event2.xydata=(-5.00913306168,1.09354304636)
        # event2.inaxes=ppm.axs['Fstk']

        # event3= matplotlib.backend_bases.MouseEvent('button_release_event', ppm.axs['Fstk'].figure.canvas, 511,869)
        # event3.xydata=(-5.00913306168,1.09354304636)
        # event3.inaxes=ppm.axs['Fstk']

        # event4= matplotlib.backend_bases.MouseEvent('button_release_event', ppm.axs['Fstk'].figure.canvas, 511,869)
        # event4.xydata=(-5.00913306168,1.09354304636)
        # event4.inaxes=ppm.axs['Fstk']

        # event5= matplotlib.backend_bases.MouseEvent('button_press_event', ppm.axs['Fstk'].figure.canvas, 594,820)
        # event5.xydata=(0.821975551496,-0.934602649007)
        # event5.inaxes=ppm.axs['Fstk']

        # event6= matplotlib.backend_bases.MouseEvent('button_press_event', ppm.axs['Fstk'].figure.canvas, 594,820)
        # event6.xydata=(0.821975551496,-0.934602649007)
        # event6.inaxes=ppm.axs['Fstk']

        # event7= matplotlib.backend_bases.MouseEvent('motion_notify_event', ppm.axs['Fstk'].figure.canvas, 600,817)
        # event7.xydata=(1.24350147534,-1.05877483444)
        # event7.inaxes=ppm.axs['Fstk']

        # event8= matplotlib.backend_bases.MouseEvent('motion_notify_event', ppm.axs['Fstk'].figure.canvas, 635,807)
        # event8.xydata=(3.70240269777,-1.47268211921)
        # event8.inaxes=ppm.axs['Fstk']

        # event9= matplotlib.backend_bases.MouseEvent('button_release_event', ppm.axs['Fstk'].figure.canvas, 635,807)
        # event9.xydata=(3.70240269777,-1.47268211921)
        # event9.inaxes=ppm.axs['Fstk']

        ppm.on_select(-3,3)

        print ppm.axpp.get_xlim()

# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #
















