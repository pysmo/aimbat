#!/usr/bin/env python
#------------------------------------------------
# Filename: filtering.py
#   Author: Lay Kuan Loh 
#    Email: lkloh2410@gmail.com
#
# Copyright (c) 2014 Lay Kuan Loh
#------------------------------------------------

import numpy as np
from scipy import signal


"""when the user is picking"""
def filtering_time_freq(originalTime, originalSignalTime, delta, filterType, highFreq, lowFreq, order, runReversePass = False):
	originalFreq, originalSignalFreq = time_to_freq(originalTime, originalSignalTime, delta)

	# make filter, default is bandpass
	MULTIPLE = 0.7*max(np.abs(originalSignalFreq))
	NYQ, Wn, B, A, adjusted_w, adjusted_h = get_filter_params(delta, lowFreq, highFreq, filterType, order, MULTIPLE)

	# apply filter
	filteredSignalTime = signal.lfilter(B, A, originalSignalTime)
	if runReversePass:
		filteredSignalTime = signal.lfilter(B, A, filteredSignalTime[::-1])
		filteredSignalTime = filteredSignalTime[::-1]

	# convert filtered time signal -> frequency signal
	filteredSignalFreq = np.fft.fft(filteredSignalTime)

	return filteredSignalTime, filteredSignalFreq, adjusted_w, adjusted_h

def get_filter_params(delta, lowFreq, highFreq, filterType, order, MULTIPLE=3000):
	NYQ = 1.0/(2*delta)
	Wn = [lowFreq/NYQ, highFreq/NYQ]
	B, A = signal.butter(order, Wn, analog=False, btype='bandpass')
	if filterType=='lowpass':
		Wn = lowFreq/NYQ
		B, A = signal.butter(order, Wn, analog=False, btype='lowpass')
	elif filterType=='highpass':
		Wn = highFreq/NYQ
		B, A = signal.butter(order, Wn, analog=False, btype='highpass')

	w, h = signal.freqz(B, A)
	adjusted_w = w*(NYQ/np.pi)
	adjusted_h = MULTIPLE*np.abs(h)

	return NYQ, Wn, B, A, adjusted_w, adjusted_h

def filtering_time_signal(originalSignalTime, delta, lowFreq, highFreq, filterType, order, MULTIPLE, runReversePass = False):
	NYQ, Wn, B, A, w, h = get_filter_params(delta, lowFreq, highFreq, filterType, order, MULTIPLE)
	filteredSignalTime = signal.lfilter(B, A, originalSignalTime)
	if runReversePass:
		filteredSignalTime = signal.lfilter(B, A, filteredSignalTime[::-1])
		filteredSignalTime = filteredSignalTime[::-1]
	return filteredSignalTime

def time_to_freq(originalTime, originalSignalTime, delta):
	originalFreq = np.fft.fftfreq(len(originalTime), delta) 
	originalSignalFreq = np.fft.fft(originalSignalTime) 
	return originalFreq, originalSignalFreq























