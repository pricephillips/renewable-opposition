# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 1 | 5 |
| contested_projects | 0 | 0 | 0 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| restrictions | res_938f4ae45c (Apache County, AZ) | status | unknown | active |
| restrictions | res_fed735544e (South Lyon City, MI) | status | unknown | active |
| restrictions | res_d718e836a2 (Pipestone County, MN) | status | unknown | active |
| restrictions | res_654b788349 (Vermilion Parish, LA) | status | unknown | active |
| restrictions | res_605ab0f3ef (Salisbury Town, VT) | status | unknown | active |

## Detail

### restrictions

| @@ | id | state | status | jurisdiction | currency | status_as_of | status_checked_on | status_evidence_url |
|---|---|---|---|---|---|---|---|---|
| -> | res_938f4ae45c | AZ | unknown->active | Apache County | unknown->in_force | ->2026-10-22 | ->2026-10-22 | ->https://ecs-cluster-bucket-wsos-prod-two.s3.us-west-2.amazonaws.com/uploads/sites/107/Utility-Renewable-Energy-Systems.pdf |
| --- | res_f73b458b6c | CO | unknown | Pueblo County | unknown |  |  |  |
| -> | res_fed735544e | MI | unknown->active | South Lyon City | unknown->in_force | ->2026-10-21 | ->2026-10-21 | ->https://cms5.revize.com/revize/southlyon/Zoning%20Ordinance%20FINAL%20with%20hyperlinks.pdf |
| -> | res_d718e836a2 | MN | unknown->active | Pipestone County | unknown->in_force | ->2026-10-21 | ->2026-10-21 | ->https://img1.wsimg.com/blobby/go/b84d0090-eb02-46e0-8112-ccf3eec10e72/downloads/Pipestone%20County%20Zoning%20Ordinance%201-9-18.pdf?ver=1790704640923 |
| -> | res_654b788349 | LA | unknown->active | Vermilion Parish | unknown->in_force | ->2026-10-22 | ->2026-10-22 | ->https://api.municode.com/CodesContent?jobId=483949&nodeId=COOR_CH42UT_ARTIISOWIFA&productId=15343 |
| -> | res_605ab0f3ef | VT | unknown->active | Salisbury Town | unknown->in_force | ->2026-10-21 | ->2026-10-21 | ->https://www.townofsalisbury.org/vertical/sites/%7B59D8C83C-9968-4A65-BB2B-00DE19899066%7D/uploads/Salisbury_App_EEnergy_Plan3_11_20.docx |
