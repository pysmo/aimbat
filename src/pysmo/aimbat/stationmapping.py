#!/usr/bin/env python
#------------------------------------------------
# Filename: stationmapping.py
#   Author: Arnav Sankaran
#    Email: arnavsankaran@gmail.com
#
# Copyright (c) 2016 Arnav Sankaran
#------------------------------------------------
"""
Python module for mapping station with the help of GMT scripts.

:copyright:
	Arnav Sankaran

:license:
	GNU General Public License, Version 3 (GPLv3) 
	http://www.gnu.org/licenses/gpl.html
"""

import subprocess
import os

class StationMapper(object):
	def __init__(self, sacgroup):
		self.sacgroup = sacgroup
		self.selats = []
		self.selons = []
		self.delats = []
		self.delons = []

	def start(self):
		self.extractData()
		selectedPath, deselectedPath = self.writeToFile()
		self.plotData(selectedPath, deselectedPath)

	def extractData(self):
		for sacdh in self.sacgroup.selist:
			self.selats.append(sacdh.stla)
			self.selons.append(sacdh.stlo)
		for sacdh in self.sacgroup.delist:
			self.delats.append(sacdh.stla)
			self.delons.append(sacdh.stlo)

	def writeToFile(self):
		selectedLatLon = ''
		for lat, lon in zip(self.selats, self.selons):
			selectedLatLon += str(lat) + ' ' + str(lon) + '\n'
		deselectedLatLon = ''
		for lat, lon in zip(self.delats, self.delons):
			deselectedLatLon += str(lat) + ' ' + str(lon) + '\n'

		selectedPath = os.path.join(os.getcwd(), 'selectedstations.gmt')
		deselectedPath = os.path.join(os.getcwd(), 'deselectedstations.gmt')

		with open(selectedPath, 'w+') as tmpfile:
			tmpfile.write(selectedLatLon)
		with open(deselectedPath, 'w+') as tmpfile:
			tmpfile.write(deselectedLatLon)

		return selectedPath, deselectedPath

	def plotData(self, selectedPath, deselectedPath):
		lats = self.selats + self.delats
		lons = self.selons + self.delons

		args = [0, 0, 0, 0, 0, 0, 0, 0]

		args[0] = min(lons) - 1.0
		args[1] = max(lons) + 1.0
		args[2] = min(lats) - 1.0
		args[3] = max(lats) + 1.0

		args[4] = (min(lons) + max(lons)) / 2
		args[5] = (min(lats) + max(lats)) / 2
		args[6] = min(lats)
		args[7] = max(lats)


		__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
		if os.name == 'nt':
			subprocess.call([os.path.join(__location__, 'stationmapper.bat')] + [selectedPath, deselectedPath] + [str(a) for a in args])
		else:
			subprocess.call(['/bin/bash', os.path.join(__location__, 'stationmapper.sh')] + [selectedPath, deselectedPath] + [str(a) for a in args])
