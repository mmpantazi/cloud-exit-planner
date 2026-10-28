"""Data Act-style exit checklist. Article numbers follow secondary legal commentary, not EUR-Lex."""

TEXT = {
    "en": {
        "title": "Migration checklist",
        "note": "Modelled on Chapter VI of the EU Data Act (Regulation 2023/2854). Not legal advice: check the article text and your contract.",
        "phase0": "0. Know where you stand",
        "phase1": "1. Switching request",
        "phase2": "2. Prepare the target",
        "phase3": "3. Transition",
        "phase4": "4. Verify and retrieve",
        "phase5": "5. Delete and close",
        "services": "Service-specific steps",
        "steps0": [
            "Read the contract: notice term, committed spend, early-termination fees (these are NOT covered by the switching-charge ban), data-export formats and support terms.",
            "List the exportable data per service: input and output data and metadata you produced. Trade secrets and the provider's own IP may be excluded.",
            "Pick the target (another provider or on-premises) and get a written quote and a data-import method from it.",
            "Decide what is moved, what is rebuilt and what is retired; record owners for each service.",
        ],
        "steps1": [
            "Send the switching request in writing to the provider. The provider may not require more than two months' notice to start the process (Art. 25).",
            "Ask in the same message for: the export procedure and formats, the list of exportable data categories, the charges that will apply, and the transition and retrieval periods (Art. 26).",
            "Ask the provider to confirm the date the process starts and that charges are limited to their direct costs, or zero after 12 January 2027 (Art. 29).",
            "Keep the reply: the provider's answer is your evidence if the invoice differs.",
        ],
        "steps2": [
            "Build the target environment from code (Terraform/compose) and run it empty first.",
            "Lower DNS TTLs to 300 seconds at least a week before cut-over.",
            "Rotate nothing yet; list every secret and token that must be reissued after the move.",
            "Rehearse a restore from a backup on the target and time it: that time is your minimum downtime.",
            "Set up monitoring and backups on the target before any production data lands there.",
        ],
        "steps3": [
            "The provider must support the transition for up to 30 days (extendable only if technically unfeasible, Art. 25).",
            "Copy data in bulk first, then sync deltas; freeze writes only for the last delta.",
            "Keep the old environment running in parallel until the new one has served real traffic. Parallel use may be charged at cost (Art. 34).",
            "For infrastructure services (IaaS) the provider must help reach functional equivalence on the target (Art. 30).",
        ],
        "steps4": [
            "Verify object counts, row counts and checksums on the target; keep the output as evidence.",
            "Use the retrieval period (at least 30 days after the transition) to fetch anything you missed.",
            "Run the application's full test suite and a restore test against the target data.",
            "Switch DNS, watch error rates for a week, keep the old data read-only meanwhile.",
        ],
        "steps5": [
            "Ask the provider in writing to delete your data after the retrieval period and to confirm deletion.",
            "Terminate the contract and cancel marketplace subscriptions, support plans and reserved capacity.",
            "Revoke API keys, service accounts, OAuth apps and SSO links on the old provider; rotate shared secrets.",
            "Update the GDPR records of processing, the processor list and customer-facing sub-processor notices.",
            "Check the final invoice against the charges the provider confirmed in step 1.",
        ],
        "title_report": "Cloud Exit Plan",
    },
    "ro": {
        "title": "Listă de verificare pentru migrare",
        "note": "Construită după Capitolul VI din Actul UE privind datele (Regulamentul 2023/2854). Nu este consultanță juridică: verificați textul articolelor și contractul. Pașii pe servicii rămân în engleză.",
        "phase0": "0. Evaluați situația",
        "phase1": "1. Cererea de schimbare a furnizorului",
        "phase2": "2. Pregătiți destinația",
        "phase3": "3. Tranziția",
        "phase4": "4. Verificare și recuperare",
        "phase5": "5. Ștergere și închidere",
        "services": "Pași pe servicii",
        "steps0": [
            "Citiți contractul: preavizul, consumul angajat, penalitățile de reziliere (NU sunt acoperite de interdicția taxelor de schimbare), formatele de export și condițiile de suport.",
            "Listați datele exportabile pentru fiecare serviciu: datele de intrare și de ieșire și metadatele produse de dvs. Secretele comerciale și proprietatea intelectuală a furnizorului pot fi excluse.",
            "Alegeți destinația (alt furnizor sau infrastructură proprie) și cereți o ofertă scrisă și metoda de import a datelor.",
            "Decideți ce se mută, ce se reconstruiește și ce se elimină; desemnați un responsabil pentru fiecare serviciu.",
        ],
        "steps1": [
            "Trimiteți cererea de schimbare în scris. Furnizorul nu poate cere un preaviz mai mare de două luni pentru a începe procesul (art. 25).",
            "Cereți în același mesaj: procedura și formatele de export, categoriile de date exportabile, taxele aplicabile, perioada de tranziție și perioada de recuperare (art. 26).",
            "Cereți confirmarea datei de început și a faptului că taxele sunt limitate la costurile directe ale furnizorului, respectiv zero după 12 ianuarie 2027 (art. 29).",
            "Păstrați răspunsul: este dovada dvs. dacă factura diferă.",
        ],
        "steps2": [
            "Construiți mediul țintă din cod (Terraform/compose) și porniți-l mai întâi gol.",
            "Reduceți TTL-ul DNS la 300 de secunde cu cel puțin o săptămână înainte de comutare.",
            "Nu schimbați încă nicio parolă; listați toate secretele și token-urile care trebuie reemise după mutare.",
            "Exersați o restaurare dintr-o copie de rezervă pe destinație și măsurați timpul: este indisponibilitatea minimă.",
            "Configurați monitorizarea și copiile de rezervă pe destinație înainte să ajungă date de producție.",
        ],
        "steps3": [
            "Furnizorul trebuie să sprijine tranziția până la 30 de zile (prelungire doar dacă este tehnic imposibil, art. 25).",
            "Copiați mai întâi datele în bloc, apoi sincronizați diferențele; blocați scrierile doar pentru ultima diferență.",
            "Păstrați vechiul mediu în paralel până când noul mediu a servit trafic real. Utilizarea în paralel poate fi taxată la cost (art. 34).",
            "Pentru servicii de infrastructură (IaaS), furnizorul trebuie să ajute la echivalența funcțională pe destinație (art. 30).",
        ],
        "steps4": [
            "Verificați numărul de obiecte, de rânduri și sumele de control pe destinație; păstrați rezultatul ca dovadă.",
            "Folosiți perioada de recuperare (cel puțin 30 de zile după tranziție) pentru ce ați ratat.",
            "Rulați testele complete ale aplicației și un test de restaurare pe datele din destinație.",
            "Comutați DNS-ul, urmăriți erorile o săptămână și păstrați între timp datele vechi în mod doar-citire.",
        ],
        "steps5": [
            "Cereți în scris furnizorului să șteargă datele după perioada de recuperare și să confirme ștergerea.",
            "Reziliați contractul și anulați abonamentele din marketplace, planurile de suport și capacitatea rezervată.",
            "Revocați cheile API, conturile de serviciu, aplicațiile OAuth și legăturile SSO de la vechiul furnizor; schimbați secretele comune.",
            "Actualizați registrul GDPR al prelucrărilor, lista persoanelor împuternicite și notificările către clienți privind sub-procesatorii.",
            "Comparați factura finală cu taxele confirmate de furnizor la pasul 1.",
        ],
        "title_report": "Plan de ieșire din cloud",
    },
}

LANGS = tuple(TEXT)
PHASES = ("0", "1", "2", "3", "4", "5")


def phase_steps(lang, phase):
    return TEXT[lang][f"steps{phase}"]
