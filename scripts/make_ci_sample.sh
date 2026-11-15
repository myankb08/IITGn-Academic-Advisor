#!/bin/sh
# Pack the A1 data that CI needs into ci/a1_validation_sample.tar.gz (about 0.5 MB). CI has no access to the DVC
# remote: this archive is the "sample Assignment 1 validation" input for the unit tests and the processed-stage
# validation, and it gives the image build its curriculum, students and the gold set (the image must bundle it;
# CI builds data/sft/gold.jsonl from it). The files are copies of DVC outputs at the current dvc.lock.
set -e
cd "$(dirname "$0")/.."
tar czf ci/a1_validation_sample.tar.gz --sort=name --owner=0 --group=0 --mtime='2026-11-10 00:00Z' \
  data/processed/courses.json data/processed/rules.json data/processed/prereq_graph.json \
  data/processed/students.jsonl data/processed/students_augmented.jsonl data/processed/queries.jsonl \
  data/processed/queries_para.jsonl data/processed/queries_augmented.jsonl \
  data/splits/train.csv data/splits/val.csv data/splits/test.csv data/splits/programme_holdout.csv \
  data/splits/shifted_forms.csv data/labels/audited.jsonl data/interim/students_corrupted.jsonl \
  data/raw/forms/responses_anonymised.jsonl data/raw/extracted/timetable_rows.jsonl data/gold/gold_test.jsonl
sha256sum ci/a1_validation_sample.tar.gz | tee ci/a1_validation_sample.sha256
