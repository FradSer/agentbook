"""Orchestration that runs each cell-sample and scores it IMMEDIATELY in the same
process, writing one self-describing result.json per sample. This makes the
old class of staleness bugs (runs/ re-executed after a separate score pass)
structurally impossible."""
