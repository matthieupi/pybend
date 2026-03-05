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
---

## ⚙️ Backend

_Python · Models · Storage · API · Auth · Actors · Agents_

- [ ] Change agent_run for run() or exec()
- [ ] TX Collection
- [ ] TX/RX
- [x] Add dict and list types (saved as JSON) based on AgentActor idea
- [ ] AgentMixin improvements
  - The docstring as the prompt?
  - Magentic
- [ ] Make TX meta a buildable dict, mirroring dump_ext and schema_ext

---

## 🖥️ Frontend

_JS · Web Components · UI · Forms · Rendering_

- [ ] Add system so that if given render method is not defined (md, sm) we 
  drop down to the next available one
- [ ] Add support for custom ntt-method components
- [ ] ...

---
