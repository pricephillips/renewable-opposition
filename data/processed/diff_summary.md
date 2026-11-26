# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 53 |
| contested_projects | 0 | 0 | 0 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction | currency | months_in_force |
|---|---|---|---|---|---|
| -> | res_683dbf36c2 | CA | Imperial | in_force | 5.7->5.8 |
| -> | res_d15e0601e4 | CA | San Juan Capistrano | in_force | 20.2->20.3 |
| -> | res_e9f1af5f5d | CO | Grand County | in_force | 17.0->17.1 |
| -> | res_1ba648b44c | CO | Grand County | in_force | 17.0->17.1 |
| -> | res_b0a803b9a1 | CO | Grand County | in_force | 17.0->17.1 |
| -> | res_aa0244cd30 | IL | Utica | in_force | 7.5->7.6 |
| -> | res_2e44b5dd8f | IL | Utica | in_force | 7.5->7.6 |
| -> | res_3b1b9e57c3 | IN | Dearborn County | in_force | 9.0->9.1 |
| -> | res_7f59df981c | IN | Dearborn County | in_force | 9.0->9.1 |
| -> | res_fb7e366860 | IN | Elkhart | in_force | 2.9->3.0 |
| -> | res_5ed8f61ebb | IA | Adair County | in_force | 8.2->8.3 |
| -> | res_eb3be1294e | IA | Audubon County | in_force | 15.4->15.5 |
| -> | res_4386dd0d91 | KS | Dickinson County | in_force | 3.8->3.9 |
| -> | res_faab116695 | KS | Dickinson County | in_force | 3.8->3.9 |
| -> | res_e4af898e31 | KS | Dickinson County | in_force | 3.8->3.9 |
| -> | res_5c78669185 | KS | Riley County | in_force | 6.2->6.3 |
| -> | res_83d055e0a7 | LA | Iberville Parish | in_force | 4.3->4.4 |
| -> | res_afc4608b28 | MI | Gun Plain Charter Township | in_force | 3.6->3.7 |
| -> | res_c2a43ef06b | MI | Hillsdale Township (Hillsdale County) | in_force | 5.5->5.6 |
| -> | res_17332b412a | MI | Hillsdale Township (Hillsdale County) | in_force | 5.5->5.6 |
| -> | res_47f6518d82 | MI | Hillsdale Township (Hillsdale County) | in_force | 5.5->5.6 |
| -> | res_56fcf2fc81 | MI | Huron County (solar and battery storage) | in_force | 6.4->6.5 |
| -> | res_2a180b4ea5 | MI | Huron County (solar and battery storage) | in_force | 6.4->6.5 |
| -> | res_20b5316c49 | MI | Kalamazoo Township | in_force | 3.9->4.0 |
| -> | res_5006f40b4e | MI | Oshtemo Charter Township | in_force->lapsed_unconfirmed | 12.0 |
| -> | res_bc38ac7804 | MI | Portage | in_force | 9.0->9.1 |
| -> | res_7c97b89755 | MI | Webster Township | in_force | 7.1->7.2 |
| -> | res_d9e7cf22f1 | MO | City of Independence | in_force | 4.6->4.7 |
| -> | res_f2fbb7f97d | NY | Arietta | in_force | 5.3->5.4 |
| -> | res_337e1aa287 | NY | Berne | in_force | 18.6->18.7 |
| -> | res_db4c9ecfa0 | NY | Berne | in_force | 18.6->18.7 |
| -> | res_2c3ebcd3e6 | NY | Byron | in_force | 7.5->7.6 |
| -> | res_b0e70bce37 | NY | Byron | in_force | 7.5->7.6 |
| -> | res_018eb34b3d | NY | Denmark (Lewis County) | in_force | 9.7->9.8 |
| -> | res_cb60d4b791 | NY | Denmark (Lewis County) | in_force | 9.7->9.8 |
| -> | res_beaaa41e63 | NY | Hurley | in_force | 13.8->13.9 |
| -> | res_d70061dcc7 | NY | Lysander (Onondaga County) | in_force | 38.1->38.2 |
| -> | res_253610cf32 | NY | Town of Marcellus | in_force | 6.6->6.7 |
| -> | res_75251bd006 | NC | City of Wilson | in_force | 6.1->6.2 |
| -> | res_a75112e36b | ND | Dunn County | in_force | 8.2->8.3 |
| -> | res_f75f6d74fe | ND | Dunn County | in_force | 8.2->8.3 |
| -> | res_f56ae22ddd | OH | Village of Lordstown | in_force | 4.6->4.7 |
| -> | res_dfb0e7fab7 | PA | West Mahanoy Township | in_force | 2.3->2.4 |
| -> | res_ffe719f142 | TN | Anderson County | in_force | 5.3->5.4 |
| -> | res_fbd8b99662 | TN | Cocke County | in_force | 5.3->5.4 |
| -> | res_238bbaf8f5 | WA | Black Diamond | in_force | 8.7->8.8 |
| -> | res_2b9a846f42 | WA | Enumclaw | in_force | 21.0->21.1 |
| -> | res_14d759540f | WI | Monroe County | in_force | 4.1->4.2 |
| -> | res_96ea8a1174 | KY | Nicholas County | in_force | 2.2->2.3 |
| -> | res_41dacebc09 | KS | Bourbon County | in_force | 5.3->5.4 |
| -> | res_fdbf3b9e3d | KS | Bourbon County | in_force | 5.3->5.4 |
| -> | res_ea5a10d01b | KS | Crawford County | in_force | 11.4->11.5 |
| -> | res_bcee17309a | KS | Crawford County | in_force | 11.4->11.5 |
