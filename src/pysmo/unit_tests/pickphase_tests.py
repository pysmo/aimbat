import unittest, shutil
import sys, os, matplotlib
from pysmo.aimbat.qualctrl import getOptions, getDataOpts, sortSeis, getAxes, PickPhaseMenuMore
from pysmo.aimbat.pickphase import PickPhaseMenu
from pysmo.aimbat.sacpickle import saveData


# ############################################################################### #
#                                     VIEWS                                       #
# ############################################################################### #

class pickphaseView(unittest.TestCase):

    def test__save_headers_filterParams(self):
    	
    	
    	shutil.copy2('20120124.00520523.bhz.pkl', 'temp-test-bhz.pkl')

    	sys.argv[1:] = ['temp-test-bhz.pkl']
    	gsac, opts = getDataOpts()
    	axs = getAxes(opts)
    	setattr(opts,'labelqual',True)
    	ppm = PickPhaseMenu(gsac, opts, axs)

    	print opts.filterParameters['lowFreq'] 

    	# click the save button
    	click_save_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppm.axpp.figure.canvas, 63, 481)
    	ppm.save(click_save_event)

    	#click the save parameters chosen event
    	click_params_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppm.axpp.figure.canvas, 256, 48)
    	ppm.save_headers_filterParams(click_params_event)

# ############################################################################### #
#                                     VIEWS                                       #
# ############################################################################### #