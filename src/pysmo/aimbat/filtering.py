import numpy as np
from scipy import signal
import math

def filtering_data(originalTime, originalSignalTime, delta, ):
	NYQ = 1.0/(2*delta)
	
	originalFreq, originalSignalFreq = time_to_freq(originalTime, originalSignalTime)

	# make filter, default is bandpass
	Wn = [self.opts.filterParameters['lowFreq']/NYQ, self.opts.filterParameters['highFreq']/NYQ]
	B, A = signal.butter(self.opts.filterParameters['order'], Wn, analog=False, btype='bandpass')
	if self.opts.filterParameters['band']=='lowpass':
		Wn = self.opts.filterParameters['lowFreq']/NYQ
		B, A = signal.butter(self.opts.filterParameters['order'], Wn, analog=False, btype='lowpass')
	elif self.opts.filterParameters['band']=='highpass':
		Wn = self.opts.filterParameters['highFreq']/NYQ
		B, A = signal.butter(self.opts.filterParameters['order'], Wn, analog=False, btype='highpass')
	
	w, h = signal.freqz(B, A)

	# apply filter
	filteredSignalTime = signal.lfilter(B, A, originalSignalTime)

	# convert filtered time signal -> frequency signal
	filteredSignalFreq = np.fft.fft(filteredSignalTime)

	return filteredSignalTime, filteredSignalFreq


def time_to_freq(originalTime, originalSignalTime, delta):
	originalFreq = np.fft.fftfreq(len(originalTime), delta) 
	originalSignalFreq = np.fft.fft(originalSignalTime) 
	return originalFreq, originalSignalFreq























