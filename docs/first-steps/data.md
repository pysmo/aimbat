## Data

AIMBAT projects are created from [seismogram files](data.md#seismogram-files).
Event and station information, as well as initial arrival time picks are read
from these files to populate the AIMBAT [project file](data.md#project-file).
The majority of operations within AIMBAT exclusively use the project file. The
contents of the seismogram files are never modified by AIMBAT.

### Seismogram files

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

### Project file

AIMBAT projects consist of a single
[sqlite](https://www.sqlite.org){ target="_blank" } file (which is
automatically generated when a new project is created). This file contains a
database to manage all aspects of an AIMBAT project. Understanding the
internals of this file is not particularly important for normal AIMBAT usage,
though it might be useful to look at the data directly in cases where AIMBAT
behaves in unexpected ways (e.g. due to inconsistencies in the seismogram files
used as input). To do this we suggest viewing the database in tools such as
[DB Browser for SQLite](https://sqlitebrowser.org){ target="_blank" }.
![DB Browser](/images/sqlbrowser.png){ loading=lazy }

## Parameters

AIMBAT uses three tiers of parameters to control behaviour and processing:

  1. AIMBAT defaults: shared across all events and seismograms in a project.
  2. Event parameters: specific to an event, or shared across all seismograms
    of that event.
  3. Seismogram parameters: specific to a single seismogram.

### AIMBAT Defaults

AIMBAT defaults are settings that are common across all events and seismograms
in a project. They are settings that control the default behaviour of AIMBAT.
Changing the values of these defaults should therefore only be done *before*
data are added to a project. The defaults are defined in
[`AimbatDefaults`][aimbat.lib.models.AimbatDefaults] and can be viewed by
running `aimbat defaults list` in the terminal.

### Event Parameters

Event parameters are used during processing. They are parameters that are
specific to an event (e.g. if an event should be marked as completed), or
parameters that are shared across all seismograms of that event (e.g. time
window for the cross-correlation, filter parameters, etc.).
These parameters are attributes of the
[`AimbatEventParametersBase`][aimbat.lib.models.AimbatEventParametersBase]
class.

### Seismogram Parameters

Seismogram parameters are also used during processing. Most notably the time
picks belong to this tier. These parameters are attributes of the
[`AimbatSeismogramParametersBase`][aimbat.lib.models.AimbatSeismogramParametersBase]
class.

## Snapshots

Unlike the AIMBAT defaults, event and seismogram parameters are constantly
changed during processing. The current state of the parameters can be saved as
a snapshot, allowing a rollback should the updated parameters cause an issue or
turn out to yield inferior results.
