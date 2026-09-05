### Building from headerless SAC files

Some data sources strip event and station headers from SAC files entirely,
leaving that metadata to be supplied separately. The script below builds a
complete project around that gap: it registers **3 events** and
**10 stations** from JSON, then links each of the **20 seismograms** to the
right pair as it imports the SAC files, and takes an initial snapshot of
each event before any processing.

```python
--8<-- "docs/snippets/api_load_project.py"
```
