import unittest
import numpy as np
from scipy import signal
from pysmo.aimbat.filtering import filtering_time_freq

"""set the parameters for filtering"""
delta = 0.25
originalTime = np.arange(-200, 200, delta)
originalSignalTime= 4*np.sin(originalTime/2) + 2.4*np.cos(originalTime*8) + 5*np.cos(originalTime*2)

# Here's our "unit tests".
class filteringModel(unittest.TestCase):

    # only the signal between 1.0 and 1.5 Hz should still be prominent
    def test__filtering_time_freq(self):
        filterType = 'bandpass'
        lowFreq = 1.0
        highFreq = 1.5
        order = 2

        filteredSignalTime, filteredSignalFreq, adjusted_w, adjusted_h = filtering_time_freq(originalTime, originalSignalTime, delta, filterType, highFreq, lowFreq, order)


        print originalTime
