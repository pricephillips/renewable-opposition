# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 8 | 0 | 0 |
| contested_projects | 2 | 0 | 27 |
| cases | 0 | 0 | 0 |

## Column changes

- contested_projects: added `source_kind`, `source_access`, `queue_id`, `pinned_id`

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction |
|---|---|---|---|
| +++ | res_b87383a66e | KS | Cherokee County |
| +++ | res_87d3ae709d | KS | Cherokee County |
| +++ | res_ef13884340 | KS | Cherokee County |
| +++ | res_06983fc527 | IA | Clarke County |
| +++ | res_1e8c482aac | IN | Jay County |
| +++ | res_0f243e591d | ID | Ada County |
| +++ | res_00c3574156 | IN | Jay County |
| +++ | res_502ffdbf02 | IN | Jay County |

### contested_projects

| @@ | id | state | project_name | opposition_groups | group_sources |
|---|---|---|---|---|---|
| -> | con_21e7d9c759 | AR | Nimbus Wind Farm | ->Stop Wind Farms | ->https://katv.com/news/local/ozark-mountain-residents-opposing-arkansas-first-wind-farm-project-caroline-rogers-richard-williams-scout-clean-energy-nimbus-wind-turbine-green-energy-green-forrest-carroll-county-nature-natural-state-stop-wind-farms-crittenden-cross-quorum-court-lease |
| -> | con_6359ae7dee | AR | Wind Catcher Energy Connection Project | ->Protect Our Pocketbooks | ->https://talkbusiness.net/2018/05/arkansas-regulators-approve-4-5-billion-wind-catcher-project/ |
| -> | con_27bceb8c04 | CA | Aramis Solar Project | ->Save North Livermore Valley | ->https://www.independentnews.com/news/livermore_news/appeal-to-overturn-aramis-is-rejected/article_de468716-3c4d-11ee-8079-d32866c986ce.html |
| -> | con_96ea3bcabe | DE | Cedar Creek Solar | ->Citizens Against Solar Pollution | ->https://townsquaredelaware.com/lawsuit-filed-to-stop-construction-of-smyrna-solar-farm/ |
| -> | con_0fec93e3ad | DE | Skipjack Wind Farm Interconnection Facility in Fenwick State Park | ->Surfrider Foundation | ->https://delaware.surfrider.org/campaigns/Reject%20the%20Proposed%20Skipjack%20Wind%20Project%20Cable%20Landing%20Proposal |
| -> | con_dbf3969a3f | FL | Sand Bluff Solar Project | ->NAACP; Sierra Club | ->https://www.wcjb.com/2021/04/26/activist-groups-speak-out-against-archer-solar-array-project-alachua-county-plan-board-approves/ |
| -> | con_688bb69672 | KY | Hardin Solar LLC Project | ->Hardin County Citizens for Responsible Solar | ->https://www.thenewsenterprise.com/news/local/group-organized-to-fight-industrial-solar/article_5b1022c3-ae9c-5601-82d5-fa18103a42c2.html |
| -> | con_c4b18e3d55 | KY | Stonefield Solar Project | ->Hardin County Citizens for Responsible Solar | ->https://www.thenewsenterprise.com/news/local/group-organized-to-fight-industrial-solar/article_5b1022c3-ae9c-5601-82d5-fa18103a42c2.html |
| -> | con_db91d6c999 | MA | Cape Wind | ->Alliance to Protect Nantucket Sound | ->https://www.wbur.org/news/2010/06/25/cape-wind-lawsuit |
| -> | con_07787373eb | MD | Dan’s Mountain Wind Farm | ->Allegany Neighbors and Citizens for Home Owners Rights | ->https://news.yahoo.com/battle-over-wind-turbines-returns-131800093.html |
| -> | con_472ba8991c | MO | Osborn Wind Project | ->Concerned Citizens for the Future of Clinton and DeKalb Counties | ->https://www.newstribune.com/news/2016/may/12/residents-fight-wind-farm-dekalb-clinton-counties/ |
| -> | con_151c377188 | MT | Mission Creek Wind Project | ->Friends of Mission Creek | ->https://www.bozemandailychronicle.com/news/across-southwest-montana-companies-plan-to-ramp-up-the-region-s-wind-industry-it-hasn/article_ce7fb7f6-df2e-11df-8801-001cc4c002e0.html |
| -> | con_b5e0b42044 | NJ | Atlantic Shores South Project | ->Save Long Beach Island | ->https://ocnjsentinel.com/?p=76634 |
| -> | con_23b3856e4c | NJ | New York Bight Offshore Wind Area | ->Save Long Beach Island | ->https://electrek.co/?p=220025 |
| -> | con_37a3a8f59f | NV | Bajle Born Solar Project | ->Save Our Mesa | ->https://knpr.org/knpr/2020-12/overton-logandale-residents-rally-against-massive-solar-project |
| -> | con_03ffbab77e | NV | Beajy Energy Center Project | ->Basin and Range Watch | ->https://pvtimes.com/news/beatty-balks-at-solar-project-101545/ |
| -> | con_5b701c8ea7 | NV | Greenlink West Transmission Project | ->Basin and Range Watch | ->https://pvtimes.com/news/federal-review-of-greenlink-west-project-begins-109901/ |
| -> | con_c5156cfe2a | OK | Cabin Creek Wind Farm | ->Craig County Concerned Citizens | ->https://www.newson6.com/story/672452dee8b932ec3534ce4a/oklahomas-own-in-focus:-craig-county-zoning-proposition-aims-to-restrict-wind-turbine-construction |
| -> | con_497edaf406 | OR | Beehive Solar Project | ->1,000 Friends of Oregon | ->https://www.oregon.gov/luba/Docs/Opinions/2018/07-18/18060.pdf |
| -> | con_a8e3b7177a | OR | Boardman-to-Hemingway Transmission Line | ->STOP B2H Coalition | ->https://bakercityherald.com/2020/11/12/state-nation-world-business-and-ag-news |
| -> | con_b9a2dc6c7a | OR | Echanis Wind Farm | ->Oregon Natural Desert Association | ->https://www.klcc.org/2016-05-26/judges-reject-steens-mountain-wind-project |
| -> | con_ba4d87b309 | OR | Origis Energy Solar Project | ->1,000 Friends of Oregon | ->https://katu.com/news/local/land-use-group-tries-to-stop-oregon-solar-farm |
| -> | con_c0061d8d93 | OR | Steens Wind | ->Oregon Natural Desert Association; Portland Audubon Society | ->https://oregonbusiness.com/7227-groups-sue-over-proposed-wind-farm/ |
| -> | con_65a8c56898 | TX | Mustang Wind Project | ->FayCoSaysNo | ->https://www.fayettecountyrecord.com/news/opposition-mounts-against-wind-energy-project-here |
| -> | con_05d2969096 | WA | Columbia Solar Project | ->Save Our Farms | ->https://www.spokesman.com/stories/2018/apr/27/solar-panels-on-farmland-stir-fight-in-central-was/ |
| -> | con_16950d2943 | WY | Pioneer Wind Parks I and II | ->Northern Laramie Range Alliance | ->https://www.wyomingpublicmedia.org/news/2012-12-18/citizens-group-loses-wyo-wind-farm-challenge |
| -> | con_552afd0839 | WY | Rock Creek Gen-Tie Line | ->Albany County Conservancy | ->https://cowboystatedaily.com/2023/08/01/lawsuit-claims-blm-excluded-public-with-secret-approval-of-wind-project/ |
| +++ | con_f906e5d6eb | IA | Coggon Solar | Iowa for Responsible Solar | https://corridorbusiness.com/linn-supervisors-give-green-light-to-coggon-solar-project/ |
| +++ | con_b6d7252c8a | KS | Rainbow Springs Solar |  |  |
