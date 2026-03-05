# 📋 N3TX TODO

> Ideas, improvements, and planned work. Check an item off with `[x]` when done.

---

## 🔗 Full Stack

_End-to-end features spanning backend and frontend_

- [ ] Streaming via SSE
- [ ] Streaming via WS
- [ ] Addr that cross boundaries
  - Currently the addr for the incoming TX will be the actor creating this 
    TX from the network data, like 'ws' or 'api'. We would need to change 
    this to have full stack addressing. A scheme could be to use IP but then 
    2 different client on the same network would share the same ref. 
- [ ] Add debug mode:
  - Server starts in debug, auto-reloads
  - All users are created as admin role
  - ntt-method shows method tx results
- 

---

## ⚙️ Backend

_Python · Models · Storage · API · Auth · Actors · Agents_

- [ ] Change agent_run for run() or exec()
- [ ] TX Collection
- [ ] TX/RX
- [ ] Add dict and list types (saved as JSON) based on AgentActor idea
- [ ] AgentMixin improvements
  - The docstring as the prompt?

---

## 🖥️ Frontend

_JS · Web Components · UI · Forms · Rendering_

- [ ] Add system so that if given render method is not defined (md, sm) we 
  drop down to the next available one
- [ ] Add support for custom ntt-method components
- [ ] ...

---
