# CERTUS migration audit report

Generated: 2026-06-22T12:47:37.475629
Repo: `D:\1406\1406`
Verdict hint: **LIKELY_SUCCESS**

## Legacy pattern audit
- `progress\.emit\(`: 0 match(es)
- `signals\.progress\.emit\(`: 0 match(es)
- `self\.progress\.emit\(`: 0 match(es)

## Positive migration signals
- `progress_snapshot`: 138 match(es)
- `build_progress_snapshot\(`: 94 match(es)
- `StepState`: 148 match(es)
- `format_eta\(`: 8 match(es)

## Tests
- `tests/ui/test_u8_u11_ux_widgets.py`: return code `0`
```text
certus\workers\certus_design_workers_needle_strat.py     127    100     40      0    16%   22, 27, 32, 37, 42, 48-84, 90-110, 116-157
certus\workers\certus_design_workers_strat.py            309    263    110      0    11%   23, 28, 33, 38, 43, 71-104, 137-139, 145, 151-153, 159-162, 168-253, 259-282, 288-359, 365, 371-402, 408-415, 421-422
certus\workers\certus_field_workers.py                   488    409    178      8    14%   19-20, 27, 30, 36, 39, 44-46, 69-138, 161-177, 180-181, 201, 206, 224, 231->234, 250-314, 326-486, 498-919
certus\workers\certus_field_workers_dto.py                99     23     14      4    71%   13-16, 19-22, 25, 28, 59, 61-64, 71, 77-79, 84-87, 97->exit
certus\workers\certus_index_workers.py                   532    363    118     13    28%   35->37, 39, 46-70, 85, 95, 99-100, 121-137, 140->146, 143->146, 147, 164-170, 173, 177, 180-181, 184-185, 188-189, 192-193, 196-197, 200-234, 237-238, 254-267, 279-281, 285, 296, 298, 300->303, 304->exit, 319, 334-346, 350-352, 356-358, 362-392, 406-414, 428-429, 432-433, 436, 440, 444-452, 455-456, 459-460, 463-464, 467-582, 585-587, 590-591, 606-611, 614, 618-652
certus\workers\certus_re_worker_utils.py                 200    165     44      0    14%   39-41, 58-72, 87-143, 160-179, 199-207, 221-238, 261, 268, 273, 278-281, 293-301, 307-316, 336-374, 398-414, 432-438, 456-482, 488-505, 522-541, 550-553, 572-606, 623, 635, 647, 671-674, 687, 701, 724-732
certus\workers\certus_re_workers.py                      177     80      2      0    54%   52-56, 60, 63-64, 67-68, 71-72, 75-76, 79-80, 83-84, 87-88, 91-92, 95-96, 99-100, 103-104, 107-108, 111-112, 115-116, 119-120, 124, 128-129, 148-157, 160-161, 164-165, 168-169, 172-173, 176-177, 183-185, 188-189, 192, 195-197, 200, 203, 206-207, 219-221, 226, 231, 236, 241, 246
certus\workers\certus_spectral_workers.py                324    217     58      0    28%   105-112, 122-134, 138-140, 145-151, 162-169, 174-178, 186-197, 202-210, 219-224, 229, 245, 253, 258, 263, 273, 290, 306, 311-314, 319-320, 325-328, 337-339, 353-367, 376-378, 393-397, 407-409, 419-421, 426, 434, 446-452, 457, 465-467, 474-482, 496-501, 518-531, 546, 558-561, 579-581, 604-606, 638, 652-666, 684-691, 695-978
certus\workers\certus_strat_workers.py                   683    579    194      0    12%   46-47, 314-327, 331-359, 368-464, 474-617, 632-923, 932-934, 937-949, 998-1006, 1009-1024, 1028-1031, 1034-1068, 1080-1128, 1132-1164, 1167, 1205-1250, 1253, 1257, 1261, 1265, 1286-1504, 1515-1619, 1631-1665, 1676-1684, 1688-1694, 1699-1706
certus\workers\certus_strat_workers_dto.py               124     59     36      1    41%   11, 18-21, 24-27, 30, 33, 36, 39-43, 63-68, 71-75, 87-91, 95-97, 110-113, 123, 141-142, 146, 155, 159, 163, 171, 179, 182-191
certus\workers\certus_strat_workers_external.py           52     33     18      1    29%   21, 26-96
certus\workers\certus_strat_workers_nominal.py            32     15      4      1    50%   18, 56-81
certus\workers\certus_strat_workers_pipeline.py          112     88     28      1    18%   25, 40-248
certus\workers\certus_strat_workers_robustness.py         62     41     20      1    27%   23, 44-152
certus\workers\certus_strat_workers_search.py             27      9      8      1    54%   20, 58-69
--------------------------------------------------------------------------------------------------
TOTAL                                                  37201  30535   9694     99    15%
Coverage HTML written to dir htmlcov
Coverage XML written to file coverage.xml
============================= 41 passed in 21.21s =============================
```

## Files included for external IA
- `certus/utils/certus_progress_tracker.py`: exists=True, lines=531
- `certus/workers/certus_index_workers.py`: exists=True, lines=652
- `certus/workers/certus_re_workers.py`: exists=True, lines=246
- `certus/workers/certus_strat_workers.py`: exists=True, lines=1712
- `certus/workers/certus_spectral_workers.py`: exists=True, lines=978
- `certus/workers/certus_field_workers.py`: exists=True, lines=929
- `certus/workers/certus_design_workers.py`: exists=True, lines=494
