# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 2 | 0 | 4 |
| contested_projects | 0 | 0 | 0 |
| cases | 0 | 0 | 0 |
| state_policies | 122 | 0 | 0 |

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|
| -> | res_42b4a46830 | NY | New Lisbon Town | ->confirmed | ->opened | ->https://townofnewlisbonny.gov/wp-content/uploads/2012/04/Local-Law-2-of-2017.pdf | compiled_flagged->primary_source | unverified->verified | ->2026-10-09 |
| -> | res_69535de7dc | IA | Fremont County | ->confirmed | ->opened | ->https://fremontia.socs.net/vimages/shared/vnews/stories/5cad3edf734e1/Wind_Energy_Conversion_Systems_-_Final_Draft.pdf | compiled_flagged->primary_source | unverified->verified | ->2026-10-09 |
| -> | res_b0f2b57d5e | OR | Crook County | ->confirmed | ->opened | ->https://www.codepublishing.com/OR/CrookCounty/html/CrookCounty18/CrookCounty18161.html | compiled_flagged->primary_source | unverified->verified | ->2026-10-09 |
| -> | res_1d1d612c38 | TX | Hallsville City | ->confirmed | ->opened | ->https://cityofhallsvilletx.com/wp-content/uploads/2018/02/Ordinance-2016-06-Zoning-Ordinance-web.pdf | compiled_flagged->primary_source | unverified->verified | ->2026-10-09 |
| +++ | res_f166b01b85 | OH | Huron County | confirmed | opened | https://www.huroncounty-oh.gov/Documents/Government/Commissioners/Agendas%20and%20Minutes/Minutes/2026/April%207,%202026%20Signatures%20on%20File%20.pdf | primary_source | verified |  |
| +++ | res_a9b410ffbf | OH | Huron County | confirmed | opened | https://www.huroncounty-oh.gov/Documents/Government/Commissioners/Agendas%20and%20Minutes/Minutes/2026/April%207,%202026%20Signatures%20on%20File%20.pdf | primary_source | verified |  |

### state_policies

| @@ | id | state |
|---|---|---|
| +++ | AK-siting_authority-1 | AK |
| +++ | AL-siting_authority-1 | AL |
| +++ | AL-other-1 | AL |
| +++ | AL-other-2 | AL |
| +++ | AR-state_setback_standard-1 | AR |
| +++ | AZ-siting_authority-1 | AZ |
| +++ | CA-siting_authority-1 | CA |
| +++ | CA-local_preemption-1 | CA |
| +++ | CO-siting_authority-1 | CO |
| +++ | CO-local_preemption-1 | CO |
| +++ | CT-siting_authority-1 | CT |
| +++ | CT-local_preemption-1 | CT |
| +++ | CT-state_setback_standard-1 | CT |
| +++ | CT-state_setback_standard-2 | CT |
| +++ | CT-state_moratorium-1 | CT |
| +++ | CT-other-1 | CT |
| +++ | DE-siting_authority-1 | DE |
| +++ | FL-siting_authority-1 | FL |
| +++ | FL-local_preemption-1 | FL |
| +++ | FL-local_preemption-2 | FL |
| +++ | FL-state_moratorium-1 | FL |
| +++ | GA-siting_authority-1 | GA |
| +++ | HI-siting_authority-1 | HI |
| +++ | HI-other-1 | HI |
| +++ | IA-siting_authority-1 | IA |
| +++ | IA-local_preemption-1 | IA |
| +++ | ID-siting_authority-1 | ID |
| +++ | ID-other-1 | ID |
| +++ | IL-siting_authority-1 | IL |
| +++ | IL-local_preemption-1 | IL |
| +++ | IL-local_preemption-2 | IL |
| +++ | IL-local_preemption-3 | IL |
| +++ | IL-state_setback_standard-1 | IL |
| +++ | IL-state_setback_standard-2 | IL |
| +++ | IN-siting_authority-1 | IN |
| +++ | IN-local_preemption-1 | IN |
| +++ | IN-state_setback_standard-1 | IN |
| +++ | IN-state_setback_standard-2 | IN |
| +++ | KS-siting_authority-1 | KS |
| +++ | KS-other-1 | KS |
| +++ | KY-siting_authority-1 | KY |
| +++ | KY-state_setback_standard-1 | KY |
| +++ | KY-other-1 | KY |
| +++ | LA-siting_authority-1 | LA |
| +++ | LA-state_setback_standard-1 | LA |
| +++ | MA-siting_authority-1 | MA |
| +++ | MA-local_preemption-1 | MA |
| +++ | MA-local_preemption-2 | MA |
| +++ | MD-siting_authority-1 | MD |
| +++ | MD-local_preemption-1 | MD |
| +++ | MD-local_preemption-2 | MD |
| +++ | MD-state_setback_standard-1 | MD |
| +++ | MD-other-1 | MD |
| +++ | ME-siting_authority-1 | ME |
| +++ | ME-state_setback_standard-1 | ME |
| +++ | ME-state_moratorium-1 | ME |
| +++ | ME-other-1 | ME |
| +++ | MI-siting_authority-1 | MI |
| +++ | MI-local_preemption-1 | MI |
| +++ | MI-state_setback_standard-1 | MI |
| +++ | MN-siting_authority-1 | MN |
| +++ | MN-local_preemption-1 | MN |
| +++ | MN-other-1 | MN |
| +++ | MO-siting_authority-1 | MO |
| +++ | MS-siting_authority-1 | MS |
| +++ | MS-local_preemption-1 | MS |
| +++ | MT-siting_authority-1 | MT |
| +++ | MT-state_setback_standard-1 | MT |
| +++ | NC-siting_authority-1 | NC |
| +++ | ND-siting_authority-1 | ND |
| +++ | ND-state_setback_standard-1 | ND |
| +++ | NE-siting_authority-1 | NE |
| +++ | NH-siting_authority-1 | NH |
| +++ | NJ-siting_authority-1 | NJ |
| +++ | NJ-local_preemption-1 | NJ |
| +++ | NJ-other-1 | NJ |
| +++ | NM-siting_authority-1 | NM |
| +++ | NM-local_preemption-1 | NM |
| +++ | NV-siting_authority-1 | NV |
| +++ | NV-local_preemption-1 | NV |
| +++ | NY-siting_authority-1 | NY |
| +++ | NY-local_preemption-1 | NY |
| +++ | NY-state_setback_standard-1 | NY |
| +++ | NY-other-1 | NY |
| +++ | OH-siting_authority-1 | OH |
| +++ | OH-local_preemption-1 | OH |
| +++ | OH-state_setback_standard-1 | OH |
| +++ | OH-local_opt_out-1 | OH |
| +++ | OK-siting_authority-1 | OK |
| +++ | OK-state_setback_standard-1 | OK |
| +++ | OR-siting_authority-1 | OR |
| +++ | OR-local_preemption-1 | OR |
| +++ | OR-other-1 | OR |
| +++ | PA-siting_authority-1 | PA |
| +++ | PR-siting_authority-1 | PR |
| +++ | RI-siting_authority-1 | RI |
| +++ | RI-local_preemption-1 | RI |
| +++ | RI-other-1 | RI |
| +++ | SC-siting_authority-1 | SC |
| +++ | SC-local_preemption-1 | SC |
| +++ | SC-state_setback_standard-1 | SC |
| +++ | SD-siting_authority-1 | SD |
| +++ | SD-state_setback_standard-1 | SD |
| +++ | TN-state_setback_standard-1 | TN |
| +++ | TN-other-1 | TN |
| +++ | TX-siting_authority-1 | TX |
| +++ | UT-siting_authority-1 | UT |
| +++ | VA-siting_authority-1 | VA |
| +++ | VA-state_setback_standard-1 | VA |
| +++ | VA-other-1 | VA |
| +++ | VT-siting_authority-1 | VT |
| +++ | VT-local_preemption-1 | VT |
| +++ | VT-state_setback_standard-1 | VT |
| +++ | WA-siting_authority-1 | WA |
| +++ | WA-local_preemption-1 | WA |
| +++ | WI-siting_authority-1 | WI |
| +++ | WI-local_preemption-1 | WI |
| +++ | WI-local_preemption-2 | WI |
| +++ | WI-state_setback_standard-1 | WI |
| +++ | WV-siting_authority-1 | WV |
| +++ | WY-siting_authority-1 | WY |
| +++ | WY-state_setback_standard-1 | WY |
