SAC Input/Output procedures for AIMBAT
--------------------------------------

Aimbat converts SAC files to python pickle data structure to increase
data processing efficiency by avoiding frequent SAC file I/O.

Reading and writing SAC files is done only once each before and after data processing, and
intermediate processing is performed on python objects and pickles.

Converting from SAC to PKL files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Place the SAC files you want to convert to a pickle (PKL) file into the same folder.
Suppose, for instance, they are BHZ channels. Note that the SAC files must be of the
same channel. cd into that folder, and run::

    aimbat-sac2pkl -s *.BHZ.sac

The output should be a PKL file in the same folder as the sac files.

.. image:: images/sac_to_pkl_conversion.png


Converting from PKL to SAC files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

cd into the folder containing the PKL file that you wish to convert into SAC files, and run::

	aimbat-sac2pkl --p2s <name-of-file>.pkl

The SAC files contained within will output into the same folder as the PKL file is stored in.

.. image:: images/pkl_to_sac_conversion.png
