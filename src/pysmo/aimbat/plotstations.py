import matplotlib
matplotlib.rcParams['backend'] = "TkAgg"
import math, sys, os
import matplotlib.pyplot as py
from mpl_toolkits.basemap import Basemap
import numpy as np

class PlotStations:

	def __init__(self,  plotname, gsac):
		self.plotname = plotname
		self.saclist = gsac.saclist
		self.selist = gsac.selist
		self.delist = gsac.delist

		self.plot_stations(gsac)

	def plot_stations(self, gsac):
		figStation = py.figure('SeismoStations', figsize=(16, 12))
		figStation.suptitle('Seismo Stations', fontsize=20)

		# lower-left/upper-right corners for the cascades domain.
		minLat, minLon, maxLat, maxLon = self.bounding_rectangle()

		# Central lat/lon coordinates.
		centerLat = 0.5 * (minLat + maxLat)
		centerLon = 0.5 * (minLon + maxLon)

		#make the basemap for cascades region
		ax = Basemap(llcrnrlon=minLon, llcrnrlat=minLat, 
		            urcrnrlon=maxLon, urcrnrlat= maxLat,
		            resolution='i',
		            area_thresh=1000., projection='lcc',
		            lat_0=centerLat, lon_0=centerLon)

		ax.drawstates()
		ax.drawcountries()
		ax.drawcoastlines()   

		py.title(self.plotname)  
		py.xlabel('Black triangles: deleted stations\n Red Points: selected stations')   

		# plot stations
		if hasattr(gsac, 'delay_times'):
			self.plot_selected_stations_color_delay_times(ax, gsac.delay_times)
		else:
			self.plot_selected_stations(ax)
		self.plot_deleted_stations(ax)

		figStation.canvas.mpl_connect('pick_event', self.show_station_name)

		self.figStation = figStation
		self.ax = ax

		py.show()


	def show_station_name(self, event):
		nearest = 1000000000
		clicked_lon = event.mouseevent.xdata
		clicked_lat = event.mouseevent.ydata
		station_name = ''
		for sacdh in self.saclist:
			(xpt, ypt) = self.ax(sacdh.stlo, sacdh.stla)
			dist = math.sqrt((xpt-clicked_lon)**2+(ypt-clicked_lat)**2)
			if dist<nearest:
				station_name = sacdh.netsta
				nearest=dist
		print 'Nearest Station selected: %s' % station_name

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

	def plot_selected_stations(self, axes_handle):
		selected_lon = [] 
		selected_lat = []
		for sacdh in self.selist:
			selected_lon.append(sacdh.stlo)
			selected_lat.append(sacdh.stla)
		axes_handle.scatter(selected_lon, selected_lat, s=50, latlon=True, marker='o', c='r', picker=True)

	def plot_selected_stations_color_delay_times(self, axes_handle, delay_times):
		selected_lon = [] 
		selected_lat = []
		for sacdh in self.selist:
			selected_lon.append(sacdh.stlo)
			selected_lat.append(sacdh.stla)
		cm = py.cm.get_cmap('seismic')
		sc = axes_handle.scatter(selected_lon, selected_lat, s=50, latlon=True, marker='o', c=delay_times, picker=True, cmap=cm)
		py.colorbar(sc)

	def plot_deleted_stations(self, axes_handle):
		deleted_lon = [] 
		deleted_lat = []
		for sacdh in self.delist:
			deleted_lon.append(sacdh.stlo)
			deleted_lat.append(sacdh.stla)
		axes_handle.scatter(deleted_lon, deleted_lat, s=50, latlon=True, marker='^', c='k', picker=True)












