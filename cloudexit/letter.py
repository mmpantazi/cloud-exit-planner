"""Draft switching request to send to a provider. Placeholders in [brackets] must be filled in."""
from .estimate import provider_name

TEMPLATES = {
    "en": """Subject: Request to switch data processing service provider (EU Data Act, Chapter VI)

To: {provider}
Account / contract reference: [account id]
Date: {date}

We are giving notice that we intend to switch from {provider} to [new provider / our own infrastructure] for the following services: {services}.

Under Chapter VI of Regulation (EU) 2023/2854 (Data Act), please confirm in writing within [14] days:

1. The date on which the switching process will start (no later than two months after this notice) and the end of the 30-day transition period.
2. The procedure, interfaces and formats for exporting our exportable data and digital assets, with documentation.
3. The categories of data and digital assets that you consider exportable, and any you regard as excluded, with the reason.
4. All charges that you will apply to the switch, itemised, and the date from which switching charges are no longer applied (12 January 2027).
5. The retrieval period after the transition (at least 30 days) and how and when you will delete our data afterwards, with written confirmation of deletion.
6. For infrastructure services: the steps you will take towards functional equivalence on the destination service.
7. Any known risk to service continuity during the transition.

Please also confirm which of your transfer-out fee waiver programmes apply and under what conditions.

Kind regards,
[name, role, company]
""",
    "ro": """Subiect: Cerere de schimbare a furnizorului serviciului de prelucrare a datelor (Actul UE privind datele, Capitolul VI)

Către: {provider}
Cont / referință contract: [id cont]
Data: {date}

Vă notificăm intenția de a trece de la {provider} la [noul furnizor / infrastructura proprie] pentru serviciile: {services}.

În temeiul Capitolului VI din Regulamentul (UE) 2023/2854 (Actul privind datele), vă rugăm să confirmați în scris în termen de [14] zile:

1. Data la care începe procesul de schimbare (cel târziu la două luni după această notificare) și data la care se încheie perioada de tranziție de 30 de zile.
2. Procedura, interfețele și formatele de export pentru datele și activele digitale exportabile, cu documentație.
3. Categoriile de date și active digitale pe care le considerați exportabile și cele pe care le considerați excluse, cu motivul.
4. Toate taxele pe care le veți aplica pentru schimbare, detaliate, și data de la care taxele de schimbare nu se mai aplică (12 ianuarie 2027).
5. Perioada de recuperare după tranziție (cel puțin 30 de zile) și modul și momentul în care ne veți șterge datele, cu confirmare scrisă a ștergerii.
6. Pentru serviciile de infrastructură: pașii pe care îi veți face pentru echivalența funcțională pe serviciul de destinație.
7. Orice risc cunoscut pentru continuitatea serviciului în timpul tranziției.

Vă rugăm să confirmați și ce programe de scutire de taxe de transfer se aplică și în ce condiții.

Cu stimă,
[nume, funcție, companie]
""",
}


def drafts(plan, notice, lang="en"):
    out = []
    for prov in sorted({f.service.provider for f in plan.services}):
        names = ", ".join(f.service.name for f in plan.services if f.service.provider == prov)
        out.append(TEMPLATES[lang].format(provider=provider_name(prov), date=notice, services=names))
    return "\n---\n\n".join(out)
