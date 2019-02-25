=================
Developing AIMBAT
=================

Github
------
We use Github for the development of AIMBAT. We welcome contributions in the form of bug reports and pull requests to the master branch. Github is easiest to use with authentication using SSH keys. Please refer to the `Github documentation <https://help.github.com/en/articles/connecting-to-github-with-ssh>`_ for setup instructions on your platform.

Once your account is properly set up you can copy the AIMBAT repository to the your workstation with the ``git clone`` command::

   $ git clone git@github.com:pysmo/aimbat.git

You can now navigate to the aimbat directory and explore the files::

   $ cd aimbat
   $ ls
   build  Changelog.txt  docs ...

.. note:: If you are not a member of the `pysmo group <https://github.com/pysmo>`_ on Github you will have to first fork the AIMBAT repository (from the GUI on Github).

Pipenv
------
In order to develop AIMBAT in a consistent and isolated environment we use `pipenv <https://pipenv.readthedocs.io/en/latest/>`_. Pipenv creates a Python virtual environment and manages the Python packages that are installed in that environment. This allows developing and testing while also having the stable version of AIMBAT installed at the same time. If pipenv isn't already available on your system you can install it with pip::

   $ pip install pipenv

Next use pipenv to create a new Python virtual environment and install all packages needed for running and developing AIMBAT::

   $ pipenv install --dev

Once this command has finished (it may take a while to complete), you can spawn a shell that uses this new Python virtual environment by running ``pipenv shell`` or execute commands that run in the environment with ``pipenv run`` For example, to build and install AIMBAT for development you would run::

   $ pipenv run python setup.py develop

.. caution:: Please note that pipenv only creates a virtual environment for Python - it is not comparable to a virtual machine and does not offer the same separation!

.. note:: For convenience we put a lot of these commands in a ``Makefile`` for you to use.

At this point you can use the stable version of AIMBAT in your regular shell, and if you spawn one with ``pipenv shell`` (from within the ``aimbat`` repository you cloned earlier) you are using the development version!

Git workflow
------------

Unit testing
------------
This section is mainly for those who wish to make tweaks to AIMBAT themselves. We have added some unit tests to AIMBAT to ensure that it is robust. See the `Python Unit Testing Framework <https://docs.python.org/2/library/unittest.html>`_ for more details.

Running the Tests
~~~~~~~~~~~~~~~~~

In the AIMBAT repository, ``cd`` into ``/src/pysmo/unit_tests`` and run::

	python run_unit_tests.py

