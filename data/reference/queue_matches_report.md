# Queued Up matches

Written by `scripts/queue_matches.py`. Do not edit by hand.

- Contested projects: 575, of which 558 are solar, wind or storage.
- Queue requests: 31008, of which 9941 carry a project name and can be matched.
- Strong matches: 116 projects (150 requests).
- Possible matches only: 25 projects.
- No match: 417 solar, wind or storage projects.
- Conflicts with the published outcome (strong matches only): 26.

| Outcome | Strong matches | With a request date | With a withdrawal date | With an operation date |
|---|---:|---:|---:|---:|
| advanced_confirmed | 12 | 12 | 1 | 5 |
| advanced_unverified | 6 | 6 | 2 | 3 |
| blocked_confirmed | 3 | 3 | 2 | 0 |
| blocked_unverified | 30 | 30 | 17 | 0 |
| needs_review | 6 | 6 | 3 | 1 |
| pending | 59 | 59 | 11 | 7 |

A match never changes an outcome; a conflict is a prompt to review the project, not a correction.
