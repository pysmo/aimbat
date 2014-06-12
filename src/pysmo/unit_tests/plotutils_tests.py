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
        axs = getAxes(opts)
        ppm = PickPhaseMenu(gsac, opts, axs)

        ppm.plotSpan()

# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #
















