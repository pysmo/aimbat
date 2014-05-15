#!/usr/bin/env python
#------------------------------------------------
# Filename: qualctrl.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009-2012 Xiaoting Lou
#------------------------------------------------
"""
Python module for interactively measuring body wave travel times and quality control.

	PickPhaseMenuMore
		||
	PickPhaseMenu + Buttons: ICCS-A  Sync  ICCS-B  MCCC  SACP2


:copyright:
	Xiaoting Lou

:license:
	GNU General Public License, Version 3 (GPLv3) 
	http://www.gnu.org/licenses/gpl.html
"""


from pylab import *
import os, sys, copy
from matplotlib.mlab import l2norm
from matplotlib.widgets import SpanSelector, Button, CheckButtons
from matplotlib import transforms
from matplotlib.font_manager import FontProperties
from ttconfig import PPConfig, QCConfig, CCConfig, MCConfig, getParser
from sacpickle import loadData, SacDataHdrs, taperWindow
from plotutils import TimeSelector, pickLegend
from plotphase import sacp2
from pickphase import PickPhase, PickPhaseMenu
from qualsort import initQual, seleSeis, sortSeisQual, sortSeisHeader, sortSeisHeaderDiff
from algiccs import ccWeightStack, checkCoverage
from algmccc import mccc, findPhase, eventListName, rcwrite

import Tkinter
import tkMessageBox

def getOptions():
	""" Parse arguments and options. """
	parser = getParser()
	maxsel = 37
	maxdel = 3
	maxnum = maxsel, maxdel
	twcorr = -15, 15
	sortby = '1'
	fill = 1
	reltime = 0
	xlimit = -30, 30
	parser.set_defaults(xlimit=xlimit)
	parser.set_defaults(twcorr=twcorr)
	parser.set_defaults(reltime=reltime)
	parser.set_defaults(maxnum=maxnum)
	parser.set_defaults(sortby=sortby)
	parser.set_defaults(fill=fill)
	parser.add_option('-b', '--boundlines', action="store_true", dest='boundlines_on',
		help='Plot bounding lines to separate seismograms.')
	parser.add_option('-n', '--netsta', action="store_true", dest='nlab_on',
		help='Label seismogram by net.sta code instead of SAC file name.')
	parser.add_option('-m', '--maxnum',  dest='maxnum', type='int', nargs=2,
		help='Maximum number of selected and deleted seismograms to plot. Defaults: {0:d} and {1:d}.'.format(maxsel, maxdel))
	parser.add_option('-p', '--phase',  dest='phase', type='str',
		help='Seismic phase name: P/S .')
	parser.add_option('-s', '--sortby', type='str', dest='sortby',
		help='Sort seismograms by i (file indices), or 0/1/2/3 (quality factor all/ccc/snr/coh), or t (time pick diff), or a given header (az/baz/dist..). Append - for decrease order, otherwise increase. Default is {:s}.'.format(sortby))
	parser.add_option('-t', '--twcorr', dest='twcorr', type='float', nargs=2,
		help='Time window for cross-correlation. Default is [{:.1f}, {:.1f}] s'.format(twcorr[0],twcorr[1]))
	parser.add_option('-g', '--savefig', action="store_true", dest='savefig',
		help='Save figure instead of showing.')
	opts, files = parser.parse_args(sys.argv[1:])
	if len(files) == 0:
		print parser.usage
		sys.exit()
	return opts, files


class PickPhaseMenuMore:
	""" Pick phase for multiple seismograms and array stack
		Button: Sync
	"""
	def __init__(self, gsac, opts, axs):
		self.gsac = gsac
		self.opts = opts
		self.axs = axs
		self.axstk = self.axs['Fstk']
		if not 'stkdh' in gsac.__dict__:
			if opts.filemode == 'sac' and os.path.isfile(opts.fstack):
				gsac.stkdh = SacDataHdrs(opts.fstack, opts.delta)
			else:
				hdrini, hdrmed, hdrfin = opts.qcpara.ichdrs
				self.cchdrs = [hdrini, hdrmed]
				self.twcorr = opts.ccpara.twcorr
				# check data coverage
				opts.ipick = hdrini
				opts.twcorr = opts.ccpara.twcorr
				checkCoverage(gsac, opts) 
				gsac.selist = gsac.saclist
				self.ccStack()
		self.initPlot()
		self.plotStack()
		self.addEarthquakeInfo()
		self.setLabels()
		self.connect()

	def initPlot(self):
		""" Plot waveforms """
		gsac = self.gsac
		opts = self.opts
		sortSeis(gsac, opts)
		self.ppm = PickPhaseMenu(gsac, opts, self.axs)
		# make the legend box invisible
		if self.opts.pick_on:
			self.ppm.axpp.get_legend().set_visible(False)

	def addEarthquakeInfo(self):
		""" Set Earthquake Info
		  * Magnitude
		  * Location (Lat and Long)
		  * Depth
		"""
		gsac = self.gsac
		# get required parameters
		locationLat = round(gsac.event[6],2)
		locationLon = round(gsac.event[7],2)
		depth = round(gsac.event[8],2)
		magnitude = round(gsac.event[9],2)

		infoaxis = self.axs['Info']

		# remove axes markings
		infoaxis.axes.get_xaxis().set_ticks([])
		infoaxis.axes.get_yaxis().set_visible(False)

		# write the info into the axis plot
		infoaxis.text(0.1,0.8,'Magnitude: '+str(magnitude))
		infoaxis.text(0.1,0.6,'Lat: '+str(locationLat))
		infoaxis.text(0.1,0.4,'Lon: '+str(locationLon))
		infoaxis.text(0.1,0.2,'Depth: '+str(depth))

	def setLabels(self):
		""" Set plot attributes """
		self.ppm.axpp.set_title('Seismograms')
		if self.opts.filemode == 'pkl':
			axstk = self.axstk
			trans = transforms.blended_transform_factory(axstk.transAxes, axstk.transAxes)
			axstk.text(1,1.01,self.opts.pklfile,transform=trans, va='bottom', ha='right',color='k')
		axpp = self.ppm.axpp
		trans = transforms.blended_transform_factory(axpp.transAxes, axpp.transData)
		font = FontProperties()
		font.set_family('monospace')
		axpp.text(1.025, 0, ' '*8+'qual= CCC/SNR/COH', transform=trans, va='center', 
			color='k', fontproperties=font)

	def plotStack(self):
		""" Plot array stack and span """
		colorwave = self.opts.pppara.colorwave
		stkybase = 0
		ppstk = PickPhase(self.gsac.stkdh, self.opts,self.axstk, stkybase, colorwave, 1) 
		ppstk.plotPicks()
		ppstk.disconnectPick()
		self.ppstk = ppstk
		self.axstk.set_title('Array Stack')
		self.ppstk.stalabel.set_visible(False)
		if self.opts.ynorm == 1.0:
			self.axstk.set_ylim(stkybase-0.5, stkybase+0.5)
		self.axstk.set_yticks([stkybase])
		self.axstk.set_yticklabels([])
		self.axstk.axvline(x=0, color='k', ls=':')
		# plot legend
		pppara = self.opts.pppara
		pickLegend(self.axstk, pppara.npick, pppara.pickcolors, pppara.pickstyles, False)
		self.plotSpan()

	def plotSpan(self):
		""" Span for array stack """
		axstk = self.axstk
		self.xzoom = [axstk.get_xlim(),]
		def on_select(xmin, xmax):
			""" Mouse event: select span. """
			if self.span.visible:
				print 'span selected: %6.1f %6.1f ' % (xmin, xmax)
				xxlim = (xmin, xmax)
				axstk.set_xlim(xxlim)
				self.xzoom.append(xxlim)
				if self.opts.upylim_on:
					print ('upylim')
					ppstk.updateY(xxlim)
				axstk.figure.canvas.draw()
		pppara = self.opts.pppara
		a, col = pppara.alphatwsele, pppara.colortwsele
		mspan = pppara.minspan * self.opts.delta
		self.span = TimeSelector(axstk, on_select, 'horizontal', minspan=mspan, useblit=False,
			rectprops=dict(alpha=a, facecolor=col))

	def on_zoom(self, event):
		""" Zoom back to previous xlim when event is in event.inaxes.
		"""
		evkey = event.key
		axstk = self.axstk
		if not axstk.contains(event)[0] or evkey is None: return
		xzoom = self.xzoom
		if evkey.lower() == 'z' and len(xzoom) > 1:
			del xzoom[-1]
			axstk.set_xlim(xzoom[-1])
			print 'Zoom back to: %6.1f %6.1f ' % tuple(xzoom[-1])
			if self.opts.upylim_on:
				for pp in self.pps:
					del pp.ynorm[-1]
					setp(pp.lines[0], ydata=pp.ybase+pp.sacdh.data*pp.ynorm[-1])
			axstk.figure.canvas.draw()

	def replot(self):
		""" Replot seismograms and array stack after running iccs.
		"""
		self.ppstk.disconnect()
		self.ppstk.axpp.cla()
		self.plotStack()
		opts = self.opts
		sortSeis(self.gsac, self.opts)
		self.ppm.initIndex()
		self.ppm.replot(0)
		self.setLabels()

	def connect(self):
		""" Connect button events. """
		self.axccim = self.axs['CCIM']
		self.axccff = self.axs['CCFF']
		self.axsync = self.axs['Sync']
		self.axmccc = self.axs['MCCC']
		#self.axsac1 = self.axs['SAC1']
		self.axsac2 = self.axs['SAC2']
		self.bnccim = Button(self.axccim, 'ICCS-A')
		self.bnccff = Button(self.axccff, 'ICCS-B')
		self.bnsync = Button(self.axsync, 'Sync')
		self.bnmccc = Button(self.axmccc, 'MCCC')
		#self.bnsac1 = Button(self.axsac1, 'SAC P1')
		self.bnsac2 = Button(self.axsac2, 'SAC P2')
		self.cidccim = self.bnccim.on_clicked(self.ccim)
		self.cidccff = self.bnccff.on_clicked(self.ccff)
		self.cidsync = self.bnsync.on_clicked(self.sync)
		self.cidmccc = self.bnmccc.on_clicked(self.mccc)
		#self.cidsac1 = self.bnsac1.on_clicked(self.plot1)
		self.cidsac2 = self.bnsac2.on_clicked(self.plot2)
		self.cidpress = self.axstk.figure.canvas.mpl_connect('key_press_event', self.on_zoom)

	def disconnect(self):
		""" Disconnect button events. """
		self.bnccim.disconnect(self.cidccim)
		self.bnccff.disconnect(self.cidccff)
		self.bnsync.disconnect(self.cidsync)
		self.bnmccc.disconnect(self.cidmccc)
		self.bnsac1.disconnect(self.cidsac1)
		self.bnsac2.disconnect(self.cidsac2)
		self.axccim.cla()
		self.axccff.cla()
		self.axsync.cla()
		self.axmccc.cla()
		self.axsac1.cla()
		self.axsac2.cla()

	def syncPick(self):
		""" Sync final time pick hdrfin from array stack to all traces. 
		"""
		self.getPicks()
		tshift = self.tfin - self.tmed
		hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
		for sacdh in self.gsac.saclist:
			tfin = sacdh.gethdr(hdrmed) + tshift
			sacdh.sethdr(hdrfin, tfin)

	def syncWind(self):
		""" Sync time window relative to hdrfin from array stack to all traces. 
			Times saved to twhdrs are alway absolute.
		"""
		wh0, wh1 = self.opts.qcpara.twhdrs
		hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
		self.getWindow(hdrfin)
		twfin = self.twcorr
		for sacdh in self.gsac.saclist:
			tfin = sacdh.gethdr(hdrfin)
			th0 = tfin + twfin[0]
			th1 = tfin + twfin[1]
			sacdh.sethdr(wh0, th0)
			sacdh.sethdr(wh1, th1)
			
	def sync(self, event):
		""" Sync final time pick and time window from array stack to each trace and update current page.
		"""
		hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
		wh0, wh1 = self.opts.qcpara.twhdrs
		if self.ppstk.sacdh.gethdr(hdrfin) == -12345.:
			print '*** hfinal %s is not defined. Pick at array stack first! ***' % hdrfin
			return
		self.syncPick()
		self.syncWind()
		twfin = self.twcorr
		for pp in self.ppm.pps:
			sacdh = pp.sacdh
			tfin = sacdh.gethdr(hdrfin)
			ipk = int(hdrfin[1])
			tpk = tfin - sacdh.reftime
			pp.timepicks[ipk].set_xdata(tpk)
			th0 = tfin + twfin[0]
			th1 = tfin + twfin[1]
			pp.twindow = [th0, th1]
			pp.resetWindow()
		print '--> Sync final time picks and time window... You can now run CCFF to refine final picks.'
	
	def getWindow(self, hdr):
		""" Get time window twcorr (relative to hdr) from array stack, which is from last run. 
		"""
		ppstk = self.ppstk
		tw0, tw1 = ppstk.twindow
		t0 = ppstk.sacdh.gethdr(hdr)
		if t0 == -12345.:
			print ('Header {0:s} not defined'.format(hdr))
			return
		twcorr = [tw0-t0, tw1-t0]
		self.twcorr = twcorr

	def getPicks(self):
		""" Get time picks of stack
		"""
		hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
		self.tini = self.gsac.stkdh.gethdr(hdrini)
		self.tmed = self.gsac.stkdh.gethdr(hdrmed)
		self.tfin = self.gsac.stkdh.gethdr(hdrfin)

	def ccim(self, event):
		# running ICCS-B will erase everything you did. Make sure the user did not hit it by mistake
		tkMessageBox.showwarning("Will Erase Work!","This will erase everything you manually selected. \nAre you sure?")

		""" Run iccs with time window from final stack. Time picks: hdrini, hdrmed.
		"""
		hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
		self.cchdrs = hdrini, hdrmed
		self.getWindow(self.cchdrs[0])
		self.ccStack()
		self.getPicks()
		self.replot()

	def ccff(self, event):
		""" Run iccs with time window from final stack. Time picks: hdrfin, hdrfin.
		"""
		hdrini, hdrmed, hdrfin = self.opts.qcpara.ichdrs
		if self.gsac.stkdh.gethdr(hdrfin) == -12345.:
			print '*** hfinal %s is not defined. Sync first! ***' % hdrfin
			return
		# running ICCS-B will erase everything you did. Make sure the user did not hit it by mistake
		tkMessageBox.showwarning("Will Erase Work!","This will erase everything you manually selected. \nAre you sure?")
		self.cchdrs = hdrfin, hdrfin
		self.getWindow(self.cchdrs[0])
		self.getPicks()
		self.ccStack()
		stkdh = self.gsac.stkdh
		stkdh.sethdr(hdrini, self.tini)
		stkdh.sethdr(hdrmed, self.tmed)
		self.replot()

	def ccStack(self):
		""" 
		Call iccs.ccWeightStack. 
		Change reference time pick to the input pick before ICCS and to the output pick afterwards.
		"""
		opts = self.opts
		ccpara = opts.ccpara
		opts.ccpara.twcorr = self.twcorr
		ccpara.cchdrs = self.cchdrs
		hdr0, hdr1 = int(ccpara.cchdrs[0][1]), int(ccpara.cchdrs[1][1])
		stkdh, stkdata, quas = ccWeightStack(self.gsac.selist, self.opts)
		stkdh.selected = True
		stkdh.sethdr(opts.qcpara.hdrsel, 'True    ')
		self.gsac.stkdh = stkdh
		if opts.reltime != hdr1:
			out = '\n--> change opts.reltime from %i to %i'
			print out % (opts.reltime, hdr1)
		opts.reltime = hdr1

	def mccc(self, event):
		""" Run mccc.py  """
		gsac = self.gsac
		mcpara = self.opts.mcpara
		rcfile = mcpara.rcfile
		ipick = mcpara.ipick
		wpick = mcpara.wpick
		self.getWindow(ipick)
		timewindow = self.twcorr
		tw = timewindow[1]-timewindow[0]
		taperwindow = taperWindow(timewindow, mcpara.taperwidth)
		mcpara.timewindow = timewindow
		mcpara.taperwindow = taperwindow
		evline, mcname = eventListName(gsac.event, mcpara.phase)
		mcpara.evline = evline
		mcpara.mcname = mcname
		mcpara.kevnm = gsac.kevnm
		#rcwrite(ipick, timewindow, taperwindow, rcfile)
		solution = mccc(gsac, mcpara)
		wpk = int(wpick[1])
		if self.opts.reltime != wpk:
			out = '\n--> change opts.reltime from %i to %i'
			print out % (self.opts.reltime, wpk)
		self.opts.reltime = wpk
		self.replot()

	def plot2(self, event):
		""" Plot P2 stack of seismograms for defined time picks (ichdrs + wpick).
		"""
		opts = copy.copy(self.opts)
		twin_on = opts.twin_on
		pick_on = opts.pick_on
		reltime = opts.reltime
		ynorm = opts.ynorm
		fill = opts.fill
		selist = self.gsac.selist

		tpicks = opts.qcpara.ichdrs + [opts.mcpara.wpick,]
		npick = len(tpicks)
		tlabs = 'ABCDE'

		fig2 = figure(figsize=(9,12))
		fig2.clf()
		subplots_adjust(bottom=.05, top=0.96, left=.1, right=.97, wspace=.5, hspace=.24)
		opts.twin_on = False
		opts.pick_on = False
		ax0 = fig2.add_subplot(npick,1,1)
		axsacs = [ ax0 ] + [ fig2.add_subplot(npick,1,i+1, sharex=ax0) for i in range(1, npick) ]
		for i in range(npick):
			opts.reltime = int(tpicks[i][1])
			ax = axsacs[i]
			sacp2(selist, opts, ax)
			tt = '(' + tlabs[i] + ')'
			trans = transforms.blended_transform_factory(ax.transAxes, ax.transAxes)
			ax.text(-.05, 1, tt, transform=trans, va='center', ha='right', size=16)	

		opts.ynorm = ynorm
		opts.twin_on = twin_on
		opts.pick_on = pick_on
		opts.reltime = reltime
		opts.fill = fill
		opts.zero_on = False

		show()


def sortSeis(gsac, opts):
	'Sort seismograms by file indices, quality factors, time difference, or a given header.'
	sortby = opts.sortby
	# determine increase/decrease order
	if sortby[-1] == '-':
		sortincrease = False
		sortby = sortby[:-1]
	else:
		sortincrease = True
	opts.labelqual = True 
	# sort 
	if sortby == 'i':   # by file indices
		gsac.selist, gsac.delist = seleSeis(gsac.saclist)
	elif sortby == 't':	# by time difference
		ipick = opts.qcpara.ichdrs[0]
		wpick = 't'+str(opts.reltime)
		if ipick == wpick:
			print ('Same time pick: {0:s} and {1:s}. Exit'.format(ipick, wpick))
			sys.exit()
		gsac.selist, gsac.delist = sortSeisHeaderDiff(gsac.saclist, ipick, wpick, sortincrease)
	elif sortby.isdigit() or sortby in opts.qheaders + ['all',]: # by quality factors
		if sortby == '1' or sortby == 'ccc':
			opts.qweights = [1, 0, 0]
		elif sortby == '2' or sortby == 'snr':
			opts.qweights = [0, 1, 0]
		elif sortby == '3' or sortby == 'coh':
			opts.qweights = [0, 0, 1]
		gsac.selist, gsac.delist = sortSeisQual(gsac.saclist, opts.qheaders, opts.qweights, opts.qfactors, sortincrease)
	else: # by a given header
		gsac.selist, gsac.delist = sortSeisHeader(gsac.saclist, sortby, sortincrease)
	return


def getDataOpts():
	'Get SAC Data and Options'
	opts, ifiles = getOptions()
	pppara = PPConfig()
	qcpara = QCConfig()
	ccpara = CCConfig()
	mcpara = MCConfig()

	gsac = loadData(ifiles, opts, pppara)


	mcpara.delta = opts.delta
	opts.qheaders = qcpara.qheaders
	opts.qweights = qcpara.qweights
	opts.qfactors = qcpara.qfactors
	opts.hdrsel = qcpara.hdrsel
	opts.fstack = ccpara.fstack
	ccpara.qqhdrs = qcpara.qheaders
	ccpara.twcorr = opts.twcorr
	# find phase:
	if opts.phase is None:
		phase = findPhase(ifiles[0])
		print ('Found phase to be: ' + phase + '\n')
	else:
		phase = opts.phase
	mcpara.phase = phase
	opts.qcpara = qcpara
	opts.ccpara = ccpara
	opts.mcpara = mcpara
	opts.pppara = pppara
	# more options:
	opts.upylim_on = False
	opts.twin_on = True
	opts.sort_on = True
	opts.pick_on = True
	opts.zero_on = False
	opts.nlab_on = True
	opts.ynormtwin_on = True
	#checkCoverage(gsac, opts)
	initQual(gsac.saclist, opts.hdrsel, opts.qheaders)
	return gsac, opts



def getAxes(opts):
	""" Get axes for plotting """
	fig = figure(figsize=(13, 12.5))
	backend = get_backend().lower()
	if backend == 'tkagg':
		get_current_fig_manager().window.wm_geometry("1100x1050+700+0")
	rcParams['legend.fontsize'] = 10

	rectseis = [0.12, 0.04, 0.66, 0.82]
	rectfstk = [0.12, 0.89, 0.66, 0.08]
	rectinfo = [0.86, 0.89, 0.12, 0.09]

	xx = 0.06
	yy = 0.04
	xm = 0.02
	dy = 0.05
	y2 = rectfstk[1] + rectfstk[3] - yy
	yccim = y2 
	ysync = y2 - dy*1
	yccff = y2 - dy*2
	ymccc = y2 - dy*3
	y1 = ymccc - 1.5*dy

	yfron = y1 - dy*0
	yprev = y1 - dy*1
	ynext = y1 - dy*2
	ysave = y1 - dy*3
	yquit = y1 - dy*4
	ysac2 = yquit - dy*1.5

	rectfron = [xm, yfron, xx, yy]
	rectprev = [xm, yprev, xx, yy]
	rectnext = [xm, ynext, xx, yy]
	rectsave = [xm, ysave, xx, yy]
	rectquit = [xm, yquit, xx, yy]
	rectccim = [xm, yccim, xx, yy]
	rectsync = [xm, ysync, xx, yy]
	rectccff = [xm, yccff, xx, yy]
	rectmccc = [xm, ymccc, xx, yy]
	rectsac2 = [xm, ysac2, xx, yy]

	axs = {}
	axs['Seis'] = fig.add_axes(rectseis)
	axs['Fstk'] = fig.add_axes(rectfstk, sharex=axs['Seis'])
	axs['Info'] = fig.add_axes(rectinfo)

	axs['Fron'] = fig.add_axes(rectfron)
	axs['Prev'] = fig.add_axes(rectprev)
	axs['Next'] = fig.add_axes(rectnext)
	axs['Save'] = fig.add_axes(rectsave)
	axs['Quit'] = fig.add_axes(rectquit)
	axs['CCIM'] = fig.add_axes(rectccim)
	axs['Sync'] = fig.add_axes(rectsync)
	axs['CCFF'] = fig.add_axes(rectccff)
	axs['MCCC'] = fig.add_axes(rectmccc)
	axs['SAC2'] = fig.add_axes(rectsac2)

	return axs


def main():
	gsac, opts = getDataOpts()
	axs = getAxes(opts)
	ppmm = PickPhaseMenuMore(gsac, opts, axs)
	fmt = 'pdf'
	fmt = 'png'
	if opts.savefig:
		if opts.pklfile is None:
			fignm = 'ttpick.' + fmt
		else:
			fignm = opts.pklfile + '.' + fmt
		savefig(fignm, format=fmt, dpi=300)
	else:
		show()

if __name__ == "__main__":
	main()


