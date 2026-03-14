# 📋 N3TX TODO

> Ideas, improvements, and planned work. Check an item off with `[x]` when done.

---

## 🔗 Full Stack

_End-to-end features spanning backend and frontend_

- [x] Streaming via SSE
- [x] Streaming via WS
- [ ] Addr that cross boundaries
  - Currently the addr for the incoming TX will be the actor creating this 
    TX from the network data, like 'ws' or 'api'. We would need to change 
    this to have full stack addressing. A scheme could be to use IP but then 
    2 different client on the same network would share the same ref. 
- [ ] Storable Mixin search method
- [ ] Storable Mixin update to get many (checks if param is item or list)

- [x] Add debug mode:
  - Server starts in debug, auto-reloads
  - All users are created as admin role
  - ntt-method shows method tx results


- [ ] When deleting from ListRef, on a Item detail page, the actual record 
  gets deleted, instead of just removing it from the list. E.g. In 
  AgentACtor, if I remove a tool, the tool disappears. THis is because Agent 
  Tool is by definition tied to AgentActor by foreign key. This is fine for 
  some e.g. comments, that does not make sense to change their parent. (A 
  comment is contextually tied to the item it was created on). But for tools,
  we would need a many-to-many relationship. We need to implement a way to 
  elegantly execute this from within the framework.

- [ ] Method button label defaults to method name instead of "run"
- [ ] When we have a method button that needs params, when we click on it we 
  should open a small form yo enter the required fields

---

## ⚙️ Backend

_Python · Models · Storage · API · Auth · Actors · Agents_

- [x] Change agent_run for run() or exec()
- [x] Swap agentic() and run()
- [ ] TX Collection
- 
- [ ] TX/RX
- [x] Add dict and list types (saved as JSON) based on AgentActor idea
- [ ] AgentMixin improvements
  - The docstring as the prompt?
  - Magentic
- [ ] Make TX meta a buildable dict, mirroring dump_ext and schema_ext
- [ ] Pyrofunc <=> Actor natural integration
- [ ] Review Pyrofunc and see if some implementations details/features could 
  enhance our current Actor
- [ ] Change relative to absolute paths for imports (SSR stuff)
- [ ] Add param to expose route to receive actual TX instead of parsed items
---

## 🖥️ Frontend

_JS · Web Components · UI · Forms · Rendering_

- [ ] Add system so that if given render method is not defined (md, sm) we 
  drop down to the next available one
- [ ] Add support for custom ntt-method components
- [ ] Make <ntx-table> row use the same widget (edit/display) as ntx-item
  - Currently it uses it's own widget, meaning we have to do everything in 
    double, and having 2 system to render leads to various bugs. 
  - E.g In Grant watcher, User is shown as User #1,2,3 Instead of showing 
    avatar. Url is not clickable. We had some validation bugs as well.
  - Might require a deeper redesign of the primitives to make the 
    integration more seamless
- [ ] ...
- 
---
