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

    """detect spikes at expected locations for frequency"""
    def atest__time_to_freq(self):
        originalFreq, originalSignalFreq = time_to_freq(originalTime, originalSignalTime, delta_time)
        amplitudeSignalFreq = np.abs(originalSignalFreq)
        for i in xrange(len(amplitudeSignalFreq)):
            if amplitudeSignalFreq[i] > 1000: #spike detected
                # check 1st signal
                print('\nChecking 1st freq: %f' % f1)
                if 0 < originalFreq[i] and originalFreq[i] < f2/2: 
                    print('Current Freq Detected at 1st spike: %f' % originalFreq[i])
                    self.assertTrue(f1-5*delta_freq<originalFreq[i])
                    self.assertTrue(originalFreq[i]<(f1+5*delta_freq))

                # check 2nd signal
                print('\nChecking 2nd freq: %f' % f2)
                if f2/2 < originalFreq[i] and originalFreq[i] < f3/2: 
                    print('Current Freq Detected at 2nd spike: %f' % originalFreq[i])
                    self.assertTrue(f2-5*delta_freq<originalFreq[i])
                    self.assertTrue(originalFreq[i]<(f2+5*delta_freq))

                # check 3rd signal
                print('\nChecking 3rd freq: %f' % f3)
                if 0.75*f3 < originalFreq[i]:
                    print('Current Freq Detected at 3rd spike: %f' % originalFreq[i])
                    self.assertTrue(f3-5*delta_freq<originalFreq[i])
                    self.assertTrue(originalFreq[i]<(f3+5*delta_freq))

    def test__get_filter_params(self):
        MULTIPLE = 3000

        lowFreq = 1.0
        highFreq = 1.5
        order = 4

        #     -------
        #    /        \
        #   /          \     
        #  /  BANDPASS  \
        # /              \
        # ----------------
        # signal high between lowFreq and highFreq
        filterType = 'bandpass'
        NYQ, Wn, B, A, w, h = get_filter_params(delta_time, lowFreq, highFreq, filterType, order)

        for i in xrange(len(w)):
            if h[i] > 1000 and w[i] > 0: #broad spike
                self.assertFalse(w[i]<0.5*lowFreq) 
                self.assertFalse(w[i]>1.5*highFreq)

        # --------
        #         \
        #          \
        #  LOWPASS  \
        #            \
        # ------------
        # signal drops sharply after lowFreq
        filterType = 'lowpass'
        NYQ, Wn, B, A, w, h = get_filter_params(delta_time, lowFreq, highFreq, filterType, order)

        for i in xrange(len(w)):
            if h[i] > 1000 and w[i] > 0: #broad spike
                self.assertFalse(w[i]>1.5*lowFreq) #not allowed to spike pas lowFreq

        #        --------
        #       /
        #      /
        #     /
        #    /  HIGHPASS
        #   /
        #   -------------
        #signal is low before highFreq
        filterType = 'highpass'
        NYQ, Wn, B, A, w, h = get_filter_params(delta_time, lowFreq, highFreq, filterType, order)

        for i in xrange(len(w)):
            if h[i] > 1000 and w[i] > 0: #broad spike
                self.assertFalse(w[i]<highFreq/2)

    """only signal3 should still be prominent"""
    def atest__filtering_time_freq(self):
        filterType = 'bandpass'
        lowFreq = 1.0
        highFreq = 1.5
        order = 2

        originalFreq, originalSignalFreq = time_to_freq(originalTime, originalSignalTime, delta_time)

        filteredSignalTime, filteredSignalFreq, adjusted_w, adjusted_h = filtering_time_freq(originalTime, originalSignalTime, delta_time, filterType, highFreq, lowFreq, order)

        filteredAmplitudeFreq = np.abs(filteredSignalFreq)

        for i in xrange(len(filteredAmplitudeFreq)):
            if filteredAmplitudeFreq[i] > 1000: #spike detected
                if 0<originalFreq[i]:
                    print('LOL %r' % originalFreq[i])
                    # only 3rd freq detected
                    self.assertTrue(f3-delta_freq < originalFreq[i])
                    self.assertTrue(originalFreq[i] < f3+delta_freq)

                    # NOT 1st freq
                    self.assertFalse(originalFreq[i] < f1+5*delta_freq)

                    # NOT 2nd freq
                    self.assertFalse(originalFreq[i] < f2+5*delta_freq)
