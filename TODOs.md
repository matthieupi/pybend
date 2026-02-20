# TODOs

Task tracking for the PyBend + NTTTX project. Each task has a checkbox,
a bold title, a one-line summary, and bullet points with specifics.

Mark tasks `[x]` when done. Add new tasks at the bottom of the relevant
section.

---

## Documentation

- [x] **Update README.md for NTT unification**\
    PTT has been merged into NTT — README.md needs to reflect the new architecture.
    - Replace all PTT references with the NTT static API (`NTT.ATTACH`, `NTT.SCHEMA`, `NTT.get()`, `NTT.attach()`)
    - Update the five pillars, actor hierarchy, and 16-step dataflow diagrams
    - Update CRUD examples and code snippets (`import { PTT }` → `import { NTT }`)

- [x] **Document FK Hydration in README.md**\
    Collection fields now return href arrays instead of embedded objects.
    - Add a section covering `ListRef[T]` backend type and href URL format (`{API_URL}/{parent_table}/{parent_id}/{field_name}/{child_id}`)
    - Document how the frontend resolves each href via NTT ATTACH/DESCRIBE
    - Reference `src/pybend/core/docs/features/FK_HYDRATION.md` for backend details

## Backend
- [x] **Implement Base Auth system**
- [ ] **Add @type and @context to schema and records returns**
No tasks yet.

## Frontend

- [ ] **Add visual feedback for error handling**
- [ ] **Improve error flow through the actor system**
- [ ] **Add full URL support for href (list, items)**
- [ ] **Add search support for ntt-list**
  - We need search query for certain list, so that they load the proper data 
    instead of the whole table content
- 
- [ ] **Frontend support for FK href arrays**\
    `<ntt-item>` currently renders collection fields as raw URL strings.
    - Detect when a field value is an array of href strings in `generators/form.js` (getInput/getArrayInput)
    - Resolve each href via the NTT actor system (ATTACH → GET → DESCRIBE)
    - Render resolved hrefs as nested `<ntt-item>` cards or a sub-list within the parent card

- [ ] **Fix `@type` assertion error on save**\
    Backend PUT responses don't include `@type`/`@context` (those are NTT-injected frontend metadata).
    - Check whether the response routes through the NTT instance or bypasses directly to the Item (`ntt-item.js:~29`)
    - The NTT-mediated update flow (`NTT.UPDATE` with optimistic update + forward) was implemented but error persists
    - May be stale browser cache — try hard refresh (Ctrl+Shift+R) first
