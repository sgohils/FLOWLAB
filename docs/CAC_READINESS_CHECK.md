# FLOWLAB local release check

Checked October 25, 2026, for Shlok Gohil's GA-07 preparation. These results
describe the local working tree, not a published Vercel release or an
independent detector-accuracy benchmark.

## Verification

| Check | Result |
| --- | --- |
| Complete backend suite | 427 tests passed |
| Complete frontend suite | 209 tests passed across 28 files |
| Backend Ruff / mypy | Passed; mypy checked 43 source files |
| Frontend production build | TypeScript and Vite passed |
| Headless Chrome walkthrough | All 14 grouped checks passed; no JavaScript exceptions, console errors or HTTP errors |
| Mobile layout | Home, real analysis, both simulation examples, brief and About fit a 375 px viewport |
| Real-video builder | Completed detector, tracker, analytics and H.264 encoding successfully |
| Ordinary local upload | The 25-second sample completed processing and returned 75 retained track IDs |

The browser checks exercised decoded video frames, the shared video/map clock,
read-only sample controls, actual simulation requests, evidence downloads and
the printable brief. Two media requests were canceled during navigation; there
were no HTTP error responses. Browser reports and screenshots are generated
under ignored `.vercel/cac-qa/` on this machine.

## Rehearsal reference

| Example | Current output and interpretation |
| --- | --- |
| `/analysis/real-demo` | Real public-domain footage: 25 seconds, 75 retained track IDs, 10 selected exit-line crossings, 24 crossings/min over this short window, peak measured queue 0, estimated wait unavailable |
| `/simulation/real-demo` baseline | Model throughput 21.6/min, three modeled vehicles left at 25 seconds; this differs from measured throughput and is not hidden as a perfect fit |
| `/simulation/demo` baseline | Synthetic example: peak queue 14, completed positive-wait mean 28.37 s, throughput 9.33/min, five vehicles left at 135 seconds |
| Synthetic volume 0.75 | Model peak queue 8; compare with baseline 14. This is a hypothetical model effect, not an observed reduction on the real road |

The simulator now preserves recorded arrival timestamps, uses completion times
for its observation-window metrics, and tests sensitivity against exactly the
same baseline. Missing source measurements stay unavailable in the interface
and shared notes. Printed regions include the full video frame.

## Remaining submission steps

1. Redeploy the changed repository, then open production deep links in a fresh
   browser and verify playback, scenarios, downloads and the brief again.
2. Test hosted upload through completion and deletion if it will be shown.
   Local upload and mocked hosted tests do not verify live PostgreSQL, Blob,
   Queues or Vercel routing. Both bundled examples work without those storage
   credentials; the API service must still deploy successfully.
3. Use only publicly shareable footage on the shared deployment. The API has
   no sign-in or per-user access controls; private Blob objects do not provide
   per-user isolation through the app.
4. Complete the student's actual contribution, motivation and AI disclosure
   records. Record and submit the demonstration personally, following the
   [submission guide](CAC_SUBMISSION.md) and [recording outline](DEMO_SCRIPT.md).

No paid service was added for the bundled examples. This work did not publish
a release, upload a submission video, register an entry or submit an application.
