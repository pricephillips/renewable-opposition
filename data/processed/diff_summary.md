# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 61 |
| contested_projects | 0 | 0 | 0 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction | currency | months_in_force |
|---|---|---|---|---|---|
| -> | res_d800b671a0 | CA | Morgan Hill | in_force | 2.9->3.0 |
| -> | res_5003f748a1 | IL | City of West Chicago | in_force | 4.1->4.2 |
| -> | res_c71cadf8a3 | IL | Sterling | in_force | 2.5->2.6 |
| -> | res_474c83417c | IN | Putnam County | in_force | 12.2->12.3 |
| -> | res_c1fc1fefb8 | IN | Putnam County | in_force | 12.2->12.3 |
| -> | res_55a77dd03c | IA | Henry County | in_force | 6.3->6.4 |
| -> | res_3d9daa14e1 | IA | Jackson County | in_force | 34.7->34.8 |
| -> | res_f2c9ca8cc1 | IA | Madison County | in_force | 5.9->6.0 |
| -> | res_2e86541afe | IA | Shelby County | in_force | 8.2->8.3 |
| -> | res_652e45dcbf | IA | Shelby County | in_force | 8.2->8.3 |
| -> | res_2ba4ec788f | IA | Shelby County | in_force | 8.2->8.3 |
| -> | res_527a1dc866 | IA | Story County | in_force | 17.2->17.3 |
| -> | res_af963b1c8d | KS | Brown County | in_force | 8.7->8.8 |
| -> | res_0d2122ecfe | KS | Brown County | in_force | 8.7->8.8 |
| -> | res_0110318ca3 | KS | Lyon County | in_force | 4.0->4.1 |
| -> | res_ac1d7084ff | KS | Marion County | in_force | 8.7->8.8 |
| -> | res_6a34b6143a | KS | Sedgwick County | in_force | 8.4->8.5 |
| -> | res_8b4294e62e | KS | Sedgwick County | in_force | 5.2->5.3 |
| -> | res_f9da48d14b | KS | South Hutchinson | in_force | 5.9->6.0 |
| -> | res_8c04d9587b | ME | Warren | in_force | 4.5->4.6 |
| -> | res_4a0069a5be | MI | Allendale Township | in_force | 5.5->5.6 |
| -> | res_a83d69672e | MI | Allendale Township | in_force | 5.5->5.6 |
| -> | res_27db754062 | MI | Allendale Township | in_force | 5.5->5.6 |
| -> | res_daead303c0 | MI | Kalamazoo | in_force | 3.2->3.3 |
| -> | res_78310c4fca | MI | Oshtemo Charter Township | in_force | 3.4->3.5 |
| -> | res_937d40a25c | MO | Cedar County | in_force | 2.5->2.6 |
| -> | res_a986d9d2c2 | MO | Cedar County | in_force | 2.5->2.6 |
| -> | res_79b5d401a8 | MO | Cedar County | in_force | 2.5->2.6 |
| -> | res_e843ecae6e | NE | Fillmore County | in_force | 5.0->5.1 |
| -> | res_d6473e9e31 | NE | Furnas County | in_force | 14.9->15.0 |
| -> | res_522547f218 | NE | Furnas County | in_force | 14.9->15.0 |
| -> | res_f0138898e6 | NY | Amsterdam | in_force | 11.7->11.8 |
| -> | res_cdad6a0cc5 | NY | Amsterdam | in_force | 11.7->11.8 |
| -> | res_339b87c3bc | NY | Babylon | in_force | 29.6->29.7 |
| -> | res_415c0abafe | NY | Mina | in_force | 18.7->18.8 |
| -> | res_ec8c140b2a | NY | Oswego City | in_force | 15.4->15.5 |
| -> | res_c7a491e45b | NY | Oswego City | in_force | 15.4->15.5 |
| -> | res_2048a509c2 | NY | Oswego City | in_force | 15.4->15.5 |
| -> | res_6d03ba619a | NY | Salem | in_force | 13.5->13.6 |
| -> | res_df5a8f6e89 | NY | Spafford | in_force | 6.3->6.4 |
| -> | res_827ab8c445 | NY | Stanford | in_force | 24.3->24.4 |
| -> | res_301b6660ab | NY | Stanford | in_force | 24.3->24.4 |
| -> | res_13585c4d9b | NY | Town of Sherburne | in_force | 10.3->10.4 |
| -> | res_72227f0bb2 | NY | Victory | in_force | 25.3->25.4 |
| -> | res_121f280a3c | NC | Pasquotank County (solar) | in_force | 4.1->4.2 |
| -> | res_cf0a4c6640 | OR | City of Hillsboro | in_force->lapsed_unconfirmed | 3.9 |
| -> | res_243cf763f3 | PA | Bensalem Township | in_force | 5.5->5.6 |
| -> | res_91dd06320d | PA | Bensalem Township | in_force | 5.5->5.6 |
| -> | res_5e4ee7185f | SC | Clarendon County | in_force | 2.3->2.4 |
| -> | res_efd77e0084 | SC | Sumter County | in_force | 3.4->3.5 |
| -> | res_a433db3007 | SC | Sumter County | in_force | 3.4->3.5 |
| -> | res_feb8d9a2ca | SD | Turner County | in_force | 14.9->15.0 |
| -> | res_c54aa497ff | SD | Turner County | in_force | 14.9->15.0 |
| -> | res_feaccae59d | UT | Iron County | in_force | 5.9->6.0 |
| -> | res_31ac77819c | WA | Duvall | in_force | 5.7->5.8 |
| -> | res_faf4dafac9 | WA | Kitsap County | in_force | 17.4->17.5 |
| -> | res_ea436715ca | WA | Snoqualmie | in_force | 5.9->6.0 |
| -> | res_fbc32b9a1a | WI | Door County | in_force | 5.9->6.0 |
| -> | res_6c30dff453 | KY | Nicholas County | in_force | 3.3->3.4 |
| -> | res_72ef3a10d7 | IA | Mitchell County | in_force | 1.8->1.9 |
| -> | res_2ec4bd8184 | IL | Assumption | in_force | 85.7->85.8 |
