=======================
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
