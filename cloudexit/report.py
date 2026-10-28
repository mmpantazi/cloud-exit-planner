import json
from datetime import date

from . import __version__
from .checklist import PHASES, TEXT, phase_steps
from .estimate import provider_name
from .pricing import AS_OF, DATA_ACT_FULL_DATE

LOCKIN_WORD = {
    "en": {1: "portable", 2: "moderate", 3: "proprietary"},
    "ro": {1: "portabil", 2: "moderat", 3: "proprietar"},
}
LEVEL_WORD = {"en": {"low": "low", "medium": "medium", "high": "high"}, "ro": {"low": "mic", "medium": "mediu", "high": "mare"}}
LABELS = {
    "en": {
        "scanned": "Scanned {n} files in `{root}`. Providers detected: {providers}.",
        "none": "No vendor-specific services were found. Check that you pointed the tool at the infrastructure folder.",
        "services": "Services in use",
        "cols": "| Service | Lock-in | Resources | Found in |",
        "lockin": "Lock-in score: **{score}/100 ({label})**. 0 means everything is drop-in elsewhere, 100 means everything is proprietary.",
        "egress": "Data leaving the provider",
        "unsized": "No data sizes were given, so no total is computed. Pass `--size storage=500 --size database=80` (GB) to size it. Cost of moving 1 TB out at list price:",
        "egcols": "| Provider | Data (GB) | List price | Vendor leave-waiver | After {date} |",
        "egwaiver": "Waiver conditions: ",
        "egnote": "List price is what an ordinary download costs. The waiver column assumes you meet the provider's leave conditions. From {date} the Data Act bans switching charges for the one-off move, but traffic during parallel use of two providers may still be charged at cost.",
        "total": "Cost picture",
        "tcols": "| Item | Low | High |",
        "t_egress": "Egress (from waiver/Data Act to list price)",
        "t_eng": "Engineering effort ({lo}-{hi} days at {rate}/day)",
        "t_par": "Parallel running of the old environment",
        "t_commit": "Remaining commitment / early-termination fee",
        "t_sum": "Total",
        "fxnote": "Amounts in EUR; egress converted at 1 USD = {fx} EUR. Engineering days are a rough model: {model}.",
        "timing": "Timing",
        "tl_notice": "Send the switching request: {d}",
        "tl_start": "Provider must start the switch by: {d}",
        "tl_trans": "Transition period ends (30 days): {d}",
        "tl_retr": "Retrieval period ends (at least 30 days later): {d}",
        "tl_before": "Your switch would start before {full}, when switching charges are still allowed at the provider's direct cost. If waiting is acceptable, send the request on or after **{earliest}** so the process starts on or after {full}.",
        "tl_after": "The switch would start on or after {full}, when switching charges for the one-off move are banned.",
        "risks": "Things that make exit harder",
        "alts": "Possible EU-friendly targets",
        "disc": "Prices: indicative list prices as of {asof}; confirm on the provider's page. Article numbers come from secondary commentary on Regulation (EU) 2023/2854. This is planning help, not legal advice.",
    },
    "ro": {
        "scanned": "Au fost scanate {n} fișiere din `{root}`. Furnizori detectați: {providers}.",
        "none": "Nu s-au găsit servicii specifice unui furnizor. Verificați dacă ați indicat folderul de infrastructură.",
        "services": "Servicii folosite",
        "cols": "| Serviciu | Dependență | Resurse | Găsit în |",
        "lockin": "Scor de dependență (lock-in): **{score}/100 ({label})**. 0 = totul se mută direct, 100 = totul este proprietar.",
        "egress": "Date care ies de la furnizor",
        "unsized": "Nu s-au dat dimensiuni de date, deci nu se calculează un total. Folosiți `--size storage=500 --size database=80` (GB). Costul mutării a 1 TB la preț de listă:",
        "egcols": "| Furnizor | Date (GB) | Preț de listă | Scutire la plecare | După {date} |",
        "egwaiver": "Condiții de scutire: ",
        "egnote": "Prețul de listă este costul unei descărcări obișnuite. Coloana de scutire presupune că îndepliniți condițiile furnizorului. Din {date} Actul privind datele interzice taxele pentru mutarea unică, dar traficul din timpul utilizării în paralel poate fi taxat la cost.",
        "total": "Imaginea costurilor",
        "tcols": "| Element | Minim | Maxim |",
        "t_egress": "Trafic de ieșire (de la scutire/Actul privind datele până la prețul de listă)",
        "t_eng": "Efort de inginerie ({lo}-{hi} zile la {rate}/zi)",
        "t_par": "Rularea în paralel a vechiului mediu",
        "t_commit": "Angajament rămas / taxă de reziliere",
        "t_sum": "Total",
        "fxnote": "Sume în EUR; traficul este convertit la 1 USD = {fx} EUR. Zilele de inginerie sunt un model aproximativ: {model}.",
        "timing": "Calendar",
        "tl_notice": "Trimiteți cererea de schimbare: {d}",
        "tl_start": "Furnizorul trebuie să înceapă schimbarea până la: {d}",
        "tl_trans": "Se termină perioada de tranziție (30 de zile): {d}",
        "tl_retr": "Se termină perioada de recuperare (cel puțin 30 de zile mai târziu): {d}",
        "tl_before": "Schimbarea ar începe înainte de {full}, când taxele de schimbare sunt încă permise la costul direct al furnizorului. Dacă puteți aștepta, trimiteți cererea în sau după **{earliest}**, ca procesul să înceapă în sau după {full}.",
        "tl_after": "Schimbarea ar începe în sau după {full}, când taxele pentru mutarea unică sunt interzise.",
        "risks": "Lucruri care îngreunează ieșirea",
        "alts": "Destinații posibile în UE",
        "disc": "Prețuri: prețuri de listă orientative la {asof}; confirmați pe pagina furnizorului. Numerele articolelor provin din comentarii secundare la Regulamentul (UE) 2023/2854. Este ajutor de planificare, nu consultanță juridică.",
    },
}
EFFORT_MODEL = "0.5 / 2 / 5 days per portable / moderate / proprietary service, +25% for each further resource, range x0.6 to x1.6"


def money(x):
    return f"€{x:,.0f}"


def _where(f):
    files = sorted({e.file for e in f.evidence})
    shown = ", ".join(f"`{x}`" for x in files[:3])
    return shown + (f" +{len(files) - 3}" if len(files) > 3 else "")


def totals(plan, fx):
    eg_hi = sum(e.list_cost for e in plan.egress) * fx
    lo = plan.effort_cost[0] + plan.parallel_cost + plan.commitment
    hi = eg_hi + plan.effort_cost[1] + plan.parallel_cost + plan.commitment
    return {"egress": (0.0, eg_hi), "effort": plan.effort_cost, "parallel": plan.parallel_cost,
            "commitment": plan.commitment, "total": (lo, hi)}


def to_markdown(result, plan, lang="en", fx=0.92):
    L, T = LABELS[lang], TEXT[lang]
    full = DATA_ACT_FULL_DATE
    out = [f"# {T['title_report']}", ""]
    provs = ", ".join(provider_name(p) for p in sorted(result.providers)) or "-"
    out += [L["scanned"].format(n=result.files_scanned, root=result.root, providers=provs), ""]
    if not plan.services:
        out += [L["none"], ""]
    else:
        out += [f"## {L['services']}", "", L["cols"], "|---|---|---|---|"]
        for f in plan.services:
            out.append(f"| {f.service.name} | {LOCKIN_WORD[lang][f.service.lockin]} | {max(f.resources, len(f.evidence) if f.resources == 0 else f.resources)} | {_where(f)} |")
        out += ["", L["lockin"].format(score=plan.lockin_score, label=LEVEL_WORD[lang][plan.lockin_label]), ""]

        out += [f"## {L['egress']}", ""]
        if plan.sized:
            out += [L["egcols"].format(date=full), "|---|---|---|---|---|"]
            for e in plan.egress:
                out.append(f"| {provider_name(e.provider)} | {e.gb:,.0f} | {money(e.list_cost * fx)} | €0 | €0 |")
            out += [""] + [f"- {L['egwaiver']}{e.waiver}" for e in plan.egress] + ["", L["egnote"].format(date=full), ""]
            t = totals(plan, fx)
            out += [f"## {L['total']}", "", L["tcols"], "|---|---|---|",
                    f"| {L['t_egress']} | {money(t['egress'][0])} | {money(t['egress'][1])} |",
                    f"| {L['t_eng'].format(lo=plan.effort_days[0], hi=plan.effort_days[1], rate=money(plan.day_rate))} | {money(plan.effort_cost[0])} | {money(plan.effort_cost[1])} |"]
            if plan.parallel_cost:
                out.append(f"| {L['t_par']} | {money(plan.parallel_cost)} | {money(plan.parallel_cost)} |")
            if plan.commitment:
                out.append(f"| {L['t_commit']} | {money(plan.commitment)} | {money(plan.commitment)} |")
            out += [f"| **{L['t_sum']}** | **{money(t['total'][0])}** | **{money(t['total'][1])}** |", "",
                    L["fxnote"].format(fx=fx, model=EFFORT_MODEL), ""]
        else:
            out += [L["unsized"], ""]
            out += [f"- {provider_name(e.provider)}: {money(e.per_tb_list * fx)}" for e in plan.egress]
            out += ["", f"{L['egwaiver']}"] + [f"- {e.waiver}" for e in plan.egress] + [""]
            out += [L["fxnote"].format(fx=fx, model=EFFORT_MODEL), "",
                    f"Engineering effort: {plan.effort_days[0]}-{plan.effort_days[1]} days ({money(plan.effort_cost[0])}-{money(plan.effort_cost[1])} at {money(plan.day_rate)}/day).", ""]

    if plan.timeline:
        tl = plan.timeline
        out += [f"## {L['timing']}", "", f"- {L['tl_notice'].format(d=tl.notice)}", f"- {L['tl_start'].format(d=tl.latest_start)}",
                f"- {L['tl_trans'].format(d=tl.transition_end)}", f"- {L['tl_retr'].format(d=tl.retrieval_end)}", ""]
        key = "tl_after" if tl.start_after_ban else "tl_before"
        out += [L[key].format(full=full, earliest=tl.earliest_notice_for_ban), ""]

    if result.risks:
        out += [f"## {L['risks']}", ""]
        seen = set()
        for file, line, res, msg in result.risks:
            out.append(f"- `{file}:{line}` ({res}): {msg}" if msg not in seen else f"- `{file}:{line}` ({res}): same as above")
            seen.add(msg)
        out.append("")

    if plan.services:
        out += [f"## {L['alts']}", ""] + [f"- {f.service.name}: {f.service.alternatives}" for f in plan.services] + [""]

    out += [f"## {T['title']}", "", f"_{T['note']}_", ""]
    for p in PHASES:
        out += [f"### {T['phase' + p]}", ""]
        out += [f"- [ ] {s}" for s in phase_steps(lang, p)]
        if p == "3" and plan.services:
            out += ["", f"**{T['services']}**", ""]
            for f in plan.services:
                for step in f.service.steps:
                    out.append(f"- [ ] {f.service.name}: {step}")
        out.append("")
    out += ["---", L["disc"].format(asof=AS_OF), f"cloudexit {__version__}", ""]
    return "\n".join(out)


def to_json(result, plan, fx=0.92):
    t = totals(plan, fx)
    return json.dumps({
        "root": result.root, "files_scanned": result.files_scanned, "providers": sorted(result.providers),
        "services": [{"key": f.service_key, "name": f.service.name, "provider": f.service.provider,
                      "lockin": f.service.lockin, "resources": f.resources,
                      "evidence": [{"file": e.file, "line": e.line, "kind": e.kind, "detail": e.detail} for e in f.evidence]}
                     for f in plan.services],
        "lockin_score": plan.lockin_score,
        "egress": [{"provider": e.provider, "gb": e.gb, "list_cost_usd": e.list_cost, "per_tb_list_usd": e.per_tb_list} for e in plan.egress],
        "effort_days": plan.effort_days, "totals_eur": {k: v for k, v in t.items()},
        "timeline": None if not plan.timeline else {k: str(v) for k, v in vars(plan.timeline).items()},
        "risks": [{"file": f, "line": l, "resource": r, "message": m} for f, l, r, m in result.risks],
    }, indent=2, default=str)
