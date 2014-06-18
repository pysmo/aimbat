import matplotlib
matplotlib.rcParams['backend'] = "TkAgg"

import matplotlib.pyplot as py
from mpl_toolkits.basemap import Basemap
import numpy as np

class PlotStations:
	"""
	solution: length(selist) x 4 array
			  columns correspond to: 
			   ------------ ----- ---------- --------
			  | mccc delay | std | cc coeff | cc std |
			   ------------ ----- ---------- -------- 
	"""
	def __init__(self, mcpara, saclist, selist, so_LonLat, solution, delist):
		self.mcpara = mcpara
		self.saclist = saclist
		self.selist = selist
		self.so_LonLat = so_LonLat
		self.solution = solution
		self.delist = delist

		self.plot_stations()

	def plot_stations(self):
		figStation = py.figure('SeismoStations')

		# lower-left/upper-right corners for the cascades domain.
		minLat, minLon, maxLat, maxLon = self.bounding_rectangle()

		# Central lat/lon coordinates.
		centerLat = 0.5 * (minLat + maxLat)
		centerLon = 0.5 * (minLon + maxLon)

		#make the basemap for cascades region
		ax = Basemap(llcrnrlon=minLon, llcrnrlat=minLat, 
		            urcrnrlon=maxLon, urcrnrlat= maxLat,
		            resolution='c',
		            area_thresh=100.,projection='lcc',
		            lat_0=centerLat, lon_0=centerLon)

		ax.drawstates()
		ax.drawcountries()
		ax.drawcoastlines()   

		py.title(self.mcpara.mcname.split('.mcp')[0])     

		# plot stations
		self.plot_stations_colorByVariable(ax, self.solution[:,0], 'MCCC Delay (s)')
		self.plot_deleted_stations(ax)

		py.show()

	def bounding_rectangle(self):
		all_station_lats = []
		all_station_lons = []
		for sacdh in self.saclist:
			all_station_lats.append(sacdh.stla)
			all_station_lons.append(sacdh.stlo)

		minLat = min(all_station_lats)-0.5
		minLon = min(all_station_lons)-0.5
		maxLat = max(all_station_lats)+0.5
		maxLon = max(all_station_lons)+0.5

		return minLat, minLon, maxLat, maxLon

	def plot_stations_colorByVariable(self, axes_handle, colorByVar, colorbarTitle):
		# plot selected stations and color by variable passed in
		axes_handle.scatter(self.so_LonLat[:,0], self.so_LonLat[:,1], latlon=True, marker='o', c=colorByVar, cmap=py.cm.RdBu_r, vmin=min(colorByVar), vmax=max(colorByVar))

		# add colorbar
		cb = axes_handle.colorbar()
		cb.set_label(colorbarTitle) 

	def plot_deleted_stations(self, axes_handle):
		deleted_lon = [] 
		deleted_lat = []
		for sacdh in self.delist:
			deleted_lon.append(sacdh.stlo)
			deleted_lat.append(sacdh.stla)
		axes_handle.scatter(deleted_lon, deleted_lat, latlon=True, marker='>', c='k')












