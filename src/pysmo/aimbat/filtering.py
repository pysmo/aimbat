import numpy as np
from scipy import signal
import math

def filtering_data(originalTime, originalSignalTime, 
		delta, filterType, highFreq, lowFreq, order):
	NYQ = 1.0/(2*delta)
	
	originalFreq, originalSignalFreq = time_to_freq(originalTime, originalSignalTime, delta)

	# make filter, default is bandpass
	Wn = [lowFreq/NYQ, highFreq/NYQ]
	B, A = signal.butter(order, Wn, analog=False, btype='bandpass')
	if filterType=='lowpass':
		Wn = lowFreq/NYQ
		B, A = signal.butter(order, Wn, analog=False, btype='lowpass')
	elif filterType=='highpass':
		Wn = self.opts.filterParameters['highFreq']/NYQ
		B, A = signal.butter(order, Wn, analog=False, btype='highpass')
	
	w, h = signal.freqz(B, A)

	MULTIPLE = 0.7*max(np.abs(originalSignalFreq))
	adjusted_w = w*(NYQ/np.pi)
	adjusted_h = MULTIPLE*np.abs(h)

	# apply filter
	filteredSignalTime = signal.lfilter(B, A, originalSignalTime)

	# convert filtered time signal -> frequency signal
	filteredSignalFreq = np.fft.fft(filteredSignalTime)

	return filteredSignalTime, filteredSignalFreq, adjusted_w, adjusted_h




def time_to_freq(originalTime, originalSignalTime, delta):
	originalFreq = np.fft.fftfreq(len(originalTime), delta) 
	originalSignalFreq = np.fft.fft(originalSignalTime) 
	return originalFreq, originalSignalFreq























