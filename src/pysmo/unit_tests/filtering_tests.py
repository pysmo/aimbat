import unittest
import numpy as np
from scipy import signal
from pysmo.aimbat.filtering import filtering_time_freq, get_filter_params, filtering_time_signal, time_to_freq

"""set the parameters for filtering"""
delta_time = 0.25
delta_freq = 0.0025
originalTime = np.arange(-200, 200, delta_time)
originalSignalTime= 4*np.sin(originalTime/2) + 2.4*np.cos(originalTime*8) + 5*np.cos(originalTime*2)

"""frequencies for wave of form A * sin(wt) is 
w=2*pi*f => f=w/(2*pi)
all freq 
"""
f1 = 0.5/(2*np.pi)
f2 = 2/(2*np.pi)
f3 = 8/(2*np.pi)

# Here's our "unit tests".
class filteringModel(unittest.TestCase):

    def test__time_to_freq(self):
        originalFreq, originalSignalFreq = time_to_freq(originalTime, originalSignalTime, delta_time)
        amplitudeSignalFreq = np.abs(originalSignalFreq)
        #print originalFreq
        # f1 spike exists
        spike1 = []
        for i in xrange(len(amplitudeSignalFreq)):
            if amplitudeSignalFreq[i] > 1000: #spike detected
                # check first signal
                print '\nChecking first freq: %f' % f1
                if 0 < originalFreq[i] and originalFreq[i] < f2/2: 
                    print 'Current Freq Detected at spike: %r' % originalFreq[i]
                    self.assertTrue(f1-50*delta_freq<originalFreq[i])
                    self.assertTrue(originalFreq[i]<(f1+50*delta_freq))


    # only the signal between 1.0 and 1.5 Hz should still be prominent
    def test__filtering_time_freq(self):
        filterType = 'bandpass'
        lowFreq = 1.0
        highFreq = 1.5
        order = 2

        filteredSignalTime, filteredSignalFreq, adjusted_w, adjusted_h = filtering_time_freq(originalTime, originalSignalTime, delta_time, filterType, highFreq, lowFreq, order)


