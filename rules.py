"""
rules.py
========
The "AI insight layer". It turns the computed numbers into decisions and
plain-English advice for the founder.

It works in two parts (a "hybrid" system, as the spec asks):
  1. RULES  — fixed if/else logic decides the signal (scale / cut / hold, what's
     stuck, what to escalate). These use the configurable thresholds.
  2. WORDS  — we wrap those signals in readable sentences.

>>> This is exactly where a real AI model (LLM) would plug in: feed it the
    signals from part 1 and ask it to write part 2. The sentence-building here
    is a faithful stand-in so the product works today. <<<

Every recommendation points at a specific campaign/SKU, quotes the numbers, and
always judges on TRUE (reconciled) revenue — never platform-reported revenue.
"""

from metrics import (
    reconcile, topline, attribution, sku_performance, campaign_rows, _div,
)


# --- Small formatting helpers so the sentences read naturally ---------------
def _inr_in(n):
    """Indian-style digit grouping (lakh/crore) for rupees."""
    n = round(n)
    s = str(abs(n))
    if len(s) <= 3:
        grouped = s
    else:
        # last 3 digits, then groups of 2
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        grouped = ",".join(parts) + "," + tail
    return ("-" if n < 0 else "") + "₹" + grouped


def _pct(n):
    """Fraction -> whole-number percent, e.g. 0.87 -> '87%'."""
    return f"{round(n * 100)}%"


def _x(n):
    """ROAS-style multiplier, e.g. 4.2 -> '4.2×'."""
    return f"{n:.1f}×"


# ---------------------------------------------------------------------------
#  PER-CAMPAIGN ACTION  (Scale / Cut / Hold / Keep)
# ---------------------------------------------------------------------------
def campaign_actions(d: dict) -> list:
    T = d["thresholds"]
    result = []

    for c in campaign_rows(d):
        action, label = "keep", "Keep · monitor"
        why = f"1-day {_x(c['roas1d'])}, 7-day {_x(c['roas7d'])}, true {_x(c['trueRoas'])}."

        # RULE 1 — the flagship: weak on day 1 but strong over 7 days => HOLD.
        # Slow-converting products look like losers on 1-day; pausing them throws
        # away sales that were about to land. So we explicitly say "don't pause".
        if c["roas1d"] < T["weak1dRoas"] and c["roas7d"] >= T["strong7dRoas"]:
            action, label = "hold", "Hold — don't pause"
            why = (f"Weak on day 1 ({_x(c['roas1d'])}) but strong over 7 days "
                   f"({_x(c['roas7d'])}). It converts on a delay — give it time.")

        # RULE 2 — weak on BOTH windows with real spend => CUT.
        elif c["roas1d"] < T["weak1dRoas"] and c["roas7d"] < T["breakevenRoas"] and c["spend"] > 8000:
            action, label = "cut", "Cut / pause"
            why = (f"Weak on both windows (1d {_x(c['roas1d'])}, 7d {_x(c['roas7d'])}) "
                   f"on {_inr_in(c['spend'])} spend. True ROAS {_x(c['trueRoas'])} is below breakeven.")

        # RULE 3 — strong 7-day AND healthy true ROAS => SCALE.
        elif c["roas7d"] >= T["strong7dRoas"] and c["trueRoas"] >= T["breakevenRoas"]:
            step = round(T["scaleStep"] * 100)
            action, label = "scale", f"Scale +{step}%"
            why = (f"7-day {_x(c['roas7d'])} and true {_x(c['trueRoas'])} are both healthy. "
                   f"Room to push {_inr_in(c['spend'])} up ~{step}%.")

        result.append({**c, "action": action, "label": label, "why": why})

    return result


# ---------------------------------------------------------------------------
#  THE MORNING BRIEFING  (answers the spec's six questions)
# ---------------------------------------------------------------------------
def briefing(d: dict) -> dict:
    T = d["thresholds"]
    rec = reconcile(d)
    kpi = topline(d)
    attrib = attribution(d)
    skus = sku_performance(d)
    camps = campaign_actions(d)

    improved, worse, stuck, escalate, todo = [], [], [], [], []

    # --- Improved / got worse: MER (efficiency) ---
    if kpi["mer"]["value"] >= kpi["mer"]["prev"]:
        improved.append(f"Blended MER rose to <strong>{_x(kpi['mer']['value'])}</strong> "
                        f"(from {_x(kpi['mer']['prev'])}) — you're keeping {_inr_in(rec['trueRevenue'])} "
                        f"of true revenue against {_inr_in(kpi['adSpend']['value'])} spend.")
    else:
        worse.append(f"MER slipped to <strong>{_x(kpi['mer']['value'])}</strong> from {_x(kpi['mer']['prev'])}.")

    # --- Improved / got worse: CAC (cost to acquire a customer) ---
    cac_delta = _div(kpi["cac"]["value"] - kpi["cac"]["prev"], kpi["cac"]["prev"])
    if kpi["cac"]["value"] <= kpi["cac"]["prev"]:
        improved.append(f"Blended CAC fell to <strong>{_inr_in(kpi['cac']['value'])}</strong> "
                        f"from {_inr_in(kpi['cac']['prev'])} per new customer.")
    elif cac_delta > T["cpaSpikePct"]:
        worse.append(f"Blended CAC spiked <strong>+{_pct(cac_delta)}</strong> to "
                     f"{_inr_in(kpi['cac']['value'])} — up sharply vs yesterday.")
    else:
        worse.append(f"Blended CAC crept up to <strong>{_inr_in(kpi['cac']['value'])}</strong> "
                     f"from {_inr_in(kpi['cac']['prev'])}.")

    # --- Best and worst campaigns ---
    scalers = sorted([c for c in camps if c["action"] == "scale"], key=lambda c: -c["roas7d"])
    if scalers:
        s = scalers[0]
        improved.append(f"<strong>{s['name']}</strong> ({s['channel']}) is your strongest — "
                        f"7-day {_x(s['roas7d'])}, true {_x(s['trueRoas'])}.")

    cutters = sorted([c for c in camps if c["action"] == "cut"], key=lambda c: c["trueRoas"])
    if cutters:
        c = cutters[0]
        worse.append(f"<strong>{c['name']}</strong> ({c['channel']}) is weak on both windows — "
                     f"true ROAS only {_x(c['trueRoas'])} on {_inr_in(c['spend'])}.")

    # --- Stuck: near stock-outs, and "hold" campaigns (flat but not dead) ---
    for s in skus:
        if s["stockOut"]:
            stuck.append(f"<strong>{s['name']}</strong> ({s['sku']}) runs out in "
                         f"~<strong>{round(s['daysToStockOut'])} days</strong> at {s['dailyVelocity']}/day — "
                         f"restock or pause its ads before you pay for out-of-stock clicks.")
    holds = [c for c in camps if c["action"] == "hold"]
    for h in holds:
        stuck.append(f"<strong>{h['name']}</strong> looks flat on day 1 ({_x(h['roas1d'])}) but is not "
                     f"stuck — it's converting late (7-day {_x(h['roas7d'])}). Do not pause.")

    # --- Escalate: platform over-report, and budget bleeding ---
    for a in attrib:
        if a["overReportPct"] > T["overReportPct"]:
            escalate.append(f"<strong>{a['name']}</strong> over-reports revenue by "
                            f"<strong>{_inr_in(a['overReportAbs'])} (+{_pct(a['overReportPct'])})</strong> "
                            f"vs reconciled Shopify. Its {_x(a['roas7d'])} platform ROAS is misleading — "
                            f"true ROAS is {_x(a['trueRoas'])}. Judge budget on the true number.")
    for c in cutters:
        if c["trueRoas"] < T["breakevenRoas"] and c["spend"] > 12000:
            escalate.append(f"Budget bleeding on <strong>{c['name']}</strong>: {_inr_in(c['spend'])} "
                            f"spent at true ROAS {_x(c['trueRoas'])}, below breakeven {_x(T['breakevenRoas'])}.")

    # --- Do today: a short, ranked action list ---
    if cutters:
        todo.append(f"Pause or cut <strong>{cutters[0]['name']}</strong> — "
                    f"true ROAS {_x(cutters[0]['trueRoas'])} on {_inr_in(cutters[0]['spend'])}.")
    if scalers:
        step = round(T["scaleStep"] * 100)
        todo.append(f"Scale <strong>{scalers[0]['name']}</strong> +{step}% — "
                    f"7-day {_x(scalers[0]['roas7d'])} has headroom.")
    soonest = sorted([s for s in skus if s["stockOut"]], key=lambda s: s["daysToStockOut"])
    if soonest:
        todo.append(f"Restock <strong>{soonest[0]['name']}</strong> — "
                    f"~{round(soonest[0]['daysToStockOut'])} days of cover left.")
    worst_over = sorted(attrib, key=lambda a: -a["overReportPct"])[0]
    if worst_over["overReportPct"] > T["overReportPct"]:
        todo.append(f"Re-check <strong>{worst_over['name']}</strong> budgets against true ROAS "
                    f"{_x(worst_over['trueRoas'])}, not its reported {_x(worst_over['roas7d'])}.")
    if holds:
        todo.append(f"Leave <strong>{holds[0]['name']}</strong> running — it converts late; "
                    f"pausing now loses booked 7-day sales.")

    n = len(escalate)
    changed = (f"Yesterday you spent <strong>{_inr_in(kpi['adSpend']['value'])}</strong> and collected "
               f"<strong>{_inr_in(rec['trueRevenue'])}</strong> in true revenue across "
               f"{kpi['orders']['value']} orders (MER {_x(kpi['mer']['value'])}). "
               f"{n} item{'' if n == 1 else 's'} need{'s' if n == 1 else ''} your attention.")

    return {"changed": changed, "improved": improved, "worse": worse,
            "stuck": stuck, "escalate": escalate, "todo": todo}
