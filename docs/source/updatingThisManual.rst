====================
Updating this manual
====================

This is for someone who wants to be a collaborator on AIMBAT only. This is NOT necessary for anyone who only wants to use AIMBAT. AIMBAT will work fine if you do not install the dependencies listed here.

To be able to update the manual, download the `source code <https://github.com/pysmo/aimbat-docs>`_ from Github, and install the dependencies.

Dependencies
------------

* `Sphinx <http://sphinx-doc.org/>`_. Download and install from `here <https://pypi.python.org/pypi/Sphinx>`_. Don't get the Python Wheel version unless you know what you are doing

* `LaTeX`. Download it from `here <http://www.tug.org/mactex/>`_. Get the package installer.

* A browser. But if you are reading this, you already have it.

How to update this manual
-------------------------

On the master branch, cd into the github repository `aimbat-docs <https://github.com/pysmo/aimbat-docs>` and run::

	sphinx-build -b html . builddir
	make html
	make latexpdf

The first two commands build the html for the webpage, while the last command makes a pdf version of the online documentation.

Now, commit the changes made in GitHub, and push the changes to the master branch. The changes should be visible in the documentation within a few minutes.
