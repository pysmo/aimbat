import unittest
import sys
from pysmo.aimbat.qualctrl import getDataOpts, getAxes
from pysmo.aimbat.pickphase import PickPhaseMenu

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

        ppm.on_select(-3,4.3)
        self.assertEqual(ppm.axpp.get_xlim(),(-3,4.3))

# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #
















