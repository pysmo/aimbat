# Command Line

## Seismogram files

AIMBAT uses [SAC](https://ds.iris.edu/files/sac-manual/) files as input. Before
adding files to an AIMBAT project please ensure the following header fields are
set correctly in all files:

- Seismogram begin time (SAC header *B*).
- Seismogram reference time (*KZTIME*) and date (*KZDATE*).
- Station name (*KSTNM*), latitude (*STLA*) and longitude *STLO*).
- Event origin time (*O*), latitude (*EVLA*) and longitude (*EVLO*).

To detect any potential problems with the data before importing them into AIMBAT,
you can use the AIMBAT cli:

<!-- termynal -->

```bash
$ aimbat checkdata *.BHZ
sacfile_01.BHZ: ✓✓✓
sacfile_02.BHZ: ✓✓✓
sacfile_03.BHZ: ✓✓✓
sacfile_04.BHZ: ✓✓✓
sacfile_05.BHZ: ✓✓✓
sacfile_06.BHZ: ✓✓✓
sacfile_07.BHZ: ✓✓✓
sacfile_08.BHZ: ✓✓✓
sacfile_09.BHZ: ✓✓✓
sacfile_10.BHZ: ✓✓✓
sacfile_11.BHZ: ✓✓✓
...
sacfile_NN.BHZ: ✓✓✓

No issues found!
```

The seismogram files can be stored in an arbitrary directory (i.e. they do not
necessarily need to be stored together with an AIMBAT project file).

!!! warning
    After importing files into an AIMBAT project, their location (and contents)
    should not be changed!
