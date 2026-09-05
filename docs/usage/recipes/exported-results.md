### Working with exported results

`aimbat snapshot results <SNAPSHOT_ID>` prints a JSON document: event
metadata (`event_time`, `event_latitude`, `event_longitude`, and the global
`mccc_rmse`) at the top level, plus a `seismograms` array with one entry per
station — `name`, `select`, the pick `t1`, `iccs_cc`, and, once MCCC has
run, `mccc_error`. MCCC fields are `null` in a snapshot taken before MCCC
ran. Full field reference: [Exporting Results](../results.md#output-format).

#### Filtering with `jq`

Selected seismograms only:

```bash
aimbat snapshot results <SNAPSHOT_ID> | \
    jq '[.seismograms[] | select(.select == true)]'
```

Stations where MCCC timing error is below 0.05 s:

```bash
aimbat snapshot results <SNAPSHOT_ID> | \
    jq '[.seismograms[] | select(.mccc_error != null and .mccc_error < 0.05)]'
```

Station names and pick times as CSV:

```bash
aimbat snapshot results <SNAPSHOT_ID> | \
    jq -r '.seismograms[] | [.name, .t1] | @csv'
```

#### Python

```python
import json

with open("results.json") as f:
    data = json.load(f)

print(f"Event: {data['event_time']}  ({data['event_latitude']}, {data['event_longitude']})")
print(f"MCCC RMSE: {data['mccc_rmse']} s")

for seis in data["seismograms"]:
    if seis["select"]:
        print(f"  {seis['name']:12s}  t1={seis['t1']}  err={seis['mccc_error']}")
```
