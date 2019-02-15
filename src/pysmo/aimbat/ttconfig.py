#!/usr/bin/env python
#------------------------------------------------
# Filename: ttconfig.py
#   Author: Xiaoting Lou
#    Email: xlou@u.northwestern.edu
#
# Copyright (c) 2009-2012 Xiaoting Lou
#------------------------------------------------
"""
Parameter Configuration
=======================

.. ############################################################################ ..
.. #                           MATPLOTLIB BACKEND                             # ..
.. ############################################################################ ..

Backend
-------

`Matplotlib <http://matplotlib.org/contents.html>`_ works with six GUI (Graphical User Interface) toolkits:

#. WX
#. Tk
#. Qt(4)
#. FTK
#. Fltk
#. macosx

The GUI of AIMBAT uses the following to support interactive plotting:

#. `GUI neutral widgets <http://matplotlib.org/api/widgets_api.html>`_
#. `GUI neutral event handling API (Application Programming Interface) <http://matplotlib.org/users/event_handling.html>`_

AIMBAT uses the default toolkit ``Tk`` and backend ``TkAgg``.

Visit these pages for an `explanation of the backend <http://matplotlib.org/faq/usage_faq.html#what-is-a-backend>`_ and `how to customize it <http://matplotlib.org/users/customizing.html#customizing-matplotlib>`_.

.. ############################################################################ ..
.. #                           MATPLOTLIB BACKEND                             # ..
.. ############################################################################ ..







.. ############################################################################ ..
.. #                           CONFIGURATION FILE                             # ..
.. ############################################################################ ..

Configuration File
------------------

Other parameters for the package can be set up by a configuration file ``ttdefaults.conf``, which is interpreted by the module ConfigParser. This configuration file is searched in the following order:

#. file ``ttdefaults.conf`` in the current working directory
#. file ``.aimbat/ttdefaults.conf`` in your ``HOME`` directory
#. a file specified by environment variable ``TTCONFIG``
#. file ``ttdefaults.conf`` in the directory where AIMBAT is installed

Python scripts in the ``<pkg-install-dir>/pysmo-aimbat-0.1.2/scripts`` can be executed from the command line. The command line arguments are parsed by the optparse module to improve the scripts' exitability. If conflicts existed, the command line options override the default parameters given in the configuration file ``ttdefaults.conf``. Run the scripts with the ``-h`` option for the usage messages.

Example of AIMBAT configuration file `ttdefaults.conf`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------------------+---------------------------------------------------------------+
| ttdefaults.conf              | Description                                                   |
+==============================+===============================================================+
| [sacplot]                    |                                                               |
+------------------------------+---------------------------------------------------------------+
| colorwave = blue             | Color of waveform                                             |
+------------------------------+---------------------------------------------------------------+
| colorwavedel = gray          | Color of waveform which is deselected                         |
+------------------------------+---------------------------------------------------------------+
| colortwfill = green	       | Color of time window fill                                     |
+------------------------------+---------------------------------------------------------------+
| colortwsele = red            | Color of time window selection                                |
+------------------------------+---------------------------------------------------------------+
| alphatwfill = 0.2            | Transparency of time window fill                              |
+------------------------------+---------------------------------------------------------------+
| alphatwsele = 0.6            | Transparency of time window selection                         |
+------------------------------+---------------------------------------------------------------+
| npick = 6                    | Number of time picks (plot picks: t0-t5)                      |
+------------------------------+---------------------------------------------------------------+
| pickcolors = kmrcgyb         | Colors of time picks                                          |
+------------------------------+---------------------------------------------------------------+
| pickstyles                   | Line styles of time picks (use second one if ran out of color)|
+------------------------------+---------------------------------------------------------------+
| figsize = 8 10               | Figure size for `plotphase.py`                                |
+------------------------------+---------------------------------------------------------------+
| rectseis = 0.1 0.06 0.76 0.9 | Axes rectangle size within the figure                         |
+------------------------------+---------------------------------------------------------------+
| minspan = 5                  | Minimum sample points for SpanSelector to select time window  |
+------------------------------+---------------------------------------------------------------+
|srate = -1                    | Sample rate for loading SAC data.                             |
|                              | Read from first file if srate < 0                             |
+------------------------------+---------------------------------------------------------------+

+---------------------------------+--------------------------------------------------+
| [sachdrs]                                                                          |
+=================================+==================================================+
| twhdrs = user8 user9            | SAC headers for time window beginning and ending |
+---------------------------------+--------------------------------------------------+
| ichdrs = t0 t1 t2               | SAC headers for ICCS time picks                  |
+---------------------------------+--------------------------------------------------+
| mchdrs = t2 t3                  | SAC headers for MCCC input and output time picks |
+---------------------------------+--------------------------------------------------+
| hdrsel = kuser0                 | SAC header for seismogram selection status       |
+---------------------------------+--------------------------------------------------+
| qfactors = ccc snr coh          | Quality factors: cross-correlation coefficient,  |
|                                 | signal-to-noise ratio, time domain coherence     |
+---------------------------------+--------------------------------------------------+
| qheaders = user0 user1 user2    | SAC Headers for quality factors                  |
+---------------------------------+--------------------------------------------------+
| qweights = 0.3333 0.3333 0.3333 | Weights for quality factors                      |
+---------------------------------+--------------------------------------------------+

+-------------------------+---------------------------------------------------------------------+
| [iccs] or Align/Refine  |                                                                     |
+=========================+=====================================================================+
| srate = -1              | Sample rate for loading SAC data. Read from first file if srate < 0 |
+-------------------------+---------------------------------------------------------------------+
| xcorr_modu = xcorrf90   | Module for calculating cross-correlation:                           |
|                         | xcorr for Numpy or xcorrf90 for Fortran                             |
+-------------------------+---------------------------------------------------------------------+
| xcorr_func = xcorr_fast | Function for calculating cross-correlation                          |
+-------------------------+---------------------------------------------------------------------+
| shift = 10              | Sample shift for running coarse cross-correlation                   |
+-------------------------+---------------------------------------------------------------------+
| maxiter = 10            | Maximum number of iteration                                         |
+-------------------------+---------------------------------------------------------------------+
| convepsi = 0.001        | Convergence criterion: epsilon                                      |
+-------------------------+---------------------------------------------------------------------+
|convtype = coef    	  | Type of convergence criterion: coef for correlation coefficient,    |
|                         | or resi for residual                                                |
+-------------------------+---------------------------------------------------------------------+
| stackwgt = coef         | Weight each trace when calculating array stack                      |
+-------------------------+---------------------------------------------------------------------+
| fstack = fstack.sac     | SAC file name for the array stack                                   |
+-------------------------+---------------------------------------------------------------------+

+---------------------------+------------------------------------------------------------------+
| [mccc]                    |                                                                  |
+===========================+==================================================================+
| srate = -1                | Sample rate for loading SAC data.                                |
|                           | Read from first file if srate :math:`< 0`                        |
+---------------------------+------------------------------------------------------------------+
| ofilename = mc            | Output file name of MCCC.                                        |
+---------------------------+------------------------------------------------------------------+
| xcorr_modu = xcorrf90	    | Module for calculating cross-correlation:                        |
|                           | xcorr for Numpy or xcorrf90 for Fortran                          |
+---------------------------+------------------------------------------------------------------+
| xcorr_func = xcorr_faster | Function for calculating cross-correlation                       |
+---------------------------+------------------------------------------------------------------+
| shift = 10                | Sample shift for running coarse cross-correlation                |
+---------------------------+------------------------------------------------------------------+
| extraweight = 1000        | Weight for the zero-mean equation in MCCC weighted lsqr solution |
+---------------------------+------------------------------------------------------------------+
| lsqr = nowe               | Type of lsqr solution: no weight                                 |
+---------------------------+------------------------------------------------------------------+
| #lsqr = lnco              | Type of lsqr solution: weighted by correlation coefficient,      |
|                           | solved by lapack                                                 |
+---------------------------+------------------------------------------------------------------+
| #lsqr = lnre              | Type of lsqr solution: weighted by residual, solved by lapack    |
+---------------------------+------------------------------------------------------------------+
| rcfile = .mcccrc          | Configuration file for MCCC parameters (deprecated)              |
+---------------------------+------------------------------------------------------------------+
| evlist = event.list       | File for event hypocenter and origin time (deprecated)           |
+---------------------------+------------------------------------------------------------------+

+---------------------+-------------+
| signal              |             |
+=====================+=============+
| tapertype = hanning | Taper type  |
+---------------------+-------------+
| taperwidth = 0.1    | Taper width |
+---------------------+-------------+

.. ############################################################################ ..
.. #                           CONFIGURATION FILE                             # ..
.. ############################################################################ ..
"""


import os
from importlib import import_module
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
        self.qweights = [float(val)  for val in config.get('sachdrs', 'qweights').split()]
        # SAC plots
        self.figsize = [float(val)  for val in config.get('sacplot', 'figsize').split()]
        self.rectseis = [float(val)  for val in config.get('sacplot', 'rectseis').split()]
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
        self.qweights = [float(val)  for val in config.get('sachdrs', 'qweights').split()]
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


def _load_xcorr_func(func):
    """
    Load cross-correlation function from
    either the fortran or python module
    """
    # Try importing from the fortran extension first
    try:
        xcorr_modu = import_module('pysmo.aimbat.xcorrf90')
        xcorr_func = getattr(xcorr_modu, func)
        # Set the __name__ attribute to the function name
        # TODO: Can this be set in the f90 file instead?
        setattr(xcorr_func, '__name__', func)

    # Fortran extension is not available, or CC func
    # only exists in the Python version
    except (ModuleNotFoundError, AttributeError):
        xcorr_modu = import_module('pysmo.aimbat.xcorr')
        xcorr_func = getattr(xcorr_modu, func)

    return(xcorr_modu, xcorr_func)

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
        self.qweights = [float(val)  for val in config.get('sachdrs', 'qweights').split()]
        # SAC headers for ICCS time picks
        self.ichdrs = config.get('sachdrs', 'ichdrs').split()
        # Choose a xcorr module and function
        self.shift = config.getint('iccs', 'shift')
        func = config.get('iccs', 'xcorr_func')
        xcorr_modu, xcorr_func = _load_xcorr_func(func)
        print('Imported {:s} from {:s} as cross-correlation method for ICCS'
              .format(xcorr_func.__name__, xcorr_modu.__name__))
        self.xcorr = xcorr_func

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
        # Choose a xcorr function
        self.shift = config.getint('mccc', 'shift')
        func = config.get('mccc', 'xcorr_func')
        xcorr_modu, xcorr_func = _load_xcorr_func(func)
        print('Imported {:s} from {:s} as cross-correlation method for MCCC'
              .format(xcorr_func.__name__, xcorr_modu.__name__))
        self.xcorr = xcorr_func
        self.xcorr_modu = xcorr_modu

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

    parser.add_option('-f', '--fill', dest='fill', type='int',
                      help='Fill/shade seismogram with positive (1) or negative (-1) signal. '
                      'Default is none ({:d}).'.format(fill))
    parser.add_option('-r', '--relative-time', dest='reltime', type='int',
                      help='Relative time to a time pick header (t0-t9). '
                      'Default is {:d}, None, use absolute time.'.format(reltime))
    parser.add_option('-u', '--upylim', action="store_true", dest='upylim_on',
                      help='Update ylim every time of zooming in.')
    parser.add_option('-k', '--pick', action="store_true", dest='pick_on',
                      help='Plot time picks.')
    parser.add_option('-w', '--twin', action="store_true", dest='twin_on',
                      help='Plot time window.')
    parser.add_option('-x', '--xlimit', dest='xlimit', type='float', nargs=2,
                      help='Left and right x-axis limit to plot.')
    parser.add_option('-y', '--ynorm', dest='ynorm', type='float',
                      help='Normalize ydata of seismograms. Effective only for positive number. '
                      'Default is {:f}.'.format(ynorm))
    parser.add_option('-Y', '--ynormtwin', action="store_true", dest='ynormtwin_on',
                      help='Normalize seismogram within time window.')
    parser.add_option('-S', '--srate', dest='srate', type='float',
                      help='Sampling rate to load SAC data. '
                      'Default is None, use the original rate of first file.')

    return parser
