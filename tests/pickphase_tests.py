import unittest, shutil, random
import sys, os, matplotlib
from pysmo.aimbat.qualctrl import getOptions, getDataOpts, sortSeis, getAxes, PickPhaseMenuMore
from pysmo.aimbat.pickphase import PickPhaseMenu
from pysmo.aimbat.sacpickle import saveData


# ############################################################################### #
#                                     VIEWS                                       #
# ############################################################################### #

class pickphaseView(unittest.TestCase):

    def test__save_headers_filterParams(self):
    	# copy the file each time so we can destroy it
    	shutil.copy2('20120124.00520523.bhz.pkl', 'temp-test-bhz.pkl')

    	sys.argv[1:] = ['temp-test-bhz.pkl']
    	gsac1, opts1 = getDataOpts()
    	axs1 = getAxes(opts1)
    	setattr(opts1,'labelqual',True)
    	ppm1 = PickPhaseMenu(gsac1, opts1, axs1)

    	# randomly get stuff
    	rand_order = random.randint(1, 4) 
    	rand_lowFreq = random.uniform(0.1,0.2)
    	rand_highFreq = random.uniform(0.8,1.2)

    	opts1.filterParameters['lowFreq'] = rand_lowFreq
    	opts1.filterParameters['highFreq'] = rand_highFreq
    	opts1.filterParameters['order'] = rand_order

    	# click the save button
    	click_save_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppm1.axpp.figure.canvas, 63, 481)
    	ppm1.save(click_save_event)

    	#click the save parameters chosen event
    	click_params_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppm1.axpp.figure.canvas, 256, 48)
    	ppm1.save_headers_filterParams(click_params_event)

    	# reload to make sure parameters exist now
    	sys.argv[1:] = ['temp-test-bhz.pkl']
    	gsac2, opts2 = getDataOpts()

    	self.assertEqual(rand_lowFreq, opts2.filterParameters['lowFreq'])
    	self.assertEqual(rand_highFreq, opts2.filterParameters['highFreq'])
    	self.assertEqual(rand_order, opts2.filterParameters['order'])

    def test__save_headers_filterParams(self):
    	# copy the file each time so we can destroy it
    	shutil.copy2('20120124.00520523.bhz.pkl', 'temp-test-bhz.pkl')

    	sys.argv[1:] = ['temp-test-bhz.pkl']
    	gsac1, opts1 = getDataOpts()
    	axs1 = getAxes(opts1)
    	setattr(opts1,'labelqual',True)
    	ppm1 = PickPhaseMenu(gsac1, opts1, axs1)

    	originalSaclist = gsac1.saclist

    	# click the save button
    	click_save_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppm1.axpp.figure.canvas, 63, 481)
    	ppm1.save(click_save_event)

    	#click the save parameters chosen event
    	click_params_event = matplotlib.backend_bases.MouseEvent('button_press_event', ppm1.axpp.figure.canvas, 415, 54)
    	ppm1.save_headers_filterParams(click_params_event)

    	# reload to make sure data has been overwritten
    	sys.argv[1:] = ['temp-test-bhz.pkl']
    	gsac2, opts2 = getDataOpts()

    	for i in xrange(len(gsac2.saclist)):
    		self.assertNotEqual(gsac1.saclist[i], gsac2.saclist[i])



    	

# ############################################################################### #
#                                     VIEWS                                       #
# ############################################################################### #








