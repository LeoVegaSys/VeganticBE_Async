# src/customer_report: customer traffic report tool

Built from the `CustomerTrafFilter_reporting_hist` procedure, as a tool that answers chat questions:
- An LLM fills the report's arguments from the question (Ollama structured output), and every value is checked.
- The UI's session filters limit the scope, as in `src/dip_new`.
- One deterministic SELECT runs through the existing MCP `arun_query`. There are no temporary tables, no `INTO OUTFILE` and no session settings, so it works with a read-only MySQL user and with `ONLY_FULL_GROUP_BY`.

Switch it off with `USE_CUSTOMER_REPORT = False` in `config.py`. Questions then go to the traffic graph, as before.

## Routing

`utils/categorize.route_query` checks the dip keywords first. It then checks `CR_KEYWORDS` (customer, circuit, LSI, VRF, upgrade, breach, threshold, exceed, saturate, NLD, …) as whole words. A question that names only a customer, such as "how much data did HDFC send", has none of these words, so it goes to the traffic graph. Add "customer" to the question, or add more keywords.

## Flow

```
/ask -> route_query -> run_customer_report -> call_customer_report_graph
  fill_slots        UI filters (request, else chat_sessions); MIN/MAX(Time_1) of the traffic table
                    LLM (format = SLOT_SCHEMA) -> arguments -> clean_slots()
  apply_scope       network must be MPLS; UI circle / tier = hard limits (via NODEANDIF_STATIC_TBL);
                    time: question > session window > the newest data day
  run_report        engine.build_report_sql -> render values -> MCP
  summarize_report  answer + "Note:" lines (rules used, data range, anything ignored)
```

## Tables (DEMO_MPLS)

| Table | Why |
|---|---|
| `CUSTOMER_VRF_TBL` | Customer ports: circuit, LSI, customer (VpnName / CustomerFullName), VRF, location, node, interface, alias, subscribed bandwidth (`IfSpeed`, Kb) |
| `ROUTERTRAFFIC_VLANPRT_SCALE1_TBL` | 5-minute In and Out traffic in bps. On DEMO, 6,861 of the 7,052 customer ports are here; only 13 are in `_B`. |
| `NODEANDIF_STATIC_TBL` | Only for the UI circle / tier filter (`APortID = PortID`) |

Set per data source in `CR_TABLES`. Production can point to other tables without code changes.

## Which ports count (same as the procedure)
- `RemoveTime IS NULL`, `PortID > 0`, `IfSpeed > 0`, `LSI > 100`, no `Loop*` interfaces, and provisioned before the end of the window.
- One row per `PortID`, the newest `ProvisionTime`. Two ports have two active rows on DEMO, and without this their traffic would count twice.

## Rules (`config.py`)
Utilization is traffic ÷ the subscribed bandwidth, with In and Out measured separately. A port's utilization is the higher of the two.

| Flag | Rule | Port count on DEMO, 5 Nov |
|---|---|---|
| Exceed Count | Samples above `THRESHOLD_PCT` (80; a number stated in the question replaces it) | n/a |
| BW Upgrade Needed | ≥ `UPGRADE_MIN_SHARE` (10%) of samples above 80%, **and** peak ≥ 70% | 106 |
| Saturated | ≥ `SATURATED_MIN_SAMPLES` (3) samples at ≥ 100% | n/a |
| Far Above Subscribed BW | Peak ≥ 200%. Most likely Out traffic that isn't policed, or an outdated subscription. | 246 |
| Underutilized | Average < 10% (downgrade candidates) | n/a |

Volume (MB) = SUM(bps) × 300 s ÷ 8 ÷ 10⁶. The procedure reported KB.

## Arguments (filled by the LLM, checked by `clean_slots`)

| Argument | Values |
|---|---|
| `report` | `circuits` (default), `customers`, `locations`, `totals`, `hourly` |
| `only` | `upgrade`, `breach`, `saturated`, `underutilized`, `over_subscribed`, `no_data` |
| `util` | `{stat: avg/max, above, below}`, e.g. "above 70% average utilization" |
| `threshold_pct` | 1–100 |
| filters | `customer` (short code = VpnName, part of the full name, or a circuit prefix), `lsi`, `circuit_id`, `vrf`, `location` (via `LOCATION_ALIASES`), `node`, `interface` |
| `nld` | `include` (default), `exclude`, `only` |
| `hourly_by`, `peak_hour_only` | Hourly per circuit or per customer; only the peak hour |
| `sort_by`, `order`, `limit` | utilization, avg_utilization, exceed, saturation, volume, traffic, time_above, upgrade |
| time | `window_hours`, or `start` + `end`. The default is the newest data day. |

## Questions it answers (DEMO data: 5 Nov 2026 only)

**Upgrades:**
- Which customers needed a bandwidth upgrade on 5 Nov?
- List circuits in Indore that need an upgrade.
- Does `<customer>` need a bandwidth upgrade?
- How many customer circuits need an upgrade in each location?

**Breaches:**
- Which customer links crossed 80% between 18:00 and 23:00?
- How many times did LSI `<n>` exceed 80%?
- Top 10 customers by threshold breaches.
- Give me the threshold breach summary.

**Saturation:**
- Which customer circuits hit 100% bandwidth?
- How many times did `<customer>`'s link saturate in the evening?

**Utilization:**
- Max and average utilization of `<customer>`'s circuits.
- Peak in and out traffic for circuit `<id>` between 09:00 and 18:00.
- Customer ports in Hyderabad above 70% average utilization.
- Customer links below 10% utilization.

**Volume:**
- How much data did customer `<x>` send and receive?
- Top 10 customers by total traffic volume.

**Scope:**
- Customer traffic report for VRF `<name>`.
- Report for LSI `<n>`.
- Which customers on node `<name>` are the most heavily used?
- Customer traffic summary for New Delhi.

**NLD / hourly:**
- Show the NLD circuit report.
- Hourly traffic for circuit `<id>`.
- At what hour did customer `<x>`'s traffic peak?

**Not covered:**
- The auto-email report (`CUST_VRF_LSI_CIRCUITID_AUTOEMAIL_TBL` isn't in DEMO).
- Week, month and month-on-month questions, which need more history.

## Response (extra keys)

`params_used`:
- `report`, `summary`, `rules`, `window`, `filters`
- `total_matches` (rows before the limit)
- `data_range`, `scope`, `from_question`, `tables`, `ms`

`warnings` lists everything that was ignored or overridden.

## Files

| File | What it is |
|---|---|
| `config.py` | Switch, tables per data source, rules, location aliases, routing keywords |
| `engine.py` | `build_report_sql()`: the SQL; `describe()`, `rules_text()` |
| `slots.py` | LLM schema and prompt, `clean_slots()`, `resolve_locations()`, `fallback_slots()` |
| `agent.py`, `graph.py`, `state.py` | The sub-graph |

The tool reuses these from `src/dip_new`:
- `render` (quoted values)
- `scope` helpers (UI filters, circle and tier codes, session window)
- `parse_json`
- `root_cause`

## Edits outside this folder

| File | Change |
|---|---|
| `utils/categorize.py` | `run_customer_report` route (after dip) |
| `src/startpoint/graph.py` | `call_customer_report_graph` node and edge |
