# AIMBAT Database Models

```mermaid
erDiagram
    AimbatStation ||--o{ AimbatSeismogram : "records"
    AimbatEvent ||--o{ AimbatSeismogram : "has"
    AimbatEvent ||--o| AimbatEventParameters : "has"
    AimbatEvent ||--o| AimbatEventQuality : "has"
    AimbatEvent ||--o{ AimbatSnapshot : "has"
    AimbatSeismogram ||--o| AimbatDataSource : "has"
    AimbatSeismogram ||--o| AimbatSeismogramParameters : "has"
    AimbatSeismogram ||--o| AimbatSeismogramQuality : "has"
    
    AimbatSnapshot ||--o| AimbatEventParametersSnapshot : "has"
    AimbatSnapshot ||--o{ AimbatSeismogramParametersSnapshot : "has"
    AimbatSnapshot ||--o| AimbatEventQualitySnapshot : "has"
    AimbatSnapshot ||--o{ AimbatSeismogramQualitySnapshot : "has"
    
    AimbatEventParameters ||--o{ AimbatEventParametersSnapshot : "snapshots"
    AimbatSeismogramParameters ||--o{ AimbatSeismogramParametersSnapshot : "snapshots"
    AimbatEventQuality ||--o{ AimbatEventQualitySnapshot : "snapshots"
    AimbatSeismogramQuality ||--o{ AimbatSeismogramQualitySnapshot : "snapshots"

    AimbatStation {
        uuid id PK
        string name
        string network
        string location
        string channel
        float latitude
        float longitude
        float elevation
    }

    AimbatEvent {
        uuid id PK
        bool is_default UK
        timestamp time UK
        float latitude
        float longitude
        float depth
        timestamp last_modified
    }

    AimbatSeismogram {
        uuid id PK
        timestamp begin_time
        timedelta delta
        timestamp t0
        uuid station_id FK
        uuid event_id FK
        dict extra
    }

    AimbatDataSource {
        uuid id PK
        string sourcename UK
        datatype datatype
        uuid seismogram_id FK
    }

    AimbatEventParameters {
        uuid id PK
        uuid event_id FK
    }

    AimbatSeismogramParameters {
        uuid id PK
        uuid seismogram_id FK
    }

    AimbatEventQuality {
        uuid id PK
        uuid event_id FK
    }

    AimbatSeismogramQuality {
        uuid id PK
        uuid seismogram_id FK
    }

    AimbatSnapshot {
        uuid id PK
        timestamp date UK
        string comment
        string parameters_hash
        uuid event_id FK
    }

    AimbatEventParametersSnapshot {
        uuid id PK
        uuid snapshot_id FK
        uuid parameters_id FK
    }

    AimbatSeismogramParametersSnapshot {
        uuid id PK
        uuid seismogram_parameters_id FK
        uuid snapshot_id FK
    }

    AimbatEventQualitySnapshot {
        uuid id PK
        uuid event_quality_id FK
        uuid snapshot_id FK
    }

    AimbatSeismogramQualitySnapshot {
        uuid id PK
        uuid seismogram_quality_id FK
        uuid snapshot_id FK
    }
```

## Relationships Summary

- **AimbatStation** → **AimbatSeismogram**: One-to-Many (a station records many seismograms)
- **AimbatEvent** → **AimbatSeismogram**: One-to-Many (an event has many seismograms)
- **AimbatEvent** → **AimbatEventParameters**: One-to-One (an event has one set of parameters)
- **AimbatEvent** → **AimbatEventQuality**: One-to-One (an event has one quality record)
- **AimbatEvent** → **AimbatSnapshot**: One-to-Many (an event can have many snapshots)
- **AimbatSeismogram** → **AimbatDataSource**: One-to-One (a seismogram has one datasource)
- **AimbatSeismogram** → **AimbatSeismogramParameters**: One-to-One
- **AimbatSeismogram** → **AimbatSeismogramQuality**: One-to-One
- **AimbatSnapshot** → **AimbatEventParametersSnapshot**: One-to-One
- **AimbatSnapshot** → **AimbatSeismogramParametersSnapshot**: One-to-Many
- **AimbatSnapshot** → **AimbatEventQualitySnapshot**: One-to-One
- **AimbatSnapshot** → **AimbatSeismogramQualitySnapshot**: One-to-Many

## Notes

- All primary keys are UUIDs
- Foreign keys use CASCADE delete
- UK = Unique Key
- FK = Foreign Key
- Snapshot tables store historical copies of parameters and quality metrics for rollback/analysis
