# CERTUS migration audit report

Generated: 2026-07-09T08:48:22.844946
Repo: `C:\Users\Lemarchand\Mon Drive\couches minces 2026\CERTUS\0807`
Verdict hint: **LIKELY_SUCCESS**

## Legacy pattern audit
- `progress\.emit\(`: 0 match(es)
- `signals\.progress\.emit\(`: 0 match(es)
- `self\.progress\.emit\(`: 0 match(es)

## Positive migration signals
- `progress_snapshot`: 211 match(es)
- `build_progress_snapshot\(`: 96 match(es)
- `StepState`: 167 match(es)
- `format_eta\(`: 8 match(es)

## Tests
- `tests/ui/test_u8_u11_ux_widgets.py`: return code `0`
```text
certus\workers\certus_design_workers_needle_strat.py        128    100     40      0    17%   23, 28, 33, 38, 43, 49-85, 91-111, 117-158
certus\workers\certus_design_workers_strat.py               313    266    110      0    11%   24, 29, 34, 39, 44, 72-105, 138-141, 147-148, 154-156, 162-165, 171-256, 262-285, 291-362, 368, 374-405, 411-418, 424-426
certus\workers\certus_field_workers.py                      513    434    188      8    13%   19-20, 27, 30, 36, 39, 44-46, 69-138, 161-177, 180-181, 201, 206, 224, 231->234, 250-335, 347-511, 523-944
certus\workers\certus_field_workers_dto.py                   99     23     14      4    71%   13-16, 19-22, 25, 28, 59, 61-64, 71, 77-79, 84-87, 97->exit
certus\workers\certus_index_workers.py                      539    365    118     13    28%   91->93, 95, 126-172, 199, 209, 245-246, 282-308, 311->341, 314->341, 342, 362-368, 371, 374, 378, 381-383, 395-397, 414-416, 453-455, 487-489, 492-590, 605-607, 626-639, 652-654, 659, 670, 672, 674->677, 678->exit, 717, 759, 762-774, 778-780, 784-786, 790-824, 838-846, 862-863, 866-868, 873, 877, 881-889, 894-896, 899-901, 906-908, 911-1150, 1153-1155, 1160-1162, 1181-1186, 1189, 1193-1229
certus\workers\certus_re_worker_utils.py                    200    165     44      0    14%   39-41, 58-72, 87-143, 160-179, 199-207, 221-238, 261, 268, 273, 278-281, 293-301, 307-316, 336-374, 398-414, 432-438, 456-482, 488-505, 522-541, 550-553, 572-606, 623, 635, 647, 671-674, 687, 701, 724-732
certus\workers\certus_re_workers.py                         177     80      2      0    54%   52-56, 60, 63-64, 67-68, 71-72, 75-76, 79-80, 83-84, 87-88, 91-92, 95-96, 99-100, 103-104, 107-108, 111-112, 115-116, 119-120, 124, 128-129, 148-157, 160-161, 164-165, 168-169, 172-173, 176-177, 183-185, 188-189, 192, 195-197, 200, 203, 206-207, 219-221, 226, 231, 236, 241, 246
certus\workers\certus_spectral_workers.py                   339    232     58      0    27%   105-112, 122-134, 138-140, 145-151, 162-169, 174-178, 186-197, 202-210, 219-224, 229, 245, 253, 258, 263, 273, 290, 306, 311-314, 319-320, 325-328, 337-339, 353-367, 376-378, 393-397, 407-409, 419-421, 426, 434, 446-452, 457, 465-467, 474-482, 496-501, 518-531, 546, 558-561, 579-581, 604-606, 638, 652-666, 684-691, 695-963
certus\workers\certus_strat_workers.py                      654    577    194      0     9%   146-159, 164-192, 202-298, 309-452, 469-766, 776-778, 781-794, 843-851, 854-869, 873-876, 879-913, 925-973, 977-1014, 1017, 1054-1099, 1102, 1105, 1108, 1111, 1131-1356, 1368-1474, 1487-1522, 1535-1543, 1547-1553, 1559-1566
certus\workers\certus_strat_workers_dto.py                  124     59     36      1    41%   11, 18-21, 24-27, 30, 33, 36, 39-43, 63-68, 71-75, 87-91, 95-97, 110-113, 123, 141-142, 146, 155, 159, 163, 171, 179, 182-191
certus\workers\certus_strat_workers_external.py              53     33     18      1    30%   21, 27-97
certus\workers\certus_strat_workers_nominal.py               32     15      4      1    50%   18, 56-81
certus\workers\certus_strat_workers_pipeline.py             113     88     28      1    18%   26, 41-249
certus\workers\certus_strat_workers_robustness.py            62     41     20      1    27%   23, 44-152
certus\workers\certus_strat_workers_search.py                27      9      8      1    54%   20, 58-69
-----------------------------------------------------------------------------------------------------
TOTAL                                                     24457  19112   6644     94    18%
Coverage HTML written to dir htmlcov
Coverage XML written to file coverage.xml
============================= 41 passed in 24.04s =============================
```

## Files included for external IA
- `certus/utils/certus_progress_tracker.py`: exists=True, lines=573
- `certus/workers/certus_index_workers.py`: exists=True, lines=1229
- `certus/workers/certus_re_workers.py`: exists=True, lines=246
- `certus/workers/certus_strat_workers.py`: exists=True, lines=1571
- `certus/workers/certus_spectral_workers.py`: exists=True, lines=963
- `certus/workers/certus_field_workers.py`: exists=True, lines=954
- `certus/workers/certus_design_workers.py`: exists=True, lines=498
