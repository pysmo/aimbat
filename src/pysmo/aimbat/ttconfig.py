#!/usr/bin/env python
#------------------------------------------------
# Filename: ttconfig.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009-2012 Xiaoting Lou
#------------------------------------------------
"""
Python module for setting up default parameters for SACPLOT (PlotPhase and PickPhase), ICCS, MCCC and QCTRL.
Create parser for command line arguments and options.


:copyright:
    Xiaoting Lou

:license:
    GNU General Public License, Version 3 (GPLv3) 
    http://www.gnu.org/licenses/gpl.html
"""


import os
from configparser    import ConfigParser
from optparse        import OptionParser


def getDefaults():
    """ 
    Get default parameters from a configuration file: ttdefaults.conf. 
    The file is searched in this order:
        (0) the current working directory
        (1) home directory
        (2) environment variable TTCONFIG 
        (3) the same directory as this program.
    """
    conf = 'TTCONFIG'
    def0 = 'ttdefaults.conf'
    def1 = os.environ['HOME'] + '/.aimbat/' + def0
    def3 = os.path.dirname(__file__) + '/' + def0
    if os.path.isfile(def0):
        defaults = def0
    elif os.path.isfile(def1):
        defaults = def1
    elif conf in os.environ:
        defaults = os.environ[conf]
    else:
        defaults = def3
    return defaults

defaults = getDefaults()
print('Read configuration file: ' + defaults)

class PPConfig:
    """    Class for SAC PlotPhase and PickPhase configurations.
    """
    def __init__(self):
        config = ConfigParser()
        defaults = getDefaults()
        config.read(defaults)
        # SAC headers for time window, trace selection, and quality factors
        self.twhdrs = config.get('sachdrs', 'twhdrs').split()
        self.hdrsel = config.get('sachdrs', 'hdrsel')
        self.qfactors = config.get('sachdrs', 'qfactors').split()
        self.qheaders = config.get('sachdrs', 'qheaders').split()
        self.qweights = [ float(val)  for val in config.get('sachdrs', 'qweights').split() ]
        # SAC plots
        self.figsize = [ float(val)  for val in config.get('sacplot', 'figsize').split() ]
        self.rectseis = [ float(val)  for val in config.get('sacplot', 'rectseis').split() ]
        self.colorwave = config.get('sacplot', 'colorwave')
        self.colorwavedel = config.get('sacplot', 'colorwavedel')
        self.colortwfill = config.get('sacplot', 'colortwfill')
        self.colortwsele = config.get('sacplot', 'colortwsele')
        self.alphatwfill = config.getfloat('sacplot', 'alphatwfill')
        self.alphatwsele = config.getfloat('sacplot', 'alphatwsele')
        self.alphawave = config.getfloat('sacplot', 'alphawave')
        self.npick = config.getint('sacplot', 'npick')
        self.pickcolors = config.get('sacplot', 'pickcolors')
        self.pickstyles = config.get('sacplot', 'pickstyles').split()
        self.minspan = config.getint('sacplot', 'minspan')
        self.srate = config.getfloat('sacplot', 'srate')
        self.tapertype = config.get('signal', 'tapertype')
        self.taperwidth = config.getfloat('signal', 'taperwidth')
        # SAC headers for filter 
        self.fhdrApply = config.get('signal', 'fhdrApply')
        self.fhdrBand = config.get('signal', 'fhdrBand')
        self.fhdrRevPass = config.get('signal', 'fhdrRevPass')
        self.fhdrLowFreq = config.get('signal', 'fhdrLowFreq')
        self.fhdrHighFreq = config.get('signal', 'fhdrHighFreq')
        self.fhdrOrder = config.get('signal', 'fhdrOrder')
        # default values for filter 
        self.fvalApply = config.getint('signal', 'fvalApply')
        self.fvalBand = config.get('signal', 'fvalBand')
        self.fvalRevPass = config.getint('signal', 'fvalRevPass')
        self.fvalLowFreq = config.getfloat('signal', 'fvalLowFreq')
        self.fvalHighFreq = config.getfloat('signal', 'fvalHighFreq')
        self.fvalOrder = config.getint('signal', 'fvalOrder')



class QCConfig:
    """ Class for QCTRL configuration.
    """
    def __init__(self):
        defaults = getDefaults()
        config = ConfigParser()
        config.read(defaults)
        # SAC headers for time window, trace selection, and quality factors
        self.twhdrs = config.get('sachdrs', 'twhdrs').split()
        self.hdrsel = config.get('sachdrs', 'hdrsel')
        self.qfactors = config.get('sachdrs', 'qfactors').split()
        self.qheaders = config.get('sachdrs', 'qheaders').split()
        self.qweights = [ float(val)  for val in config.get('sachdrs', 'qweights').split() ] 
        # SAC headers for ICCS time picks
        self.ichdrs = config.get('sachdrs', 'ichdrs').split()
        # plots
        self.colorwave = config.get('sacplot', 'colorwave')
        self.colortwfill = config.get('sacplot', 'colortwfill')
        self.colortwsele = config.get('sacplot', 'colortwsele')
        self.alphatwfill = config.get('sacplot', 'alphatwfill')
        self.alphatwsele = config.get('sacplot', 'alphatwsele')
        self.npick = config.getint('sacplot', 'npick')
        self.pickcolors = config.get('sacplot', 'pickcolors')
        self.pickstyles = config.get('sacplot', 'pickstyles').split()
        self.minspan = config.getint('sacplot', 'minspan')
        self.fstack = config.get('iccs', 'fstack')


class CCConfig:
    """ Class for ICCS configuration.
    """
    def __init__(self):
        defaults = getDefaults()
        config = ConfigParser()
        config.read(defaults)
        self.tapertype = config.get('signal', 'tapertype')
        self.taperwidth = config.getfloat('signal', 'taperwidth')
        self.maxiter = config.getint('iccs', 'maxiter')
        self.convepsi = config.getfloat('iccs', 'convepsi')
        self.convtype = config.get('iccs', 'convtype')
        self.stackwgt = config.get('iccs', 'stackwgt')
        self.srate = config.getfloat('iccs', 'srate')
        self.fstack = config.get('iccs', 'fstack')
        # SAC headers for time window, trace selection, and quality factors
        self.twhdrs = config.get('sachdrs', 'twhdrs').split()
        self.hdrsel = config.get('sachdrs', 'hdrsel')
        self.qfactors = config.get('sachdrs', 'qfactors').split()
        self.qheaders = config.get('sachdrs', 'qheaders').split()
        self.qweights = [ float(val)  for val in config.get('sachdrs', 'qweights').split() ] 
        # SAC headers for ICCS time picks
        self.ichdrs = config.get('sachdrs', 'ichdrs').split()
        # Choose a xcorr module and function
        self.shift = config.getint('iccs', 'shift')
        modu = config.get('iccs', 'xcorr_modu')
        func = config.get('iccs', 'xcorr_func')
        cmd1a = 'from  {:s} import {:s}'.format(modu, func)
        cmd1r = 'from .{:s} import {:s}'.format(modu, func)
        cmd2 = 'self.xcorr = {:s}'.format(func)
        try:
            exec(cmd1r)
        except:
            exec(cmd1a)
        exec(cmd2)
        print('Using {:s}.{:s} as cross-correlation method for ICCS'.format(modu, func))
        self.xcorr_modu = modu
        self.xcorr_func = func

class MCConfig:
    """ Class for MCCC configuration. 
    """
    def __init__(self):
        defaults = getDefaults()
        config = ConfigParser()
        config.read(defaults)
        self.tapertype = config.get('signal', 'tapertype')
        self.taperwidth = config.getfloat('signal', 'taperwidth')
        self.lsqr = config.get('mccc', 'lsqr')
        self.ofilename = config.get('mccc', 'ofilename')
        self.tapertype = config.get('signal', 'tapertype')
        self.taperwidth = config.getfloat('signal', 'taperwidth')
        self.exwt = config.getfloat('mccc', 'extraweight')
        self.srate = config.getfloat('mccc', 'srate')
        self.rcfile = config.get('mccc', 'rcfile')
        self.evlist = config.get('mccc', 'evlist')
        self.fstack = config.get('iccs', 'fstack')
        # SAC headers for time window, trace selection, and quality factors
        self.twhdrs = config.get('sachdrs', 'twhdrs').split()
        self.hdrsel = config.get('sachdrs', 'hdrsel')
        # SAC headers for MCCC time picks
        self.ipick, self.wpick = config.get('sachdrs', 'mchdrs').split()
        # Choose a xcorr module and function
        self.shift = config.getint('mccc', 'shift')
        modu = config.get('mccc', 'xcorr_modu')
        func = config.get('mccc', 'xcorr_func')
        cmd1a = 'from  {:s} import {:s}'.format(modu, func)
        cmd1r = 'from .{:s} import {:s}'.format(modu, func)
        cmd2 = 'self.xcorr = {:s}'.format(func)
        try:
            exec(cmd1r)
        except:
            exec(cmd1a)
        exec(cmd2)
        print('Using {:s}.{:s} as cross-correlation method for MCCC'.format(modu, func))
        self.xcorr_modu = modu
        self.xcorr_func = func

def getParser():
    """ Parse command line arguments and options. """
    reltime = -1
    fill = 0 
    ynorm = 2.0
    usage = "Usage: %prog [options] <sacfile(s) or a picklefile>"
    parser = OptionParser(usage=usage)
    parser.set_defaults(reltime=reltime)
    parser.set_defaults(fill=fill)
    parser.set_defaults(ynorm=ynorm)

    parser.add_option('-f', '--fill', dest='fill', type = 'int',
        help='Fill/shade seismogram with positive (1) or negative (-1) signal. Default is none ({:d}).'.format(fill))
    parser.add_option('-r', '--relative-time',  dest='reltime', type='int',
        help='Relative time to a time pick header (t0-t9). Default is {:d}, None, use absolute time.'.format(reltime))
    parser.add_option('-u', '--upylim', action="store_true", dest='upylim_on',
        help='Update ylim every time of zooming in.')
    parser.add_option('-k', '--pick', action="store_true", dest='pick_on',
        help='Plot time picks.')
    parser.add_option('-w', '--twin', action="store_true", dest='twin_on',
        help='Plot time window.')
    parser.add_option('-x', '--xlimit',  dest='xlimit', type='float', nargs=2, 
        help='Left and right x-axis limit to plot.')
    parser.add_option('-y', '--ynorm',  dest='ynorm', type='float',
        help='Normalize ydata of seismograms. Effective only for positive number. Default is {:f}.'.format(ynorm))
    parser.add_option('-Y', '--ynormtwin', action="store_true", dest='ynormtwin_on',
        help='Normalize seismogram within time window.')
    parser.add_option('-S', '--srate',  dest='srate', type='float',
        help='Sampling rate to load SAC data. Default is None, use the original rate of first file.')

    return parser


