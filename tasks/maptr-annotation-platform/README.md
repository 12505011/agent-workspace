# MapTR annotation platform

Verified 2026-10-12.

- Project: `/data/baize/baize-welldriver/code/maptr_annotation_validation_tool`, code branch `master`; no source changes made during initial audit.
- Context branch: `task/maptr-annotation-platform`, isolated worktree `/home/westwell/agent-workspace-maptr-annotation-platform`. Original agent-workspace checkout has unrelated uncommitted work and was left untouched.
- Reference: `/home/westwell/Downloads/cnwxijk.json`, version 1.3, 3 lanes and 3 matching arcline_path_3/connectivity entries. All incoming/outgoing arrays are empty; reference does not demonstrate actual connected lanes.
- Existing Web flow: polygon then directed center path for each lane/lane_connector; center required one-to-one. Automatic connectivity uses end-to-start distance (default 0.30 m) and heading (default 60 degrees), with manual reciprocal relation editing. Imported connectivity is retained until applying automatic topology.
- `src/annotation_document.cpp`: exports node/line/polygon, arcline_path_3 segment arrays and connectivity; backend rejects missing/duplicate centers and dangling/self/duplicate/asymmetric connectivity.
- Center paths are manually drawn then fitted to arcs/lines, not extracted automatically from lane polygons. Lane divider and edge relation attributes default empty for newly drawn lanes; these are distinct from lane-to-lane connectivity.
- Fresh build succeeded: `cmake -S . -B /tmp/maptr-annotation-audit-build`; `cmake --build /tmp/maptr-annotation-audit-build --target maptr_annotation_document_check -j4`.
- Reference roundtrip: 45 editor objects before/after; arcline_path_3/connectivity preserved exactly. Whole document differs only in stop_line default attributes added by existing exporter.
- Temporary synthetic checks passed: reciprocal nonempty relations survive roundtrip; asymmetric relations and missing centers rejected. Node VM execution of actual frontend functions passed sequential connection, ambiguous nearby starts, and exactly snapped split cases.
- Audit artifacts: `/tmp/maptr-annotation-audit/`. Browser UI and running deployment were not tested.

## Field-level follow-up audit

- Reference nonempty layers: road_segment 12, lane 3, road_divider 16, lane_divider 8, ped_crossing 1, stop_line 2; base geometry node 1300, line 26, polygon 16.
- Reference stop_line uses line_token. Web CATEGORIES declares stop_line polygon:true, and finishDraft follows category geometry, so new stop lines are polygons; imported line stop lines are supported by backend. New stop lines also lack a road_segment_token default, although imported values survive.
- No semantic attribute editing in EditableAnnotation/sceneDescription: lane_type defaults CAR, road_segment is_intersection defaults false; edge/divider and road/drivable area association fields are preserved on import or default empty/null, without editor logic.
- Polygon holes are read for map rendering and preserved in exporter, but editable objects carry exterior points only and have no hole authoring tool.
- Center validation checks ownership, counts and nondegenerate segments; does not establish containment in owning lane or validate the entire fitted curve against its polygon.
- Reference itself has empty edge/divider/road ownership associations and holes, false intersection flags, only CAR lane types, all-straight center paths, no lane_connector. It cannot establish completeness for those behaviors.

## Implementation 2026-10-12

- Source branch: `feat/annotation-categories-and-properties` in project checkout. Changes are uncommitted; no push performed.
- Added file-scoped category definitions in top-level `annotation_categories` (`id`, `label`, `color`, `polygon`). Custom records use their category ID as a top-level layer and ordinary geometry token references. Standard IDs retain their center/topology behavior. Used categories cannot be deleted or change shape in UI.
- Web settings allow category creation/name/color changes, custom polygon/line drawing, and label-based object search. New stop lines default to lines; imported polygon stop lines remain supported.
- Editable semantic payload includes lane_type, is_intersection, road/drivable-area ownership and edge-line associations, plus additional JSON attributes. Export removes explicitly deleted custom attributes. Segment arrays have type checks/editor access, not automatic semantic segment construction.
- Polygon holes support canvas drawing and coordinate-ring editing/deletion; included in rendering, import/export and derived boundary preview. Desktop overlay also renders custom layers and holes.
- GEOS validates new/edited polygons/holes and checks sampled fitted center paths for containment. Unchanged imported geometry is exempt to preserve legacy files (reference has a center outside its owning lane). Center paths remain manually authored.
- Save now validates a candidate document and updates live state only after a successful write; unknown classes/invalid geometry are rejected rather than silently dropped.
- Built all local targets successfully with `cmake --build build -j4`. `node --check web/app.js` and `git diff --check` pass.
- Five end-to-end tests in `tests/test_annotation_export.py` pass using the built local web server. Cover custom polygon/line layers, holes, semantic deletion, category roundtrip, required references, stop lines, lane/connector connectivity, containment rejection, and legacy preservation.
- Reference roundtrip succeeds with 45 editor objects before/after. Original reference file was not changed. Temporary testing exports are under `/tmp/maptr-annotation-audit` and `/tmp/maptr-browser-review`.
- Headless Chrome UI checks passed category creation/renaming, semantic editing, canvas custom polygon/line/hole drawing, save/reopen and absence of page errors. Browser runtime tool was not available; after reading browser skill, used isolated Playwright environment `/tmp/maptr-ui-test-env` with installed Chrome. Screenshots under `/tmp/maptr-browser-review`.
- Usage and data compatibility notes added to project README section 类别配置与语义属性. Custom classes do not automatically alter downstream MapTR class mappings.

## Editing workflow optimization 2026-10-12

- Implemented on the same source branch; changes remain uncommitted and unpushed.
- Web workspace now has Draw / Properties / Check tabs, a category management dialog with automatic unique IDs, persistent undo/redo controls, and explicit unsaved/saved/exported status.
- Property input updates the editor immediately. Per-object raw input buffers preserve incomplete JSON across selection changes and draft reopening. Advanced JSON is collapsed by default and opens when invalid input needs attention.
- Ctrl+S saves an append-only `.draft.json` using `maptr-editor-draft-v1`, embedding the source map plus editor state, unfinished sketches, pending center/hole ownership, topology settings and raw form buffers. Ctrl+Shift+S validates and exports ordinary MapTR JSON. Draft filename collision handling retains `.draft.json`.
- Dirty UI scene refresh/project switching saves a draft first; failed saves retain the current scene. Browser close/reload warns on unsaved work. Drafts must be exported before camera projection; the backend prevents projection of the editor wrapper and the frontend invalidates stale projection state after saving/exporting.
- Full editor snapshot undo/redo covers drawing/completion/cancellation, vertex movement, deleting an object with its center, attributes/holes, categories, topology and center reversal. History is session-local, bounded to 40 operations with an approximate 32 MiB snapshot budget.
- Canvas relation picking supports semantic ownership/edge refs and reciprocal predecessor/successor relations. It frames the owner and up to eight nearby eligible targets. Relation colors and directed center arrows help inspect links; centers can be reversed.
- `/api/validate` checks a candidate without writing or changing live objects. The Check tab refreshes after edits and offers object navigation for attributable errors. Strict export validation remains separate from draft persistence.
- All CMake targets build. Seven isolated HTTP regression tests pass. `tests/browser_workflow_check.py` passes real headless Chrome workflows for automatic property persistence, invalid input recovery/error navigation, undo/redo, canvas edge/topology picks, categories, dirty refresh protection, hole edits, unfinished lane/center draft reopening, validated export and center direction. No page errors.
- `node --check` for both JS files and `git diff --check` pass. Reference roundtrip still contains 45 editor objects; original `arcline_path_3` and `connectivity` preserved exactly. Original Downloads reference unchanged.
- Preview runs on `http://127.0.0.1:18880`, using final built backend and assets under `/tmp/maptr-workflow-review/web` with a temporary reference copy. Header save/export controls checked at 1280 and 1600 px. Screenshots under `/tmp/maptr-workflow-review`.

## Direct relation selection follow-up 2026-10-12

- User clarified that global edge candidate lists include distant lines and prefers direct mouse selection. Removed semantic relation dropdowns; start/end edges and ownership refs now use canvas selection as the primary action.
- Mouse hover previews eligible objects in cyan without changing selection or attributes. Click confirms; Esc cancels. Starting edge selection keeps the current camera instead of framing all candidates. Topology framing includes only owners within 10 m of the relevant endpoint.
- Associated-object cards show a miniature lane/target diagram, class, distance to the directed center endpoint and coordinates, plus locate, reselect and unlink actions. Hidden form values retain existing export semantics.
- Added `web/relation_picker.js`. Preview state is transient and excluded from drafts/history. Unlink is undoable; restored raw property buffers refresh associated-object cards.
- Headless browser workflow checks pass, including absence of edge dropdowns, unchanged camera when entering edge picking, hover without assignment, click assignment, thumbnail, locate/Esc, unlink and undo. Existing workflow regression still passes without page errors. JS syntax and diff whitespace checks pass. Preview assets refreshed on port 18880; original reference unchanged.

## Local directory browsing branch 2026-10-12

- User requested a local development branch differing from master only in accessible directory defaults. Created `local-dev` from master `b487cf2` in isolated worktree `/data/baize/baize-welldriver/code/maptr_annotation_validation_tool-local-dev`. Original feature branch and uncommitted UI/annotation work retained untouched.
- Commit `5c9858e` changes only `src/web_main.cpp`: unrestricted local filesystem browsing when `--browse-root` is absent; explicit browse roots retain restriction, and `--allow-any-path` can explicitly override. CLI help updated accordingly. Docker entrypoint already passes `--browse-root`, so its configured restriction still applies. Master remains at `b487cf2`; no push.
- Built the isolated branch web server at `/tmp/maptr-local-dev-build/maptr_annotation_web_server`. Temporary real-server checks first failed against old defaults, then passed local defaults, explicit root restriction, and explicit unrestricted override. Synthetic JSON file and directory both exercised.
- Current enhanced preview on port 18880 retains the original feature build/assets and now starts with `--allow-any-path`; loaded reference and empty PCD configuration retained. This runtime flag fixes local picker access without changing the feature checkout's source defaults. Original reference/data unchanged.
- Headless UI verification on the updated preview selected `/home/westwell/Downloads` as a PCD directory and `cnwxijk.json` as the map file successfully; both listing requests returned 200 and no page errors occurred. Selection alone was exercised, without loading data or saving files.

## Local feature synchronization 2026-10-12

- At user's request, committed all prior verified annotation/UI fixes as `7008207` on `feat/annotation-categories-and-properties`, then cherry-picked to `local-dev` as `155df1b`. Both worktrees are clean; local-dev differs from the feature branch only in `src/web_main.cpp` directory browsing defaults. Master remains unchanged; no push.
- Built all targets in local-dev's own `build/`. Seven backend tests, headless UI workflow regression, JS syntax/whitespace checks and local/explicit-root/override directory checks pass with that binary.
- Verified automatic topology calculations against real frontend functions: end-to-start XY distance (default 0.30 m), smallest difference between last/first nondegenerate segment headings (default 60 degrees). 0.2 m / 20 degrees connects; 0.4 m or 90 degrees rejects. Exactly snapped endpoints within 1e-4 m bypass the heading limit to permit intentional turns/branches; multiple nonsnapped candidates are ambiguous.
- User-started PID 4048206 listens on 8787 from the local-dev worktree and still runs the old binary image. Left running to avoid interrupting annotation work. User must save work, stop it and relaunch `./build/maptr_annotation_web_server --port 8787`, then refresh browser, to activate new backend. Earlier temporary preview services are no longer running.

## Wide-view snapping and downstream topology 2026-10-12

- Local-dev commit `61c58b9` and feature-branch cherry-pick `a14421f` remove world-distance caps that made mouse hit targets only a few pixels wide at wide zoom. Vertex drawing snap is 18 screen pixels, edge snap 12, line selection 14, and selected-vertex drag handle 22. Snap preview marker is 18 pixels. Master remains unchanged.
- Isolated Playwright test `tests/browser_snapping_check.py` passes line selection and vertex snapping from 12 px away, absence of snap at 24 px, actual vertex drag from 12 px away, and undo. Existing `tests/browser_workflow_check.py`, seven backend tests, JS syntax, Python compilation and diff whitespace checks pass. Both worktrees are clean after commits.
- In `/data/baize/baize-welldriver/code/maptr`, `tools/3dod_maptr/westwell_joint_converter.py` reads `get_incoming_lane_ids` / `get_outgoing_lane_ids` for lane/lane_connector centerlines and uses those tokens in `union_centerline` to connect directed centerline graph edges before writing vector annotation into PKL. The offline dataset consumes coordinates/classes from the PKL, not connectivity fields directly. Road segments supply boundary geometry there, not predecessor/successor connectivity. Reference `cnwxijk.json` has three connectivity entries, all with empty incoming/outgoing arrays.
