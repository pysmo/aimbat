import unittest
import sys, os, matplotlib
from pysmo.aimbat.sacpickle import readPickle, zipFile, pkl2sac
from pysmo.aimbat.qualctrl import getOptions, getDataOpts, sortSeis, getAxes, PickPhaseMenuMore

test_filename = '20120109.04071467.bhz.pkl'

# ############################################################################### #
#                                     MODELS                                      #
# ############################################################################### #

class qualctrlModel(unittest.TestCase):

    def test_getOptions(self):
    	sys.argv[1:] = [test_filename]
    	opts = getOptions()
    	self.assertIsNone(opts[0].twin_on)
        self.assertEqual(opts[0].maxnum,(37,3))
        self.assertIsNone(opts[0].nlab_on)

    def test_getDataOpts(self):
    	sys.argv[1:] = [test_filename]
    	gsac, opts = getDataOpts()
        self.assertEqual(len(gsac.delist),7)
        self.assertEqual(len(gsac.selist),117)
        self.assertEqual(len(gsac.delist)+len(gsac.selist),len(gsac.saclist))

    def test_readSACfilesRight(self):
        sys.argv[1:] = [test_filename]
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

    def test_sortSeismogramsFilename(self):
        sys.argv[1:] = [test_filename]
        gsac, opts = getDataOpts()

        """before sorting"""
        unsortedFiles = []
        for sacdh in gsac.saclist:
            unsortedFiles.append(sacdh.filename)

        """after sorting"""
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

    # ------------------------------ SORTING ------------------------------------ #

    def test_sortFigExists(self):
        sys.argv[1:] = [test_filename]
        gsac, opts = getDataOpts()
        axs = getAxes(opts)
        ppmm = PickPhaseMenuMore(gsac, opts, axs)

        self.assertFalse(hasattr(ppmm,'figsort'))

        fake_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.axstk.figure.canvas, 62, 295)
        ppmm.sorting(fake_event)

        self.assertIsNotNone(ppmm.figsort)
        self.assertIsNotNone(ppmm.sortAxs)

    def test_sortButtonWorks(self):
        sys.argv[1:] = [test_filename]
        gsac, opts = getDataOpts()

        axs = getAxes(opts)
        ppmm = PickPhaseMenuMore(gsac, opts, axs)

        # get files before sorting
        unsortedFiles = []
        for sacdh in gsac.selist:
            unsortedFiles.append(sacdh.filename)

        # click the sort button
        event_clickSortBtn = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.axstk.figure.canvas, 62, 295)
        ppmm.sorting(event_clickSortBtn)
        event_clickSortFilenameBtn = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.figsort.canvas, 151, 700)
        ppmm.sort_file(event_clickSortFilenameBtn)

        # get files after sorting
        sortedFiles = []
        for sacdh in gsac.selist:
            sortedFiles.append(sacdh.filename)
        
        self.assertNotEqual(unsortedFiles, sortedFiles)

    # ------------------------------ SORTING ------------------------------------ #


    # ------------------------------- FILTERING --------------------------------- #

    def test_filterFigExists(self):
        sys.argv[1:] = [test_filename]
        gsac, opts = getDataOpts()
        axs = getAxes(opts)
        ppmm = PickPhaseMenuMore(gsac, opts, axs)

        self.assertFalse(hasattr(ppmm,'figfilter'))

        fake_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.axstk.figure.canvas, 56, 224)
        ppmm.filtering(fake_event)

        self.assertIsNotNone(ppmm.figfilter)
        self.assertIsNotNone(ppmm.filterAxs)

    def test_filterSelectOrderWorks(self):
        sys.argv[1:] = [test_filename]
        gsac, opts = getDataOpts()
        axs = getAxes(opts)
        ppmm = PickPhaseMenuMore(gsac, opts, axs)
        fake_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.axstk.figure.canvas, 56, 224)
        ppmm.filtering(fake_event)

        ppmm.getButterOrder('3')


        

    # ------------------------------- FILTERING --------------------------------- #

# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #
















