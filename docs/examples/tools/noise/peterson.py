#!/usr/bin/env python

# Example script for pysmo.tools.noise
import pysmo.tools.noise as noise
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

npts=10000
delta=0.5
fs = 1 / delta
nperseg=npts/4
nfft=npts/2
time = np.linspace(0,npts*delta, npts)

# Generate random noise
high_noise = noise.genNoiseNHNM(delta, npts)
low_noise = noise.genNoiseNLNM(delta, npts)

# Calculuate power spectral density
f_high, Pxx_dens_high = signal.welch(high_noise, fs, nperseg=nperseg, nfft=nfft, scaling='density')
f_low, Pxx_dens_low = signal.welch(low_noise, fs, nperseg=nperseg, nfft=nfft, scaling='density')

fig = plt.figure(figsize=(13,6))
# Plot random high and low noise
plt.subplot(221)
plt.plot(time, high_noise, 'c')
plt.ylabel('Ground Accelaration')

plt.subplot(223)
plt.plot(time, low_noise, 'm')
plt.ylabel('Ground Accelaration')
plt.xlabel('Time [s]')

# Plot PSD of noise
plt.subplot(122)
plt.plot(1/f_high, 10*np.log10(Pxx_dens_high), 'c', label='generated high noise')
plt.plot(1/f_low, 10*np.log10(Pxx_dens_low), 'm', label='generated low noise')
plt.plot(noise.NLNM['T'],noise.NLNM['dB'], 'k', linewidth=2)
plt.plot(noise.NHNM['T'],noise.NHNM['dB'], 'k', linewidth=2)
plt.gca().set_xscale("log")
plt.xlabel('Period [s]')
plt.ylabel('Power Spectral Density (dB/Hz)')
plt.legend()
plt.savefig('peterson.png')
plt.show()
