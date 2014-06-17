import matplotlib
matplotlib.rcParams['backend'] = "TkAgg"

import matplotlib.pyplot as py
from mpl_toolkits.basemap import Basemap

def plot_stations():
	"""
	lower-left/upper-right corners for the cascades domain.
	"""
	minLat = 40
	minLon = -123
	maxLat = 47
	maxLon = -120

	"""
	Central lat/lon coordinates.
	"""
	centerLat = 0.5 * (minLat + maxLat)
	centerLon = 0.5 * (minLon + maxLon)

	"""make the basemap for cascades region"""
	m = Basemap(llcrnrlon=minLon, llcrnrlat=minLat, 
	            urcrnrlon=maxLon, urcrnrlat= maxLat,
	            resolution='c',
	            area_thresh=100.,projection='lcc',
	            lat_0=centerLat, lon_0=centerLon)

	m.drawstates()
	m.drawcountries()
	m.drawcoastlines()        

	"""attempt to plot pointshere"""
	m.scatter(-122, 45, s=50, color='k', latlon=True)   

	m.drawmapboundary(fill_color='#99ffff')

	"""show the map"""
	py.show()