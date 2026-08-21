asynchronous architecture
                                  ┌───────────────────────────┐
                                  │       React Frontend      │
                                  │                           │
                                  │  UI / Chat / API Client   │
                                  └─────────────┬─────────────┘
                                                │
                                      Async HTTP / WebSocket
                                                │
                                                ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                         PYTHON ASYNC BACKEND                                  │
│                                                                               │
│  ┌──────────────────────────┐                                                │
│  │       aiohttp            │                                                │
│  │                          │                                                │
│  │ Async HTTP Server / API  │                                                │
│  └─────────────┬────────────┘                                                │
│                │                                                              │
│                ▼                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                         LangGraph                                       │  │
│  │                                                                        │  │
│  │              Async Graph Orchestration / State Machine                 │  │
│  │                                                                        │  │
│  │       Nodes ──────── Edges ──────── State ──────── Async Tasks         │  │
│  └───────┬────────────────┬─────────────────┬───────────────────┬──────────┘  │
│          │                │                 │                   │             │
│          │                │                 │                   │             │
│          ▼                ▼                 ▼                   ▼             │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐ ┌──────────────────┐ │
│  │  LangChain   │ │  MCP Layer   │ │  LangGraph      │ │   Skills Loader  │ │
│  │              │ │              │ │  Store           │ │                  │ │
│  │ Prompts      │ │ Tool calls   │ │                 │ │ *.md files       │ │
│  │ LLM calls    │ │ Resources    │ │ Async Redis      │ │                  │ │
│  │ Tools        │ │              │ │ Stack Podman     │ │                  │ │
│  └──────┬───────┘ └──────┬───────┘ └────────┬────────┘ └──────────────────┘ │
│         │                │                  │                                │
│         │                │                  │                                │
│         │                │                  ▼                                │
│         │                │        ┌──────────────────────┐                    │
│         │                │        │   Async Redis Stack  │                    │
│         │                │        │       Podman         │                    │
│         │                │        │                      │                    │
│         │                │        │   LangGraph Store    │                    │
│         │                │        └──────────────────────┘                    │
│         │                │                                                   │
│         │                │                                                   │
│         │                ▼                                                   │
│         │       ┌───────────────────────────┐                                │
│         │       │        MCP Servers        │                                │
│         │       │                           │                                │
│         │       │ ┌───────────────────────┐ │                                │
│         │       │ │ MotherDuck MCP        │ │                                │
│         │       │ │ DuckDB / MotherDuck   │ │                                │
│         │       │ └───────────────────────┘ │                                │
│         │       │                           │                                │
│         │       │ ┌───────────────────────┐ │                                │
│         │       │ │ Custom MySQL MCP      │ │                                │
│         │       │ │ MySQL 5.7             │ │                                │
│         │       │ └───────────────────────┘ │                                │
│         │       └───────────────────────────┘                                │
│         │                                                                    │
│         │                                                                    │
│         ├──────────────────────────────────────────────────────────┐         │
│         │                                                          │         │
│         ▼                                                          ▼         │
│  ┌──────────────────┐                              ┌──────────────────────┐   │
│  │ Ollama Podman #1 │                              │   py-memoize         │   │
│  │                  │                              │                      │   │
│  │ Port: XXXX       │                              │ Independent Async    │   │
│  │ LLM / Model A    │                              │ Caching              │   │
│  └──────────────────┘                              └──────────────────────┘   │
│                                                                               │
│  ┌──────────────────┐                                                        │
│  │ Ollama Podman #2 │                                                        │
│  │                  │                                                        │
│  │ Port: YYYY       │                                                        │
│  │ LLM / Model B    │                                                        │
│  └──────────────────┘                                                        │
│                                                                               │
Async execution flow
React
  │
  │ Async HTTP / WebSocket
  ▼
aiohttp
  │
  ▼
LangGraph
  │
  ├───────────────────┐
  │                   │
  │                   ├──────────────▶ LangGraph Store
  │                   │                │
  │                   │                ▼
  │                   │        Async Redis Stack
  │                   │
  │                   ├──────────────▶ Checkpointer
  │                   │                │
  │                   │                ▼
  │                   │        Async PostgreSQL Saver
  │                   │
  │                   ├──────────────▶ py-memoize
  │                   │                │
  │                   │                └── Async Cache
  │                   │
  │                   ├──────────────▶ Skills
  │                   │                │
  │                   │                └── *.md files
  │                   │
  │                   ├──────────────▶ MCP
  │                   │                │
  │                   │                ├── MotherDuck
  │                   │                │
  │                   │                └── MySQL 5.7
  │                   │
  │                   └──────────────▶ LangChain
  │                                    │
  │                                    ├──▶ Ollama #1
  │                                    ├──▶ Ollama #2
  │                                    ├──▶ Ollama #3
  │                                    ├──▶ Ollama #4
  │                                    └──▶ Ollama #5
  │
  │
  └──────────────────────────────────────────────────────▶
                          Async Response
                                │
                                ▼
                             React
Component relationship
                         ┌─────────────┐
                         │    React    │
                         └──────┬──────┘
                                │
                         Async HTTP/WS
                                │
                                ▼
                         ┌─────────────┐
                         │   aiohttp   │
                         └──────┬──────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │      LangGraph        │
                    │                       │
                    │ Async Orchestrator    │
                    └───────┬───────────────┘
                            │
        ┌───────────────────┼────────────────────────┐
        │                   │                        │
        ▼                   ▼                        ▼
 ┌────────────┐      ┌──────────────┐        ┌──────────────┐
 │ LangChain  │      │ MCP Servers  │        │ Skills       │
 └─────┬──────┘      └──────┬───────┘        │ *.md         │
       │                    │                └──────────────┘
       │              ┌─────┴─────┐
       │              │           │
       │              ▼           ▼
       │         MotherDuck    MySQL 5.7
       │
       ├─────────────┬─────────────┬─────────────┬─────────────┐
       ▼             ▼             ▼             ▼             ▼
   Ollama #1     Ollama #2     Ollama #3     Ollama #4     Ollama #5
   Podman        Podman        Podman        Podman        Podman
   :XXXX         :YYYY         :ZZZZ         :AAAA         :BBBB




                    LangGraph State Management
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
          ┌──────────────┐          ┌─────────────────┐
          │ Redis Stack  │          │ PostgreSQL      │
          │              │          │                 │
          │ LangGraph    │          │ Async Saver     │
          │ Store        │          │ Checkpointer    │
          └──────────────┘          └─────────────────┘




                     Independent Async Cache
                              │
                              ▼
                       ┌─────────────┐
                       │ py-memoize  │
                       └─────────────┘




                 Cross-cutting infrastructure
                              │
                              ▼
                       ┌─────────────┐
                       │ fastlogging │
                       └─────────────┘