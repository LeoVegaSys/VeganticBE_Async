# src/dip_new: LLM-filled dip tool with the UI's global filters

This replaces the regex `dip_detect` of `src/dip` (left untouched) with the Dip_Tool engine:
- An LLM fills the tool's arguments from the question.
- The UI's session filters limit the scope.
- The SQL is deterministic and runs through the existing MCP database manager.

Switch between the two with `USE_DIP_NEW` in `src/dip_new/config.py`.

## Flow

```
/ask -> route_query (dip keywords) -> run_dip -> call_dip_graph
   USE_DIP_NEW = True:
     fill_slots     filters from the request, else ai_db.chat_sessions by session id
                    network -> source; MAX(Time_1) of the anchor table = "now"
                    LLM (Ollama /api/generate, format = SLOT_SCHEMA) -> arguments, checked
     apply_scope    UI circle / tier = hard limits; question time wins over session time
     calculate_dip  dip_engine.build_dip_sql -> render values -> MCP arun_query
     summarize_dip  summary + "Note:" lines for anything ignored or overridden
```

## Request

```json
{
  "question": "show traffic dip of more than 5 %",
  "context": {
    "session_id": "12", "user_id": "1", "data_source": "demo_mpls",
    "filters": {
      "networks": ["MPLS"], "levels": ["T1", "T2"], "circle": ["Maharashtra"],
      "services": ["Mobility"],
      "dateFrom": "2026-09-29", "dateTo": "2026-09-29",
      "timeStart": "09:00", "timeEnd": "10:00"
    }
  }
}
```

- `filters` may also be at the top level.
- The keys match `NewSessionRequest`, the `/sessions` body.
- When `filters` is missing and `session_id` is a number, the same columns are read from `chat_sessions`.
- Values may be lists, JSON text or comma-separated text. A value of `All` means no filter.

## What each UI filter does

| UI filter | Applied as | Notes |
|---|---|---|
| Network | `MPLS` → source `mpls` (the `mpls_traffic_raw` view) | Other networks: "not available yet" |
| Hierarchical level | `Tier IN ('T1','T2')` | Accepts `T1`, `Tier 1` or `1` |
| Circle | `Circle IN ('MH')` | Names are mapped to codes by `CIRCLE_CODES` in `config.py`; codes pass through |
| Services | not applied (on hold) | The reply says it was not applied |
| Date and time | `start` = dateFrom + timeStart, `end` = dateTo + timeEnd | A time only: on the newest data's day. Dates only: whole days. ISO dates with `Z` are read in IST. |

When the question and the session disagree:
- **Circle and tier:** the question can narrow them ("MH" when the session has MH and AP), but not widen them. If it asks for a circle outside the session, the session's circles are used and the reply says so.
- **Time:** a time in the question ("last 2 hours") replaces the session window, and the reply says so.

## Response (extra keys)

| Key | Contents |
|---|---|
| `results`, `columns`, `row_count`, `sql_query` | As before |
| `params_used` | Source, table, threshold, window, level, filters, one-line `summary`, `method`, `latest_data_time`, `scope` (the session filters used) and `from_question` (what the LLM read) |
| `warnings` | Every ignored or overridden filter |
| `formatted_data_for_visualization` | Traffic points around each dip, when the user asks for a chart |

## Files

| File | What it is |
|---|---|
| `config.py` | Switch, models, views per data source, circle map, known link types |
| `slots.py` | LLM schema and prompt, and `clean_slots()`, which checks every value the LLM returns |
| `scope.py` | Reads the UI filters, maps circle and tier codes, merges with the slots |
| `runner.py` | `DipRunner.find()`: the engine run through MCP; `series()` for charts |
| `tool/dip_engine.py` | Copied unchanged from `Dip_Tool` |
| `tool/render.py` | Turns `%s` placeholders into quoted values (MCP takes one SQL string) |
| `agent.py`, `graph.py`, `state.py` | The sub-graph |
| `sql/demo_mpls_dip_views.sql` | `CREATE VIEW mpls_traffic_raw` and `mpls_b2b_traffic_raw` for DEMO_MPLS |

## Edits outside this folder (all additive)

| File | Change |
|---|---|
| `utils/context.py` | `QueryRequest.filters` |
| `src/startpoint/state.py` | `filters`, `params_used`, `warnings` |
| `src/startpoint/graph.py` | Passes `filters`; `call_dip_graph` uses dip_new when `USE_DIP_NEW` is set |
| `managers/models/llm.py` | `call(..., format=None, options=None)`: Ollama structured output, plus a real `temperature: 0` |
| `db/demo_mpls/config.py` | `TRAFFIC_TABLE_NAME`, which `db/demo_mpls/src.py` imports. Without it the app fails at import. |

## Setup

1. Run `sql/demo_mpls_dip_views.sql` on DEMO_MPLS, then checks (a) and (b) in it.
2. Ollama 0.5 or later, for `format` with a JSON schema.
3. Check the circle codes: `SELECT DISTINCT ACircle FROM NODEANDIF_STATIC_TBL;`, then fix `CIRCLE_CODES` if needed (for example, is `MUM` its own circle?).
