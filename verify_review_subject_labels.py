"""Verify that generated review blocks expose their discipline."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise RuntimeError(message)


def main():
    planner=(ROOT/'planner.py').read_text(encoding='utf-8')
    require('REVIEW SUBJECT LABELS V1' in planner,'Review-subject patch is missing.')
    require("subject_names={x['id']:x.get('name','Disciplina')" in planner,'Subject-name map is missing.')
    require("discipline+' · Revisão de teoria: '" in planner,'Theory review title does not include the discipline.')
    require("discipline+' · Exercícios: '" in planner,'Exercise review title does not include the discipline.')
    require("subjectName=task.get('subjectName','')" in planner,'Review-session subject metadata is missing.')
    require("' Disciplina: '+discipline" in planner,'Review reason does not include the discipline.')
    print('MEUCRONOGRAMA_REVIEW_SUBJECT_LABELS_CHECK_OK: discipline appears in review blocks and metadata.',flush=True)


if __name__=='__main__':main()
