import matplotlib
matplotlib.rcParams['backend'] = "TkAgg"
import math
import matplotlib.pyplot as plt
import numpy as np
try:
 from mpl_toolkits.basemap import Basemap
 basemapthere=True
except:
 basemapthere=False

class PlotStations:

    def __init__(self,  plotname, gsac):
        self.plotname = plotname
        self.saclist = gsac.saclist
        self.selist = gsac.selist
        self.delist = gsac.delist

        self.plot_stations(gsac)

    def plot_stations(self, gsac):
        figStation = plt.figure('SeismoStations', figsize=(16, 12))
        figStation.suptitle('Seismic Stations', fontsize=20)

        # lower-left/upper-right corners for the cascades domain.
        minLat, minLon, maxLat, maxLon = self.bounding_rectangle()

        # Central lat/lon coordinates.
        centerLat = 0.5 * (minLat + maxLat)
        centerLon = 0.5 * (minLon + maxLon)
        
        qLat = min(abs(minLat),abs(maxLat))
        h = 1.2*6370997.*np.radians(maxLat-minLat)
        w = 1.1*6370997.*np.radians(maxLon-minLon)*np.cos(np.radians(qLat))

        #make the basemap 
        if basemapthere:
        #ax = Basemap(llcrnrlon=minLon, llcrnrlat=minLat, 
        #            urcrnrlon=maxLon, urcrnrlat= maxLat,
            ax = Basemap(width=w,
                height=h, 
                resolution='i',
                area_thresh=1000., projection='lcc',
                lat_0=centerLat, lon_0=centerLon)
            ax.drawstates()
            ax.drawcountries()
            ax.drawcoastlines()   
            plt.xlabel('Black triangles: deleted stations\n Red Points: selected stations')   
        else:
            simplexmin=minLon-1.
            simplexmax=maxLon+1.
            simpleymin=minLat-1.
            simpleymax=maxLat+1.
            ax = figStation.add_subplot(111)
            ax.axis([simplexmin,simplexmax,simpleymin,simpleymax])
            plt.xlabel('Black triangles: deleted stations\n Red Points: selected stations\n No coastline because Basemap module not found')   

            plt.title(self.plotname)  

        # plot stations
        if hasattr(gsac, 'delay_times'):
            self.plot_selected_stations_color_delay_times(ax, gsac.delay_times)
        else:
            self.plot_selected_stations(ax)
        self.plot_deleted_stations(ax)

        figStation.canvas.mpl_connect('pick_event', self.show_station_name)

        self.figStation = figStation
        self.ax = ax

        plt.show()


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
        print(('Nearest Station selected: %s' % station_name))

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
        if basemapthere:
          axes_handle.scatter(selected_lon, selected_lat, s=50, latlon=True, marker='o', c='r', picker=True)
        else:
          axes_handle.scatter(selected_lon, selected_lat, s=50, marker='o', c='r', picker=True)

    def plot_selected_stations_color_delay_times(self, axes_handle, delay_times):
        selected_lon = [] 
        selected_lat = []
        for sacdh in self.selist:
            selected_lon.append(sacdh.stlo)
            selected_lat.append(sacdh.stla)
        cm = plt.cm.get_cmap('seismic')
        if basemapthere:
          sc = axes_handle.scatter(selected_lon, selected_lat, s=50, latlon=True, marker='o', c=delay_times, picker=True, cmap=cm)
        else:
          sc = axes_handle.scatter(selected_lon, selected_lat, s=50, marker='o', c=delay_times, picker=True, cmap=cm)
        plt.colorbar(sc)

    def plot_deleted_stations(self, axes_handle):
        deleted_lon = [] 
        deleted_lat = []
        for sacdh in self.delist:
            deleted_lon.append(sacdh.stlo)
            deleted_lat.append(sacdh.stla)
        if basemapthere:
           axes_handle.scatter(deleted_lon, deleted_lat, s=50, latlon=True, marker='^', c='k', picker=True)
        else:
           axes_handle.scatter(deleted_lon, deleted_lat, s=50, marker='^', c='k', picker=True)

