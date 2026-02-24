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
- [ ] **Layout as a schema**
  - Have a Layout model, that manages rendering, and that integrate with our 
    current structure
  - The layout can be edited via an admin panel
- [ ] **DB-based, compiled models**
  - Enables admin, no code or low code changes directly to the system
- 

## Frontend

- [ ] **Implement editable visibility only when permisisons allow it**
- [x] **Improve NTT method implementation**
  - ~~Show methods only when permissions allows it~~
  - ~~Be able to customize positioning~~
  - ~~Improve fine grain display options ( button -> form, form directly, etc)~~
  - Done: button layout (icon + count pill), inline layout, fieldset layout, `__ui__.methods` hints
- [ ] **Silent sections** Have section that are titleless
- [ ] **Add visual feedback for error handling**
- [ ] **Improve error flow through the actor system**
- [ ] **Add full URL support for href (list, items)**
- [ ] **Add search support for ntt-list**
  - We need search query for certain list, so that they load the proper data 
    instead of the whole table content
- 
- [x] **Frontend support for FK href arrays**\
    ~~`<ntt-item>` currently renders collection fields as raw URL strings.~~
    - Done: `form.js` `getListInput()` resolves hrefs via NTT ATTACH, renders as nested `<ntt-item>` cards
    - Populated wrapper normalization handles both href strings and `{$id, ...}` objects

- [ ] **Fix `@type` assertion error on save**\
    Backend PUT responses don't include `@type`/`@context` (those are NTT-injected frontend metadata).
    - Check whether the response routes through the NTT instance or bypasses directly to the Item (`ntt-item.js:~29`)
    - The NTT-mediated update flow (`NTT.UPDATE` with optimistic update + forward) was implemented but error persists
    - May be stale browser cache — try hard refresh (Ctrl+Shift+R) first
