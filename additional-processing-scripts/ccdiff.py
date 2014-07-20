#!/usr/bin/env python

from pylab import *

d2r = pi/180

def ccdiff(i, phase='P'):
	'Difference in crustal correction for Moho depth: vertial and ray'
	if phase == 'P':
		vc, vm = 6.5, 8.04
	else:
		vc, vm = 3.75, 4.47
	i *= d2r
	sini = sin(i)
	cosi = cos(i)
	sinj = vm/vc*sini
	cosj = sqrt(1-sinj**2)
	tani = sini/cosi
	tanj = sinj/cosj
	# vertical correction
	tv = (1./vc - 1./vm)
	# take incidence angle into account
	#print tanj, tani, (tanj-tani)*sinj
	tr = 1./vc/cosi + (tanj-tani)*sinj/vm - 1./vm/cosj
	return tv, tr

if __name__ == '__main__':

	# crustal correction
	incs = arange(14, 25, 1.)
	
	ccp = array([ ccdiff(i, 'P')  for i in incs ])
	ccs = array([ ccdiff(i, 'S')  for i in incs ])

	cpv = ccp[:, 0]
	cpr = ccp[:, 1]
	csv = ccs[:, 0]
	csr = ccs[:, 1]

	figure()
	plot(incs, cpv, label='P ver. Mean {:.3f} s'.format(mean(cpv)))
	plot(incs, cpr, label='P inc. Mean {:.3f} s'.format(mean(cpr)))
	plot(incs, csv, label='S ver. Mean {:.3f} s'.format(mean(csv)))
	plot(incs, csr, label='S inc. Mean {:.3f} s'.format(mean(csr)))

	legend(loc=5)
	title('Crustal Correction for Moho Depth ( vertical vs. incidence angle)')

	xlabel('Incidence Angle ' + r'[$^{\circ}$]')
	ylabel('Correction Time [s]')

	grid()

	show()
