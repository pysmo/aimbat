=================
Installing AIMBAT
=================

.. ############################################################################ ..
.. #                          GETTING THE PACKAGES                            # ..
.. ############################################################################ ..

Getting the Packages
--------------------

AIMBAT is released as a sub-package of pysmo under the name ``pysmo.aimbat`` along with another sub-package ``pysmo.sac``. The latest stable release of AIMBAT is available for download at the `official project webpage <http://www.earth.northwestern.edu/~xlou/aimbat.html>`_.

We are working on a new release of AIMBAT, available on `Github <https://github.com/pysmo>`_. Download `pysmo.aimbat <https://github.com/pysmo/aimbat>`_ and `pysmo.sac <https://github.com/pysmo/sac>`_ from Github. You will now have two folders called ``aimbat`` and ``sac`` respectively.

You may want to download `example code <https://github.com/pysmo/data-example>`_ to run AIMBAT on as well.

.. ############################################################################ ..
.. #                          GETTING THE PACKAGES                            # ..
.. ############################################################################ ..






.. ############################################################################ ..
.. #                             BUILDING PYSMO                               # ..
.. ############################################################################ ..

Building the Pysmo Packages
---------------------------

You need to be an administrator on the computer you are installing AIMBAT on, as you need to run the commands with ``sudo``.

Building pysmo.sac
~~~~~~~~~~~~~~~~~~

Python module ``Distutils`` is used to write a setup.py script to build, distribute, and install ``pysmo.sac``. cd into the ``sac`` directory on the command line and run::

	sudo python setup.py build
  	sudo python setup.py install

If you successfully installed the sac module, in the python console, after you type::

	from pysmo import sac

there should be no errors.

Installing pysmo.aimbat
~~~~~~~~~~~~~~~~~~~~~~~

Three sub-directories are included in the ``aimbat`` directory:

- ``example``: Example SAC files
- ``scripts``: Python scripts to run at the command line
- ``src``: Python modules to install

The core cross-correlation functions are written in both Python/Numpy (``xcorr.py``) and Fortran (``xcorr.f90``). Therefore, we need to use Numpy’s ``Distutils`` module for enhanced support of Fortran extension. The usage is similar to the standard Disutils.

Note that some sort of Fortran compiler must already be installed first. Specify them in place of gfortran in the following commands.

cd into the ``aimbat`` directory and run::

	sudo python setup.py build --fcompiler=gfortran
  	sudo python setup.py install

to install the :code:`src` directory.

Add ``<path-to-folder>/aimbat/scripts`` to environment variable ``PATH`` in a shells start-up file for command line execution of the scripts. Inside the :code:`~/.bashrc` file, add the lines

Bash Shell Users::

	export PATH=$PATH:<path-to-folder>/aimbat/scripts

C Shell Users::

	setenv PATH=$PATH:<path-to-folder>/aimbat/scripts

Don't forget to run :code:`source ~/.bashrc` If AIMBAT has been installed, type ``from pysmo import aimbat`` in a Python shell, and no errors should appear.

If you have added the scripts correctly, typing part of the name of the script in the terminal should be sufficient to allow the system to autocomplete the name.


.. ############################################################################ ..
.. #                             BUILDING PYSMO                               # ..
.. ############################################################################ ..

.. ############################################################################ ..
.. #                             EXAMPLE CODE                                 # ..
.. ############################################################################ ..

Example Data
------------

Get the repository `data-example <https://github.com/pysmo/data-example>`_ from Github. There is some example code inside `data-example/example_pkl_files` that will be needed for later demonstrations.
