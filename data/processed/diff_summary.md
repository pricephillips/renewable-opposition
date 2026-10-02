# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 29 |
| contested_projects | 0 | 0 | 1 |
| cases | 0 | 0 | 0 |

## Column changes

- restrictions: added `county_fips_all`, `county_fips_method`
- contested_projects: added `county_fips_all`, `county_fips_method`

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | restriction_type | jurisdiction | severity_basis |
|---|---|---|---|---|---|
| -> | res_66d7f44e41 | HI | setback | Honolulu City | wind setback 6600 ft / 0x height->wind setback 6600 ft |
| -> | res_d3dfa408f8 | IA | setback | Dallas County | wind setback 2640 ft / 0x height->wind setback 2640 ft |
| -> | res_75e99b2ba8 | ID | setback | Bingham County | wind setback 5280 ft / 0x height->wind setback 5280 ft |
| -> | res_b2f00e8272 | IL | setback | DeKalb County | wind setback 15840 ft / 0x height->wind setback 15840 ft |
| -> | res_029353e208 | IL | setback | Monroe County | wind setback 2640 ft / 0x height->wind setback 2640 ft |
| -> | res_a34404786e | IN | setback | Miami | wind setback 2640 ft / 0x height->wind setback 2640 ft |
| -> | res_fd0d691db9 | KS | height_limit->setback | Cherokee | wind setback 5250 ft / 0x height->wind setback 5250 ft |
| -> | res_dd5facad54 | MD | setback | Allegany | wind setback 5000 ft / 0x height->wind setback 5000 ft |
| -> | res_c8e3d88190 | ME | setback | Dixfield | wind setback 5280 ft / 0x height->wind setback 5280 ft |
| -> | res_06e32ef1aa | ME | setback | Freedom | wind setback 0 ft / 13x height->wind setback 13x height |
| -> | res_2f2cf007ae | MI | height_limit->setback | Claybanks Township | wind setback 3000 ft / 0x height->wind setback 3000 ft |
| -> | res_e517e13ceb | MT | setback | Wibaux County | wind setback 7920 ft / 0x height->wind setback 7920 ft |
| -> | res_ba1b926f2f | NC | setback | Carteret | wind setback 5280 ft / 0x height->wind setback 5280 ft |
| -> | res_71319018f9 | NC | setback | Craven | wind setback 5280 ft / 0x height->wind setback 5280 ft |
| -> | res_661b9f02a9 | NE | setback | Brown County | wind setback 5280 ft / 0x height->wind setback 5280 ft |
| -> | res_cca5e7b1c7 | NE | setback | Buffalo County | wind setback 10560 ft / 0x height->wind setback 10560 ft |
| -> | res_ee3bc1725d | NE | setback | Burt County | wind setback 15840 ft / 0x height->wind setback 15840 ft |
| -> | res_53565fbe1e | NE | setback | Cedar County | wind setback 5280 ft / 0x height->wind setback 5280 ft |
| -> | res_9cc4427902 | NE | setback | Dakota County | wind setback 10560 ft / 0x height->wind setback 10560 ft |
| -> | res_b935260821 | NE | setback | Hamilton County | wind setback 10560 ft / 0x height->wind setback 10560 ft |
| -> | res_b28e1324d3 | NE | setback | Holt County | wind setback 5280 ft / 0x height->wind setback 5280 ft |
| -> | res_56951854b6 | NY | setback | Farmersville | wind setback 3000 ft / 0x height->wind setback 3000 ft |
| -> | res_036786ece0 | OK | setback | Owasso | wind setback 7920 ft / 0x height->wind setback 7920 ft |
| -> | res_0fbddfd48f | OR | setback | Umatilla | wind setback 10560 ft / 0x height->wind setback 10560 ft |
| -> | res_4719af30b3 | SD | setback | Letcher Township | wind setback 5280 ft / 0x height->wind setback 5280 ft |
| -> | res_0af970e524 | SD | setback | Lincoln County | wind setback 2640 ft / 0x height->wind setback 2640 ft |
| -> | res_c231c2b93c | SD | setback | Walworth County | wind setback 10560 ft / 0x height->wind setback 10560 ft |
| -> | res_412e51c531 | WI | setback | Manitowoc County | wind setback 2640 ft / 0x height->wind setback 2640 ft |
| -> | res_4393c67d8b | WI | setback | Union | wind setback 2640 ft / 0x height->wind setback 2640 ft |

### contested_projects

| @@ | id | state | project_name | county_fips |
|---|---|---|---|---|
| -> | con_37179879f8 | IL | Alta Wind Farm | ->17039 |
