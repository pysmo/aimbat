### Deduplicating events

`add_data_to_project` deduplicates stations automatically by SEED code
`(network, name, location, channel)`, so importing the same station from
multiple sources never creates duplicate records.

Events are a different story. Import reuses an existing event on an exact
origin-time match, or when the gap is within `event_duplicate_tolerance`
(default 0.1 s); a larger gap either raises (the "ambiguous gap" band) or,
beyond `event_duplicate_raise_tolerance`, silently creates a separate
`AimbatEvent` record. When two data sources report the same earthquake with
times that differ by more than that, they end up as separate records. The
script below detects such near-duplicates, merges their seismograms into the
record with the most data, averages the location and depth, and removes the
extras.

```python
--8<-- "docs/snippets/api_deduplicate.py"
```
