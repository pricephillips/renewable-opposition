# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 191 |
| contested_projects | 0 | 0 | 0 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction | currency | ends_on | ends_on_basis | months_in_force |
|---|---|---|---|---|---|---|---|
| -> | res_683dbf36c2 | CA | Imperial | in_force | 2027-05-30 | record | 5.5->5.6 |
| -> | res_d15e0601e4 | CA | San Juan Capistrano | in_force |  |  | 20.0->20.1 |
| -> | res_e9f1af5f5d | CO | Grand County | in_force | 2027-06-24 | text | 16.8->16.9 |
| -> | res_1ba648b44c | CO | Grand County | in_force | 2027-06-24 | text | 16.8->16.9 |
| -> | res_b0a803b9a1 | CO | Grand County | in_force | 2027-06-24 | text | 16.8->16.9 |
| -> | res_695eb1b7c2 | CT | Morris | in_force | ->2028-05 | ->term | 6.6 |
| -> | res_aa0244cd30 | IL | Utica | in_force |  |  | 7.3->7.4 |
| -> | res_2e44b5dd8f | IL | Utica | in_force |  |  | 7.3->7.4 |
| -> | res_3b1b9e57c3 | IN | Dearborn County | in_force |  |  | 8.8->8.9 |
| -> | res_7f59df981c | IN | Dearborn County | in_force |  |  | 8.8->8.9 |
| -> | res_fb7e366860 | IN | Elkhart | in_force | 2027-12-31 | text | 2.7->2.8 |
| -> | res_7b36d14b7f | IN | Huntington County | in_force->lapsed_unconfirmed | ->2026-09 | ->text | 8.9->7.2 |
| -> | res_5ed8f61ebb | IA | Adair County | in_force |  |  | 8.0->8.1 |
| -> | res_eb3be1294e | IA | Audubon County | in_force | 2027-05-01 | record | 15.2->15.3 |
| -> | res_5b5ac548d9 | IA | Dickinson County | in_force->lapsed_unconfirmed | 2026-11-12 | text | 6.0 |
| -> | res_43e92f14af | IA | Dickinson County | in_force->lapsed_unconfirmed | 2026-11-12 | text | 6.0 |
| -> | res_a3d035aa67 | IA | Tama County | in_force->lapsed_unconfirmed | 2026-08-24 | text | 9.5 |
| -> | res_4386dd0d91 | KS | Dickinson County | in_force | 2027-07-30 | record | 3.6->3.7 |
| -> | res_faab116695 | KS | Dickinson County | in_force | 2027-07-30 | record | 3.6->3.7 |
| -> | res_e4af898e31 | KS | Dickinson County | in_force | 2027-07-30 | record | 3.6->3.7 |
| -> | res_5c78669185 | KS | Riley County | in_force |  |  | 6.0->6.1 |
| -> | res_357bbf6c40 | KY | Henderson County | in_force->lapsed_unconfirmed | 2026-10-28 | term | 12.0 |
| -> | res_83d055e0a7 | LA | Iberville Parish | in_force | 2028-07-15 | term | 4.1->4.2 |
| -> | res_f4d4403e34 | ME | Albion | in_force->lapsed_unconfirmed | ->2026-06 | ->text | 23.8->19.2 |
| -> | res_1531765a2c | ME | Albion | in_force->lapsed_unconfirmed | ->2026-06 | ->text | 23.8->19.2 |
| -> | res_935ea2a72c | MA | Chesterfield | in_force->lapsed_unconfirmed | 2026-09-30 | text | 3.2 |
| -> | res_d12620ee3f | MA | Westfield | in_force->lapsed_unconfirmed | 2026-09-30 | text | 7.8 |
| -> | res_6658d3c6e4 | MI | Casco Township (Allegan County) | in_force->lapsed_unconfirmed | 2026-10-20 | text | 6.0 |
| -> | res_379a7bcdd7 | MI | Casco Township (Allegan County) | in_force->lapsed_unconfirmed | 2026-10-20 | text | 6.0 |
| -> | res_0a3624cb01 | MI | Fayette Township (Hillsdale County) | pending | ->2027-07 | ->term | ->4.6 |
| -> | res_eabd8ef980 | MI | Fayette Township (Hillsdale County) | pending | ->2027-07 | ->term | ->4.6 |
| -> | res_afc4608b28 | MI | Gun Plain Charter Township | in_force | 2026-12-21 | record | 3.4->3.5 |
| -> | res_c2a43ef06b | MI | Hillsdale Township (Hillsdale County) | in_force | 2027-07-02 | text | 5.3->5.4 |
| -> | res_17332b412a | MI | Hillsdale Township (Hillsdale County) | in_force | 2027-07-02 | text | 5.3->5.4 |
| -> | res_47f6518d82 | MI | Hillsdale Township (Hillsdale County) | in_force | 2027-07-02 | text | 5.3->5.4 |
| -> | res_56fcf2fc81 | MI | Huron County (solar and battery storage) | in_force | 2026-12-29 | record | 6.2->6.3 |
| -> | res_2a180b4ea5 | MI | Huron County (solar and battery storage) | in_force | 2026-12-29 | record | 6.2->6.3 |
| -> | res_20b5316c49 | MI | Kalamazoo Township | in_force |  |  | 3.7->3.8 |
| -> | res_bc38ac7804 | MI | Portage | in_force | 2026-12-31 | record | 8.8->8.9 |
| -> | res_7c97b89755 | MI | Webster Township | in_force | 2027-04-21 | text | 6.9->7.0 |
| -> | res_d9e7cf22f1 | MO | City of Independence | in_force | 2027-01-02 | text | 4.4->4.5 |
| -> | res_af4ea77fbd | NE | Hitchcock County | pending | ->2028-05 | ->term |  |
| -> | res_d1e80919ed | NE | Hitchcock County | pending | ->2028-05 | ->term |  |
| -> | res_357aae4988 | NE | Hitchcock County | pending | ->2028-05 | ->term |  |
| -> | res_75734fceb1 | NY | Allen (Allegany County) | in_force->lapsed_unconfirmed | 2026-09-30 | text |  |
| -> | res_f2fbb7f97d | NY | Arietta | in_force | 2027-06-22 | text | 5.1->5.2 |
| -> | res_e3701fdf17 | NY | Aurora (Erie County) | in_force->lapsed_unconfirmed | 2026-06-09 | text | 12.4 |
| -> | res_337e1aa287 | NY | Berne | in_force |  |  | 18.4->18.5 |
| -> | res_db4c9ecfa0 | NY | Berne | in_force |  |  | 18.4->18.5 |
| -> | res_a6f75f7572 | NY | Brasher | in_force->lapsed_unconfirmed | 2026-10-31 | text |  |
| -> | res_2c3ebcd3e6 | NY | Byron | in_force |  |  | 7.3->7.4 |
| -> | res_b0e70bce37 | NY | Byron | in_force |  |  | 7.3->7.4 |
| -> | res_e00a7ea432 | NY | Cameron | in_force->lapsed_unconfirmed | 2026-08-31 | text | 23.0 |
| -> | res_b43a199a42 | NY | Cameron | in_force->lapsed_unconfirmed | 2026-08-31 | text | 23.0 |
| -> | res_e1d2224c2a | NY | Carlton | in_force->lapsed_unconfirmed | 2026-09-30 | text |  |
| -> | res_696d66789d | NY | Claverack | in_force->lapsed_unconfirmed | 2026-06-11 | text |  |
| -> | res_c11e735546 | NY | Collins | in_force->lapsed_unconfirmed | 2026-09-30 | text |  |
| -> | res_018eb34b3d | NY | Denmark (Lewis County) | in_force | 2027-02-03 | term | 9.5->9.6 |
| -> | res_cb60d4b791 | NY | Denmark (Lewis County) | in_force | 2027-02-03 | term | 9.5->9.6 |
| -> | res_b9c1c9eff7 | NY | Eden | in_force->lapsed_unconfirmed | 2026-09-30 | text |  |
| -> | res_f1e86e0b1b | NY | Ellery | in_force | ->2026-12 | ->term | 5.6 |
| -> | res_1ab1233ef7 | NY | Ellery | in_force | ->2026-12 | ->term | 5.6 |
| -> | res_fdc0bd59fd | NY | Ellery | in_force | ->2026-12 | ->term | 5.6 |
| -> | res_b4d9483faa | NY | Gainesville | in_force->lapsed_unconfirmed | 2026-10-20 | text |  |
| -> | res_21ed3f0f23 | NY | German Flatts | in_force->lapsed_unconfirmed | ->2026-05 | ->term | ->13.0 |
| -> | res_41361d106c | NY | German Flatts | in_force->lapsed_unconfirmed | ->2026-05 | ->term | ->13.0 |
| -> | res_9cb502c96f | NY | Hartwick | in_force->lapsed_unconfirmed | 2026-09-20 | text | 6.0 |
| -> | res_052a61f368 | NY | Huntington | in_force | ->2026-12 | ->term | 5.6 |
| -> | res_beaaa41e63 | NY | Hurley | in_force |  |  | 13.6->13.7 |
| -> | res_2f95b1510f | NY | Kent (Putnam County) | in_force->lapsed_unconfirmed | 2026-08-31 | text | 25.7 |
| -> | res_d70061dcc7 | NY | Lysander (Onondaga County) | in_force | 2026-12-18 | text | 37.9->38.0 |
| -> | res_415c0abafe | NY | Mina | in_force | 2025-11-02-> | term-> | 6.0->18.6 |
| -> | res_6af7cf0cf0 | NY | New Castle | in_force->lapsed_unconfirmed | 2025-08-11->2026-08 | term->text | 6.0->18.7 |
| -> | res_108995efdf | NY | North Hempstead | in_force->lapsed_unconfirmed | 2026-11-18 | text | 23.5 |
| -> | res_0bb5121b24 | NY | Peekskill | in_force->lapsed_unconfirmed | 2026-05-24 | text | 14.0 |
| -> | res_1803ef1c62 | NY | Prattsburgh | in_force->lapsed_unconfirmed | ->2025-04 | ->term | ->7.0 |
| -> | res_eab222a0b1 | NY | Prattsburgh | in_force->lapsed_unconfirmed | ->2025-04 | ->term | ->7.0 |
| -> | res_ebb9baf26f | NY | Smithtown | in_force->lapsed_unconfirmed | 2026-10-23 | text | 25.1 |
| -> | res_d6a569c01f | NY | Southport | in_force->lapsed_unconfirmed | 2026-04-14 | text | 14.1 |
| -> | res_468d6495cc | NY | Southport | in_force->lapsed_unconfirmed | 2026-04-14 | text | 14.1 |
| -> | res_827ab8c445 | NY | Stanford | in_force | 2025-11-14-> | term-> | 12.0->24.2 |
| -> | res_301b6660ab | NY | Stanford | in_force | 2025-11-14-> | term-> | 12.0->24.2 |
| -> | res_7a7feac939 | NY | Ticonderoga | in_force | ->2026-11 | ->term | 6.6 |
| -> | res_253610cf32 | NY | Town of Marcellus | in_force | ->2027-05 | ->text | 6.4->6.5 |
| -> | res_35efeb1fb2 | NY | Town of Northampton | in_force | ->2027-03 | ->term | 8.6 |
| -> | res_13585c4d9b | NY | Town of Sherburne | in_force | 2026-07-14-> | term-> | 6.0->10.2 |
| -> | res_4921cbf856 | NY | Virgil | in_force->lapsed_unconfirmed | 2026-09-30 | text |  |
| -> | res_41dfd1b666 | NY | West Bloomfield | in_force->lapsed_unconfirmed | 2026-09-11 | text | 24.0 |
| -> | res_17c4603104 | NY | West Bloomfield | in_force->lapsed_unconfirmed | 2026-09-11 | text | 24.0 |
| -> | res_5fad04fc44 | NY | Yonkers | in_force->lapsed_unconfirmed | 2026-03-31 | text | 20.5 |
| -> | res_75251bd006 | NC | City of Wilson | in_force | 2027-05-21 | record | 5.9->6.0 |
| -> | res_a75112e36b | ND | Dunn County | in_force | 2027-03-18 | term | 8.0->8.1 |
| -> | res_f75f6d74fe | ND | Dunn County | in_force | 2027-03-18 | term | 8.0->8.1 |
| -> | res_f56ae22ddd | OH | Village of Lordstown | in_force | 2027-01-02 | text | 4.4->4.5 |
| -> | res_cf0a4c6640 | OR | City of Hillsboro | in_force | 2026-11-24 | text | 3.7->3.8 |
| -> | res_b9948e27eb | PA | Adams Township (Butler County) | in_force->lapsed_unconfirmed | 2026-09-23 | text | 2.3 |
| -> | res_dfb0e7fab7 | PA | West Mahanoy Township | in_force |  |  | 2.1->2.2 |
| -> | res_9aa8e37604 | SD | Pennington County | in_force->lapsed_unconfirmed | 2026-11-18 | text | 24.0 |
| -> | res_c228a38a3e | SD | Pennington County | in_force->lapsed_unconfirmed | 2026-11-18 | text | 24.0 |
| -> | res_ffe719f142 | TN | Anderson County | in_force | 2028-06-15 | term | 5.1->5.2 |
| -> | res_fbd8b99662 | TN | Cocke County | in_force | 2027-06-30 | text | 5.1->5.2 |
| -> | res_b3fc1c63e7 | TX | Austin County | in_force->lapsed_unconfirmed | 2026-09-23 | text | 1.9 |
| -> | res_238bbaf8f5 | WA | Black Diamond | in_force | 2027-03-01 | record | 8.5->8.6 |
| -> | res_d768a363b3 | WA | Bonney Lake | in_force->lapsed_unconfirmed | 2026-10-11 | text | 5.9 |
| -> | res_2b9a846f42 | WA | Enumclaw | in_force | 2027-02-24 | record | 20.8->20.9 |
| -> | res_14d759540f | WI | Monroe County | in_force |  |  | 3.9->4.0 |
| -> | res_bdff8bd6ce | AR | Carroll County | in_force | ->2030-05 | ->term | ->18.6 |
| -> | res_83371d0298 | AR | Carroll County | in_force | ->2030-05 | ->term | ->18.6 |
| -> | res_6dcb5d629d | AZ | Mohave County | in_force->lapsed_unconfirmed | ->2024-02 | ->term | ->4.9 |
| -> | res_3083700b99 | CO | Mesa County | in_force->lapsed_unconfirmed | ->2024-07 | ->term | ->7.0 |
| -> | res_b8532ebc3d | CO | Phillips County | in_force->lapsed_unconfirmed | 2026-03-30 | text |  |
| -> | res_d8d6d5d5b8 | CO | Phillips County | in_force->lapsed_unconfirmed | 2026-03-30 | text |  |
| -> | res_04e99ce656 | CO | San Miguel County | in_force->lapsed_unconfirmed | ->2024-11 | ->text |  |
| -> | res_f58ec65c21 | GA | Oglethorpe County | in_force->lapsed_unconfirmed | ->2023-09 | ->text |  |
| -> | res_2a494842cd | GA | Thomas County | in_force->lapsed_unconfirmed | ->2017-05 | ->text |  |
| -> | res_cbb289c104 | IA | Cerro Gordo County | in_force->lapsed_unconfirmed | ->2024-08 | ->term | ->16.0 |
| -> | res_d6bf5568a4 | IA | Cerro Gordo County | in_force->lapsed_unconfirmed | ->2024-08 | ->term | ->16.0 |
| -> | res_051d64d201 | IA | Cerro Gordo County | in_force->lapsed_unconfirmed | ->2024-08 | ->term | ->16.0 |
| -> | res_931cdd87e1 | IA | Clinton County | in_force->lapsed_unconfirmed | ->2025-06 | ->text |  |
| -> | res_29265191bd | IA | Decatur County | in_force->lapsed_unconfirmed | 2026-06-01 | text |  |
| -> | res_b247af8597 | IA | Decatur County | in_force->lapsed_unconfirmed | 2026-06-01 | text |  |
| -> | res_28f98d975d | IA | Floyd County | in_force->lapsed_unconfirmed | 2024-05-20 | text |  |
| -> | res_57cb715999 | IA | Henry County | in_force->lapsed_unconfirmed | ->2025-04 | ->term | ->13.0 |
| -> | res_f8168e424d | IL | Piatt County | in_force->lapsed_unconfirmed | ->2023-09 | ->text |  |
| -> | res_2c890bb404 | IN | Boone County | in_force->lapsed_unconfirmed | ->2026-04 | ->term | ->25.0 |
| -> | res_a999b39708 | IN | Boone County | in_force->lapsed_unconfirmed | ->2026-04 | ->term | ->25.0 |
| -> | res_4efc8b5ddb | IN | Boone County | in_force->lapsed_unconfirmed | ->2026-04 | ->term | ->25.0 |
| -> | res_c6a4ec775e | KS | Harvey County | in_force->lapsed_unconfirmed | ->2023-08 | ->term | ->7.0 |
| -> | res_c5fd6999ab | KS | Harvey County | in_force->lapsed_unconfirmed | ->2023-08 | ->term | ->7.0 |
| -> | res_bd07588f07 | KS | Linn County | in_force->lapsed_unconfirmed | ->2021-12 | ->text |  |
| -> | res_4e8540171c | KS | Pottawatomie County | in_force->lapsed_unconfirmed | ->2024-11 | ->term | ->13.0 |
| -> | res_3f92cbabd0 | KS | Reno County | in_force->lapsed_unconfirmed | ->2022-03 | ->text |  |
| -> | res_8240e89d68 | KS | Sedgwick County | in_force->lapsed_unconfirmed | ->2024-09 | ->text |  |
| -> | res_0aa4467c55 | KS | Sedgwick County | in_force->lapsed_unconfirmed | ->2024-09 | ->text |  |
| -> | res_b1a701e7bc | KS | Shawnee County | in_force->lapsed_unconfirmed | ->2025-06 | ->term | ->13.0 |
| -> | res_ae47ea2963 | KS | Shawnee County | in_force->lapsed_unconfirmed | ->2025-06 | ->term | ->13.0 |
| -> | res_fef7abd18a | KS | Wabaunsee County | in_force | ->2028-05 | ->term | ->42.6 |
| -> | res_70c4695157 | KS | Woodson County | in_force->lapsed_unconfirmed | ->2026-02 | ->text |  |
| -> | res_89925635c6 | KS | Woodson County | in_force->lapsed_unconfirmed | ->2026-02 | ->text |  |
| -> | res_de45b44793 | MA | Town of Blandford | in_force->lapsed_unconfirmed | 2026-05-31 | text |  |
| -> | res_1e7c6ca0f5 | MA | Town of Blandford | in_force->lapsed_unconfirmed | 2026-05-31 | text |  |
| -> | res_fbc3079b81 | MA | Town of Northfield | in_force->lapsed_unconfirmed | ->2025-05 | ->term | ->13.0 |
| -> | res_87d65f767d | MA | Town of Northfield | in_force->lapsed_unconfirmed | ->2025-05 | ->term | ->13.0 |
| -> | res_e5a513f63a | ME | Albion | in_force->lapsed_unconfirmed | ->2023-09 | ->term | ->7.0 |
| -> | res_1a7efc63cd | ME | City of Brewer | in_force->lapsed_unconfirmed | ->2024-02 | ->term | ->6.9 |
| -> | res_77cc7aac01 | ME | Town of Cutler | in_force->lapsed_unconfirmed | ->2025-08 | ->text |  |
| -> | res_fa70628e29 | ME | Town of Glenburn | in_force->lapsed_unconfirmed | ->2021-06 | ->term | ->3.0 |
| -> | res_44f8f7e6f9 | ME | Town of Weld | in_force->lapsed_unconfirmed | ->2023-12 | ->term | ->7.0 |
| -> | res_d343965aee | MI | Augusta Township | in_force->lapsed_unconfirmed | ->2022-09 | ->term | ->7.0 |
| -> | res_71283fdfa1 | MI | Clinton County | in_force->lapsed_unconfirmed | ->2024-05 | ->term | ->13.0 |
| -> | res_47dc719881 | MI | Elmwood Township | in_force->lapsed_unconfirmed | ->2017-03 | ->term | ->13.0 |
| -> | res_a0a73e1851 | MI | Genoa Township | in_force->lapsed_unconfirmed | ->2023-09 | ->term | ->7.0 |
| -> | res_698588ff4b | MI | Huron County | in_force->lapsed_unconfirmed | ->2016-11 | ->term | ->13.0 |
| -> | res_9b22c847ab | MI | Iosco Township | in_force->lapsed_unconfirmed | ->2023-08 | ->term | ->7.0 |
| -> | res_9405ea9316 | MI | Iosco Township | in_force->lapsed_unconfirmed | ->2023-08 | ->term | ->7.0 |
| -> | res_3b4d20f2ca | MI | White River Township | in_force->lapsed_unconfirmed | ->2023-07 | ->term | ->7.0 |
| -> | res_6ff144a6e2 | MI | White River Township | in_force->lapsed_unconfirmed | ->2023-07 | ->term | ->7.0 |
| -> | res_e79b7f8860 | MN | Chippewa County | in_force->lapsed_unconfirmed | ->2025-02 | ->term | ->12.9 |
| -> | res_742d1b5f08 | ND | McLean County | in_force->lapsed_unconfirmed | ->2022-08 | ->term | ->25.0 |
| -> | res_b74210fb25 | NE | Gage County | in_force->lapsed_unconfirmed | ->2020-10 | ->term | ->4.0 |
| -> | res_805639de1b | NE | Gage County | in_force->lapsed_unconfirmed | ->2020-10 | ->term | ->4.0 |
| -> | res_978e990261 | NE | Greeley County | in_force | ->2027-04 | ->term | ->31.6 |
| -> | res_21b64ad370 | NE | Greeley County | in_force | ->2027-04 | ->term | ->31.6 |
| -> | res_7e46c6479c | NE | Lincoln County | in_force->lapsed_unconfirmed | ->2024-03 | ->term | ->13.0 |
| -> | res_229c3ab473 | NE | Lincoln County | in_force->lapsed_unconfirmed | ->2024-03 | ->term | ->13.0 |
| -> | res_efa7f1fcf1 | NV | Nye County | in_force->lapsed_unconfirmed | ->2023-05 | ->term | ->7.0 |
| -> | res_7cc607c0ab | NV | Nye County | in_force->lapsed_unconfirmed | ->2023-05 | ->term | ->7.0 |
| -> | res_00d7467877 | NY | Broome County | in_force | ->2026-12 | ->term | ->11.6 |
| -> | res_c3a398b80c | NY | City of Olean | in_force->lapsed_unconfirmed | ->2024-05 | ->term | ->13.0 |
| -> | res_924315be10 | NY | Enfield | in_force->lapsed_unconfirmed | ->2019-11 | ->text |  |
| -> | res_40b7c01acb | NY | Enfield | in_force->lapsed_unconfirmed | ->2019-11 | ->text |  |
| -> | res_9ee255a16a | NY | Town of Canajoharie | in_force->lapsed_unconfirmed | ->2022-11 | ->term | ->10.0 |
| -> | res_2b04aa9073 | NY | Town of Clayton | in_force->lapsed_unconfirmed | ->2016-10 | ->term | ->7.0 |
| -> | res_d86c600f7c | NY | Town of Clifton Park | in_force->lapsed_unconfirmed | ->2021-07 | ->term | ->7.0 |
| -> | res_b8e468ccab | NY | Town of Dryden | in_force->lapsed_unconfirmed | ->2017-01 | ->term | ->7.0 |
| -> | res_e926a0ce47 | NY | Town of Duanesburg | in_force->lapsed_unconfirmed | ->2020-07 | ->term | ->7.0 |
| -> | res_84f6ab3894 | NY | Town of Glenville | in_force->lapsed_unconfirmed | ->2026-04 | ->term | ->25.0 |
| -> | res_973e3660aa | NY | Town of Hoosick | in_force->lapsed_unconfirmed | ->2025-03 | ->term | ->13.0 |
| -> | res_aabafef997 | NY | Town of Hoosick | in_force->lapsed_unconfirmed | ->2025-03 | ->term | ->13.0 |
| -> | res_365ec2a04a | NY | Town of Lyme | in_force->lapsed_unconfirmed | ->2025-12 | ->term | ->13.0 |
| -> | res_aecb1d0fc7 | NY | Town of Lyme | in_force->lapsed_unconfirmed | ->2025-12 | ->term | ->13.0 |
| -> | res_970905d4d3 | RI | City of Warwick | in_force->lapsed_unconfirmed | ->2022-05 | ->term | ->7.0 |
| -> | res_52055abc58 | SC | Calhoun County | in_force->lapsed_unconfirmed | ->2023-09 | ->term | ->7.0 |
| -> | res_a61c658822 | WA | Grant County | in_force->lapsed_unconfirmed |  |  |  |
| -> | res_3c395894f2 | WI | Sawyer County | in_force->lapsed_unconfirmed | ->2026-05 | ->term | ->10.0 |
| -> | res_038a3f0ab7 | WI | Sawyer County | in_force->lapsed_unconfirmed | ->2026-05 | ->term | ->10.0 |
| -> | res_96ea8a1174 | KY | Nicholas County | in_force | 2027-09-18 | term | 2.0->2.1 |
| -> | res_41dacebc09 | KS | Bourbon County | in_force |  |  | 5.1->5.2 |
| -> | res_fdbf3b9e3d | KS | Bourbon County | in_force |  |  | 5.1->5.2 |
| -> | res_ea5a10d01b | KS | Crawford County | in_force | 2026-12-31 | record | 11.2->11.3 |
| -> | res_bcee17309a | KS | Crawford County | in_force | 2026-12-31 | record | 11.2->11.3 |
