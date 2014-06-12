import unittest
import sys, os, matplotlib
from pysmo.aimbat.sacpickle import readPickle, zipFile, pkl2sac
from pysmo.aimbat.qualctrl import getOptions, getDataOpts, sortSeis, getAxes, PickPhaseMenuMore

# ############################################################################### #
#                                     MODELS                                      #
# ############################################################################### #

class qualctrlModel(unittest.TestCase):

    def test_getOptions(self):
    	sys.argv[1:] = ['20120109.04071467.bhz.pkl']
    	opts = getOptions()
    	self.assertIsNone(opts[0].twin_on)
        self.assertEqual(opts[0].maxnum,(37,3))
        self.assertIsNone(opts[0].nlab_on)

    def test_getDataOpts(self):
    	sys.argv[1:] = ['20120109.04071467.bhz.pkl']
    	gsac, opts = getDataOpts()
        self.assertEqual(len(gsac.delist),7)
        self.assertEqual(len(gsac.selist),117)
        self.assertEqual(len(gsac.delist)+len(gsac.selist),len(gsac.saclist))

    def test_readSACfilesRight(self):
        sys.argv[1:] = ['20120109.04071467.bhz.pkl']
        gsac, opts = getDataOpts()

        """event year correct"""
        self.assertEqual(gsac.event[0], 2012) 

        """event month correct"""
        self.assertEqual(gsac.event[1], 1) 

        """event day correct"""
        self.assertEqual(gsac.event[2], 9) 

        """event lat correct"""
        self.assertEqual(gsac.event[6], -10.616999626159668) 

        """event lon correct"""
        self.assertEqual(gsac.event[7], 165.16000366210938) 

        """event depth correct"""
        self.assertEqual(gsac.event[8], 28.0) 

        """event magnitude correct"""
        self.assertEqual(gsac.event[9], 6.400000095367432) 

    def test_sortSeismograms(self):
        sys.argv[1:] = ['20120109.04071467.bhz.pkl']
        gsac, opts = getDataOpts()

        """sort by file name"""
        unsortedFiles = []
        for sacdh in gsac.saclist:
            unsortedFiles.append(sacdh.filename)

        sortedFiles = []
        opts.sortby = 'i';
        sortSeis(gsac, opts)
        for sacdh in gsac.saclist:
            sortedFiles.append(sacdh.filename)
        sortedFiles = sortedFiles.sort()

        self.assertEqual(sortedFiles, unsortedFiles.sort())

# ############################################################################### #
#                                     MODELS                                      #
# ############################################################################### #






# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #
        
class qualctrlView(unittest.TestCase):

    def test_buttonClick(self):
        sys.argv[1:] = ['20120109.04071467.bhz.pkl']
        gsac, opts = getDataOpts()
        axs = getAxes(opts)
        ppmm = PickPhaseMenuMore(gsac, opts, axs)
        fake_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.axstk.figure.canvas, 62, 295)
        ppmm.sorting(fake_event)
        self.assertIsNotNone(ppmm.sortAxs)


# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #
















