# Samples: transcript_reorder

10 of 445 verified children, picked with seed 206. For human spot checks: does the child ask the same thing (text augmentations) or is the new gold right for the new state (transcript_length)?

## Q0016-R (remaining_core)

- before: I'm an MTech-CSE student in the AI/ML stream (coursework track) and I have completed 2 semesters. Am I missing any compulsory or stream core course?
- after: I'm an MTech-CSE student in the AI/ML stream (coursework track) and I have completed 2 semesters. Am I missing any compulsory or stream core course?
- student before: `S0153` semesters_completed=2; transcript: CS 610 (s1, A-), ES 606 (s1, B-), ES 612 (s1, B-), ES 615 (s1, A), ES 678 (s1, C), FP 601 (s1, P), PE 600 (s1, P), CS 617 (s2, B-), CS 621 (s2, B-), ES 667 (s2, B), FP 602 (s2, B), PE 600 (s2, P), REQ-PROJECT (s2, B)
- student after: `S0153-R` semesters_completed=2; transcript: FP 602 (s2, B), REQ-PROJECT (s2, B), PE 600 (s1, P), CS 617 (s2, B-), ES 615 (s1, A), ES 612 (s1, B-), ES 678 (s1, C), CS 621 (s2, B-), PE 600 (s2, P), CS 610 (s1, A-), ES 606 (s1, B-), ES 667 (s2, B), FP 601 (s1, P)

## Q0096-R (remaining_core)

- before: I'm an MTech-AI student in the AI/ML stream (coursework track) and I have completed 2 semesters. Can you give me a full audit of my remaining graduation requirements?
- after: I'm an MTech-AI student in the AI/ML stream (coursework track) and I have completed 2 semesters. Can you give me a full audit of my remaining graduation requirements?
- student before: `S0163` semesters_completed=2; transcript: CS 610 (s1, A-), CS 613 (s1, B), ES 678 (s1, A), FP 601 (s1, P), FP 602 (s1, A-), PE 600 (s1, P), CS 621 (s2, A-), ES 417 (s2, A-), ES 667 (s2, A), PE 600 (s2, P), REQ-PROJECT (s2, C)
- student after: `S0163-R` semesters_completed=2; transcript: FP 602 (s1, A-), ES 417 (s2, A-), CS 621 (s2, A-), FP 601 (s1, P), CS 613 (s1, B), PE 600 (s2, P), CS 610 (s1, A-), PE 600 (s1, P), REQ-PROJECT (s2, C), ES 678 (s1, A), ES 667 (s2, A)

## Q0331-R (eligibility)

- before: I'm an MTech-ICDT student (coursework track) and I have completed 3 semesters. Have I met the prerequisites for CS 614 (Advanced Algorithms)?
- after: I'm an MTech-ICDT student (coursework track) and I have completed 3 semesters. Have I met the prerequisites for CS 614 (Advanced Algorithms)?
- student before: `S0057` semesters_completed=3; transcript: EE 651 (s1, A-), ES 626 (s1, A-), ES 660 (s1, B), FP 601 (s1, P), FP 602 (s1, B-), PE 600 (s1, P), EE 617 (s2, B-), EE 618 (s2, B-), EE 644 (s2, A), ES 669 (s2, A-), PE 600 (s2, P), REQ-PROJECT (s2, C), CS 620 (s3, A), ES 662 (s3, A-), ES 673 (s3, B-), ES 679 (s3, B), REQ-PROJECT (s3, B)
- student after: `S0057-R` semesters_completed=3; transcript: ES 673 (s3, B-), ES 662 (s3, A-), FP 601 (s1, P), PE 600 (s2, P), EE 651 (s1, A-), ES 679 (s3, B), EE 644 (s2, A), CS 620 (s3, A), EE 618 (s2, B-), REQ-PROJECT (s2, C), ES 669 (s2, A-), ES 626 (s1, A-), REQ-PROJECT (s3, B), FP 602 (s1, B-), EE 617 (s2, B-), ES 660 (s1, B), PE 600 (s1, P)

## Q0382-R (eligibility)

- before: I'm an MTech-CSE student in the AI/ML stream (coursework track) and I have completed 3 semesters. Is it possible for me to enrol in ES 656 next term?
- after: I'm an MTech-CSE student in the AI/ML stream (coursework track) and I have completed 3 semesters. Is it possible for me to enrol in ES 656 next term?
- student before: `S0061` semesters_completed=3; transcript: CS 610 (s1, B), ES 645 (s1, A-), ES 667 (s1, A), FP 601 (s1, P), FP 602 (s1, B-), PE 600 (s1, P), CS 615 (s2, B-), CS 617 (s2, B), CS 621 (s2, C), ES 678 (s2, A-), MA 607 (s2, B-), PE 600 (s2, P), CS 613 (s3, B), ES 621 (s3, B), ES 656 (s3, A), REQ-PROJECT (s3, C)
- student after: `S0061-R` semesters_completed=3; transcript: ES 667 (s1, A), CS 610 (s1, B), MA 607 (s2, B-), FP 602 (s1, B-), CS 615 (s2, B-), PE 600 (s2, P), ES 656 (s3, A), CS 617 (s2, B), ES 678 (s2, A-), CS 621 (s2, C), ES 645 (s1, A-), CS 613 (s3, B), FP 601 (s1, P), PE 600 (s1, P), ES 621 (s3, B), REQ-PROJECT (s3, C)

## Q0386-R (eligibility)

- before: I'm an MTech-EE student in the Power Engineering & Control Systems stream (coursework track) and I have completed 2 semesters. Am I eligible to take EE 606 (Applied Statistical Bioelectric Signal Analysis) in the upcoming term, 2026-27 Sem-I?
- after: I'm an MTech-EE student in the Power Engineering & Control Systems stream (coursework track) and I have completed 2 semesters. Am I eligible to take EE 606 (Applied Statistical Bioelectric Signal Analysis) in the upcoming term, 2026-27 Sem-I?
- student before: `S0051` semesters_completed=2; transcript: ES 613 (s1, B), ES 665 (s1, A-), FP 601 (s1, P), FP 602 (s1, B), PE 600 (s1, P), EE 604 (s2, B), EE 619 (s2, A-), ES 642 (s2, A), PE 600 (s2, P)
- student after: `S0051-R` semesters_completed=2; transcript: ES 613 (s1, B), PE 600 (s2, P), PE 600 (s1, P), ES 642 (s2, A), FP 601 (s1, P), ES 665 (s1, A-), FP 602 (s1, B), EE 619 (s2, A-), EE 604 (s2, B)

## Q0423-R (elective_recommendation)

- before: I'm an MTech-ICDT student (thesis track) and I have completed 2 semesters. Which courses should I take to complete my basket requirements?
- after: I'm an MTech-ICDT student (thesis track) and I have completed 2 semesters. Which courses should I take to complete my basket requirements?
- student before: `S0028` semesters_completed=2; transcript: EE 647 (s1, B), EE 651 (s1, B), ES 660 (s1, B), ES 672 (s1, A), FP 601 (s1, P), PE 600 (s1, P), CS 622 (s2, A-), FP 602 (s2, A-), PE 600 (s2, P), REQ-THESIS (s2, A)
- student after: `S0028-R` semesters_completed=2; transcript: EE 651 (s1, B), ES 672 (s1, A), PE 600 (s1, P), REQ-THESIS (s2, A), FP 601 (s1, P), PE 600 (s2, P), FP 602 (s2, A-), EE 647 (s1, B), ES 660 (s1, B), CS 622 (s2, A-)

## Q0428-R (elective_recommendation)

- before: I'm an MTech-CSE student in the Systems stream (coursework track) and I have completed 1 semester. Which 3 electives would you recommend for 2026-27 Sem-II?
- after: I'm an MTech-CSE student in the Systems stream (coursework track) and I have completed 1 semester. Which 3 electives would you recommend for 2026-27 Sem-II?
- student before: `S0118` semesters_completed=1; transcript: CS 435 (s1, A), CS 610 (s1, B-), CS 612 (s1, B-), FP 601 (s1, P), PE 600 (s1, P)
- student after: `S0118-R` semesters_completed=1; transcript: PE 600 (s1, P), CS 612 (s1, B-), CS 610 (s1, B-), CS 435 (s1, A), FP 601 (s1, P)

## Q0548-R (elective_recommendation)

- before: I'm an MTech-AI student in the AI/ML stream (coursework track) and I have completed 3 semesters. Which 3 electives would you recommend for 2026-27 Sem-II?
- after: I'm an MTech-AI student in the AI/ML stream (coursework track) and I have completed 3 semesters. Which 3 electives would you recommend for 2026-27 Sem-II?
- student before: `S0151` semesters_completed=3; transcript: CS 610 (s1, B), CS 613 (s1, A), ES 634 (s1, B), ES 659 (s1, B), ES 678 (s1, A), FP 601 (s1, P), PE 600 (s1, P), CS 621 (s2, A), ES 667 (s2, B), FP 602 (s2, B), PE 600 (s2, P), CS 620 (s3, A), ES 604 (s3, A), ES 621 (s3, B), REQ-PROJECT (s3, C)
- student after: `S0151-R` semesters_completed=3; transcript: CS 610 (s1, B), ES 604 (s3, A), CS 620 (s3, A), REQ-PROJECT (s3, C), PE 600 (s2, P), ES 621 (s3, B), PE 600 (s1, P), CS 621 (s2, A), FP 601 (s1, P), FP 602 (s2, B), ES 634 (s1, B), ES 667 (s2, B), CS 613 (s1, A), ES 678 (s1, A), ES 659 (s1, B)

## Q0564-R (elective_recommendation)

- before: I'm an MTech-EE student in the Power Engineering & Control Systems stream (thesis track) and I have completed 3 semesters. Suggest 3 electives I can take next semester.
- after: I'm an MTech-EE student in the Power Engineering & Control Systems stream (thesis track) and I have completed 3 semesters. Suggest 3 electives I can take next semester.
- student before: `S0158` semesters_completed=3; transcript: EE 604 (s1, B-), ES 616 (s1, B-), ES 642 (s1, B-), FP 601 (s1, P), FP 602 (s1, A-), PE 600 (s1, P), EE 659 (s2, B), ES 665 (s2, A-), PE 600 (s2, P), REQ-THESIS (s2, B), CS 620 (s3, B), EE 663 (s3, C-), EE 671 (s3, B-), REQ-THESIS (s3, B)
- student after: `S0158-R` semesters_completed=3; transcript: FP 602 (s1, A-), REQ-THESIS (s2, B), PE 600 (s2, P), FP 601 (s1, P), REQ-THESIS (s3, B), EE 659 (s2, B), EE 663 (s3, C-), ES 665 (s2, A-), EE 671 (s3, B-), ES 616 (s1, B-), EE 604 (s1, B-), ES 642 (s1, B-), PE 600 (s1, P), CS 620 (s3, B)

## Q0566-R (elective_recommendation)

- before: I'm an MTech-AI student in the AI/ML stream (thesis track) and I have completed 3 semesters. Suggest 3 electives I can take next semester.
- after: I'm an MTech-AI student in the AI/ML stream (thesis track) and I have completed 3 semesters. Suggest 3 electives I can take next semester.
- student before: `S0066` semesters_completed=3; transcript: CS 610 (s1, B-), ES 667 (s1, A), ES 678 (s1, B), FP 601 (s1, P), FP 602 (s1, A), PE 600 (s1, P), CS 621 (s2, B), ES 404 (s2, A-), ES 634 (s2, A), ES 666 (s2, B-), PE 600 (s2, P), REQ-THESIS (s2, A), CS 691-XVIII (s3, A-), REQ-THESIS (s3, A)
- student after: `S0066-R` semesters_completed=3; transcript: FP 602 (s1, A), ES 678 (s1, B), CS 610 (s1, B-), ES 634 (s2, A), ES 667 (s1, A), CS 621 (s2, B), REQ-THESIS (s2, A), FP 601 (s1, P), ES 666 (s2, B-), PE 600 (s2, P), CS 691-XVIII (s3, A-), PE 600 (s1, P), REQ-THESIS (s3, A), ES 404 (s2, A-)
