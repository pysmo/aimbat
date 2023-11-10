# Data

An AIMBAT project consists of two kinds of data:

  1. **Static data:** [Seismogram files](data.md#seismogram-files) are treated as
     immutable objects by AIMBAT (i.e. the file contents are never changed).
     Besides the seismograms themselves, these files must also provide the
     necessary metadata (e.g. event information) to initialise a new AIMBAT
     project.

  2. **Mutable data:** A lot of operations in AIMBAT involve changing only metadata.
     Since it doesn't make much sense to read an entire seismogram file every
     time such an operation is performed, all mutable data are stored in the
     [AIMBAT project file](data.md#aimbat-project-file). This file holds a
     database, which is much more efficient at handling data which is frequently
     changed. The project file is automatically created from the seismogram files
     when a new AIMBAT project is started.


## Seismogram files

AIMBAT uses [SAC](https://ds.iris.edu/files/sac-manual/) files as input. Before adding
files to an AIMBAT project please ensure the following header fields are set correctly
in all files:

  - Seismogram begin time (SAC header *B*).
  - Seismogram reference time (*KZTIME*) and date (*KZDATE*).
  - Station name (*KSTNM*), latitude (*STLA*) and longitude *STLO*).
  - Event origin time (*O*), latitude (*EVLA*) and longitude (*EVLO*).

To detect any potential problems with the data before importing them into AIMBAT, you can
use the AIMBAT cli:

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

The seismogram files can be stored in an arbitrary directory (i.e. they don't necessarily
need to be stored together with an AIMBAT project file). They are also never modified by
AIMBAT.

!!! warning

    After importing files into an AIMBAT project, their location (and contents) should
    not be changed!


## AIMBAT project file

AIMBAT projects consist of a single [sqlite](https://www.sqlite.org) file (which is
automatically generated when a new project is created). This file contains all relevant
metadata of imported seismograms, but not the actual time series data. This separation of
data and metadata is mainly to increase performance in AIMBAT. However, it also means we
get some additional nice features as byproducts:

  - The single (and small) file makes it easy to backup and restore entire AIMBAT
    projects.
  - Starting over is also trivially simple - one only needs to delete a single file.
  - The same seismogram files can be used for multiple AIMBAT projects. In practice
    one might, for example, want to use the same files multiple times but with
    different parameters.


### Database tables

AIMBAT users typically will never need to interact directly with the project file. As as
reference for AIMBAT developers, or advanced users who may want to interact with the
database file directly (e.g. via 3rd party tools), we describe the tables below:

``` mermaid
---
title: AIMBAT database structure
---
classDiagram
  class AimbatDefault{
    id: int
    name: str
    is_of_type: str
    description: str
    initial_value: str
    fvalue: float
    ivalue: int
    bvalue: bool
    svalue: str
  }

  class AimbatStation{
    id: int
    name: str
    latitude: float
    longitude: float
    network: str
    elevation: float
  }

  class AimbatEvent{
    id: int
    time: DateTime
    latitude: float
    longitude: float
    depth: float
  }

  class AimbatFile{
    id: int
    filename: Path
  }

  class AimbatMeta{
    id: int
    file_id: int | None = Field(default=True, foreign_key="aimbatfile.id")
    station_id: int | None = Field(default=None, foreign_key="aimbatstation.id")
    event_id: int | None = Field(default=None, foreign_key="aimbatevent.id")
    use: bool = True
  }

AimbatFile  --> AimbatMeta
```

#### AimbatDefault

The `AimbatDefault` table contains defaults used to tweak the behaviour of AIMBAT. It is
populated when a new AIMBAT project is created.


To account for values
of different types (float, integer, boolean, string), multiple columns are required. If
a default is of type `float`, the `fvalue` column will contain data, whereas if it is a
`str` the `svalue` column contains data, and so on.
