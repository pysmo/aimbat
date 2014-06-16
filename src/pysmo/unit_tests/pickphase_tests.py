import unittest
import sys, os, matplotlib
from pysmo.aimbat.pickphase import 


# ############################################################################### #
#                                     VIEWS                                       #
# ############################################################################### #

class pickphaseView(unittest.TestCase):

    def test_getOptions(self):
    	sys.argv[1:] = [test_filename]
    	opts = getOptions()
    	self.assertIsNone(opts[0].twin_on)
        self.assertEqual(opts[0].maxnum,(37,3))
        self.assertIsNone(opts[0].nlab_on)


# ############################################################################### #
#                                     VIEWS                                       #
# ############################################################################### #