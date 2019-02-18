import unittest
import sys, os, matplotlib
import matplotlib.pyplot as py
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

        # event year correct
        self.assertEqual(gsac.event[0], 2012) 

        # event month correct
        self.assertEqual(gsac.event[1], 1) 

        # event day correct
        self.assertEqual(gsac.event[2], 9) 

        # event lat correct
        self.assertEqual(gsac.event[6], -10.616999626159668) 

        # event lon correct
        self.assertEqual(gsac.event[7], 165.16000366210938) 

        # event depth correct
        self.assertEqual(gsac.event[8], 28.0) 

        # event magnitude correct
        self.assertEqual(gsac.event[9], 6.400000095367432) 

    def test_sortSeismogramsFilename(self):
        sys.argv[1:] = [test_filename]
        gsac, opts = getDataOpts()

        # before sorting
        unsortedFiles = []
        for sacdh in gsac.saclist:
            unsortedFiles.append(sacdh.filename)

        # after sorting
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
        
class qualctrlView():

    # ------------------------------ SORTING ------------------------------------ #

    class sortingClass(unittest.TestCase):

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

            # click sort filename button
            event_clickSortFilenameBtn = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.figsort.canvas, 151, 700)
            ppmm.sort_file(event_clickSortFilenameBtn)

            # get files after sorting
            sortedFiles = []
            for sacdh in gsac.selist:
                sortedFiles.append(sacdh.filename)
            
            self.assertNotEqual(unsortedFiles, sortedFiles)

        def test_filter_spreadButter(self):
            sys.argv[1:] = [test_filename]
            gsac, opts = getDataOpts()
            axs = getAxes(opts)
            ppmm = PickPhaseMenuMore(gsac, opts, axs)

            # click the filter button
            event_clickFilterBtn = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.axstk.figure.canvas, 71,223)
            ppmm.filtering(event_clickFilterBtn)
   
            # click apply filter button
            event_clickApplyFilterBtn = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.figfilter.canvas, 646,829)
            ppmm.applyFilter(event_clickApplyFilterBtn)

    # ------------------------------ SORTING ------------------------------------ #


    # ------------------------------- FILTERING --------------------------------- #

    class filterClass(unittest.TestCase):

        """setup the necessary environment first"""
        def runBefore(self):
            sys.argv[1:] = [test_filename]
            gsac, opts = getDataOpts()
            axs = getAxes(opts)
            ppmm = PickPhaseMenuMore(gsac, opts, axs)

            fake_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.axstk.figure.canvas, 56, 224)
            ppmm.filtering(fake_event)
            return ppmm

        """test that the filter popup window has the expected components"""
        def test_filterFigExists(self):
            ppmm = self.runBefore()
            self.assertIsNotNone(ppmm.figfilter)
            self.assertIsNotNone(ppmm.filterAxs)

        """can change order of filter"""
        def test_filter_getButterOrder(self):
            ppmm = self.runBefore()
            ppmm.getButterOrder('3')
            self.assertEqual(ppmm.opts.filterParameters['order'], 3)

        """can change type of filter to bandpass/lowpass/highpass """
        def test_filter_getBandType(self):
            ppmm = self.runBefore()
            ppmm.getBandtype('lowpass')
            self.assertEqual(ppmm.opts.filterParameters['band'], 'lowpass')

        """can change filter parameter for lowpass filter"""
        def test_filter_getLowFreq(self):
            ppmm = self.runBefore()
            self.assertEqual(ppmm.opts.filterParameters['lowFreq'], 0.05)
            ppmm.getBandtype('lowpass')

            fake_event = matplotlib.backend_bases.LocationEvent('button_press_event', ppmm.figfilter.canvas, 370, 266)
            fake_event.inaxes = ppmm.filterAxs['amVfreq']
            fake_event.xdata = 0.38
            ppmm.getLowFreq(fake_event)

            self.assertEqual(ppmm.opts.filterParameters['lowFreq'], 0.38)

        """can change filter parameter for highpass filter"""
        def test_filter_getHighFreq(self):
            ppmm = self.runBefore()
            self.assertEqual(ppmm.opts.filterParameters['highFreq'], 0.25)
            ppmm.getBandtype('highpass')

            fake_event = matplotlib.backend_bases.LocationEvent('button_press_event', ppmm.figfilter.canvas, 370, 266)
            fake_event.inaxes = ppmm.filterAxs['amVfreq']
            fake_event.xdata = 0.55
            ppmm.getHighFreq(fake_event)

            self.assertEqual(ppmm.opts.filterParameters['highFreq'], 0.55)

        """can change filter parameter for bandpass filter"""
        def test_filter_getBandpassFreq(self):
            ppmm = self.runBefore()
            self.assertEqual(ppmm.opts.filterParameters['band'],'bandpass')
            self.assertFalse(ppmm.opts.filterParameters['advance'])

            # first click
            eventA = matplotlib.backend_bases.LocationEvent('button_press_event', ppmm.figfilter.canvas, 370, 266)
            eventA.inaxes = ppmm.filterAxs['amVfreq']
            eventA.xdata = 0.20
            ppmm.getBandpassFreq(eventA)
            self.assertEqual(ppmm.opts.filterParameters['lowFreq'], 0.20)

            # second click
            eventB = matplotlib.backend_bases.LocationEvent('button_press_event', ppmm.figfilter.canvas, 371, 267)
            eventB.inaxes = ppmm.filterAxs['amVfreq']
            eventB.xdata = 0.45
            ppmm.getBandpassFreq(eventB)
            self.assertEqual(ppmm.opts.filterParameters['highFreq'], 0.45)

        """applying the filter works"""
        def test_filter_applyFilter(self):
            ppmm = self.runBefore()

            fake_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.figfilter.canvas, 636, 823)
            ppmm.applyFilter(fake_event)

            # check the figure has been closed
            self.assertFalse(py.fignum_exists(ppmm.figfilter.number))

        """unapplying the filter works"""
        def test_filter_unapplyFilter(self):
            ppmm = self.runBefore()

            event_apply = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.figfilter.canvas, 636, 823)
            ppmm.applyFilter(event_apply)

            event_unapply = matplotlib.backend_bases.MouseEvent('button_press_event', ppmm.figfilter.canvas, 538, 838)
            ppmm.unapplyFilter(event_unapply)

            self.assertFalse(ppmm.opts.filterParameters['apply'])
            self.assertFalse(py.fignum_exists(ppmm.figfilter.number))

    # ------------------------------- FILTERING --------------------------------- #

# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #
















