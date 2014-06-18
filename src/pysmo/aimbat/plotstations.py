import matplotlib
matplotlib.rcParams['backend'] = "TkAgg"

import matplotlib.pyplot as py
from mpl_toolkits.basemap import Basemap

class PlotStations:
	
	def __init__(self, saclist, selist, so_LonLat, solution, delist):
		self.saclist = saclist
		self.selist = selist
		self.so_LonLat = so_LonLat
		self.solution = solution
		self.delist = delist

		self.plot_stations()

	def plot_stations(self):
		figStation = py.figure('SeismoStations')

		# lower-left/upper-right corners for the cascades domain.
		minLat = 40
		minLon = -123
		maxLat = 47
		maxLon = -120

		# Central lat/lon coordinates.
		centerLat = 0.5 * (minLat + maxLat)
		centerLon = 0.5 * (minLon + maxLon)

		"""plot the delay times"""
		#make the basemap for cascades region
		ax1 = figStation.add_subplot(211)
		ax1 = Basemap(llcrnrlon=minLon, llcrnrlat=minLat, 
		            urcrnrlon=maxLon, urcrnrlat= maxLat,
		            resolution='c',
		            area_thresh=100.,projection='lcc',
		            lat_0=centerLat, lon_0=centerLon)

		ax1.drawstates()
		ax1.drawcountries()
		ax1.drawcoastlines()        

		#attempt to plot pointshere
		ax1.scatter(-122, 45, s=50, color='k', latlon=True)   

		ax1.drawmapboundary(fill_color='#99ffff')

		ax2 = figStation.add_subplot(212)

		# show the map
		py.show()

