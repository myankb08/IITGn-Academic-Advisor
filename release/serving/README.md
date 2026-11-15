Files copied into the image next to the model (models/production/):
- reported_gold.json: gold-set metrics of this release measured inside the container on CPU (full set and the
  20-item UI subset), with the stated tolerance. Written by `validate --write_reported --reported_out`.
- monitoring_thresholds.json: drift thresholds set on val replay windows (src/monitor/replay.py).
