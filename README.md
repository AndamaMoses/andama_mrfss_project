S/N	BUSINESS NAME	                         CATEGORY	                    CONTACT	           ADDRESS
1	COMMUNION ENGINEERING SERVICES LTD     	CONSULTANT AGENCY	           0776102744	         JINJA
2	ONZIMA CHARLSE DRUG SHOP	                HEALTH CARE RETAIL		                         KIREKA










Challenges Facing Consultant Agencies Consultant agencies face several challenges that can affect their performance, profitability, and ability to satisfy clients. Some of the major challenges include:
1.	High competition – Many consulting firms offer similar services, making it difficult to attract and retain clients.
2.	Difficulty in attracting qualified consultants – Finding professionals with the right skills, experience, and expertise can be challenging.
3.	Changing client needs – Clients' requirements change frequently, forcing consulting agencies to continuously adapt their services.
4.	Limited financial resources – Small consulting agencies may struggle with limited capital, delayed client payments, and high operating costs.
5.	Maintaining quality services – Agencies must consistently provide high-quality and reliable advice to maintain their reputation and client trust.
6.	Client expectations – Some clients expect quick results at low costs, which can create pressure on consultants.
7.	Technological changes – Rapid changes in technology require agencies to continuously learn, invest in new tools, and update their skills.
8.	Regulatory and legal requirements – Changes in government regulations, licensing requirements, taxation, and professional standards can increase the cost and complexity of operations.
9.	Difficulty in measuring results – It can sometimes be difficult to demonstrate the direct impact and value of consulting services to clients.
10.	Dependence on clients – Losing a major client can significantly affect the agency's revenue, especially for small firms.
11.	Time management – Consultants may have to handle several projects simultaneously, leading to workload pressure and missed deadlines.
12.	Building client trust – New agencies may find it difficult to establish credibility and convince clients to hire them.
13.	Confidentiality and data security – Consultants often handle sensitive business information, creating risks related to data loss, unauthorized access, or disclosure.
14.	Economic instability – Inflation, economic downturns, and reduced business spending can cause organizations to cut consulting budgets.
15.	Staff turnover – Experienced consultants may leave for better-paying jobs or start their own consulting businesses, resulting in loss of skills and clients.

Solutions to Challenges Facing Consultant Agencies — From a Web Developer's Perspective Challenge Web-based solution
1.	High competition Develop a professional, modern website that clearly presents the agency's services, previous projects, expertise, testimonials, and contact information.
2.	Difficulty finding clients Build an online client-acquisition system with service pages, inquiry forms, appointment booking, SEO, and social-media integration.
3.	Difficulty managing clients Create a Client Management System (CRM) where consultants can register clients, track projects, record communication, and monitor progress.
4.	Poor project management Develop a project-management dashboard showing tasks, deadlines, assigned consultants, project status, and milestones.
5.	Poor communication Add secure messaging, email notifications, contact forms, and automated updates so clients can communicate with consultants easily.
6.	Delayed payments Integrate online invoicing and payment systems so clients can receive invoices, make payments, and receive payment confirmations electronically.
7.	Difficulty measuring performance Create dashboards and reports showing revenue, completed projects, active clients, consultant performance, and customer satisfaction.
8.	Maintaining quality services Build a client feedback and rating system. Management can use the feedback to identify weaknesses and improve services.
9.	Poor record keeping Replace paper files with a secure digital database for client information, contracts, reports, invoices, and project documents.
10.	Data security problems Implement secure login, role-based access, encrypted passwords, backups, audit logs, and controlled access to sensitive documents.
11.	Changing client requirements Build a flexible system where services, project requirements, pricing, and client information can easily be updated.
12.	Limited resources Automate repetitive activities such as invoices, reports, appointment reminders, emails, and project notifications to reduce administrative work.
13.	Difficulty demonstrating results Create automated reports and visual dashboards that show clients project progress, completed work, costs, and measurable outcomes.
14.	Staff turnover Store organizational knowledge, project records, procedures, and client history in a centralized system so work can continue when employees leave.
15.	Lack of online presence Develop a responsive website that works on phones, tablets, and computers, allowing potential clients to find the agency 24/7.


Challenges faced by consultants Agencies
1.	Unstable cash flow – Payments from clients may be delayed, making it difficult to pay staff and operating expenses.
2.	High competition – Many consultancy firms offer similar services, making it difficult to attract and retain clients.
3.	Difficulty finding clients – New agencies often struggle to build a strong client base and reputation.
4.	Client expectations – Clients may expect quick, inexpensive results even when the work requires significant time and expertise.
5.	Limited skilled personnel – Finding consultants with the right technical skills and experience can be difficult.
6.	Changing regulations – Changes in government policies, laws, and industry standards can require agencies to continually update their knowledge.
7.	Scope creep – Clients may request additional work without agreeing to additional fees.
8.	Delayed client decisions – Consultancy projects can be slowed when clients take too long to provide information, approvals, or feedback.
9.	Maintaining quality – Delivering consistently high-quality work across multiple projects can be challenging.
10.	Technology changes – Agencies must continually invest in new software, tools, and digital skills.
11.	Reputation risks – A single unsuccessful project or dissatisfied client can negatively affect the agency's reputation.
12.	Difficulty retaining consultants – Experienced employees may leave for better-paying jobs or competitors.
13.	Poor project management – Weak planning, budgeting, or scheduling can cause projects to exceed their deadlines and budgets.
14.	Economic uncertainty – When businesses reduce spending, consultancy services may be among the expenses they cut.
15.	Data confidentiality and security – Consultants often handle sensitive client information and must protect it from unauthorized access.


## Running locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:PYTHONIOENCODING = "utf-8"
python -m pip install -r requirements-dev.txt
python run.py
```

Open `http://127.0.0.1:5000` for the drug shop and
`http://127.0.0.1:5000/tender` for Tender Copilot. Tender Copilot can also be
sold and hosted as a standalone workspace; see
[`docs/tender-standalone.md`](docs/tender-standalone.md) for the optional
separate-domain mapping, shared sign-in settings, and demo-hygiene rules.

## Packaging runbooks

- [Onboarding runbook](docs/onboarding-runbook.md) — backup, first boot, plan
  activation, smoke checks, and handover.
- [Rollback runbook](docs/rollback-runbook.md) — access, code, and database
  rollback, plus the restore rehearsal.
- [Pilot runbook](docs/pilot-runbook.md) — Onzima Legacy deployment, Core
  staging rehearsal, owner walkthrough, and daily observation.
- [Pilot tracker](docs/pilot-tracker.md) — baseline, daily metrics, support
  tickets, and exit decision.

The Phase 5 packaging dry run copies the real database, applies the additive
migration, seeds a bundle, checks access, downgrades to Core, re-upgrades, and
rehearses a restore. It never writes to the source database or backup:

```powershell
python scripts\dry_run_packaging.py --bundle legacy `
    --restore-backup "instance\backups\drugshop-pre-packaging-20261021-161243.db"
```

Use `--bundle pro` for the Pro acceptance path. The script prints a `PASS` line
and leaves a temporary directory behind only when `--keep` is passed.

## Tests and lint

```powershell
python -m pytest -q
python -m ruff check .
```

With the app running, execute the HTTP smoke checks:

```powershell
$env:SMOKE_PASSWORD = "the-admin-password"
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1 -Plan core -Username admin
```

The smoke script checks `/api/apps`, plan-aware POS/Patients access, the Tender
redirect, and the always-on backup endpoint. Use
`-Plan core|pro|growth|tender|legacy|unseeded` to assert a plan, or omit `-Plan`
to detect it. `SMOKE_PASSWORD` keeps the password out of shell history; fresh
installs fall back to `admin123`. Pass `-Username` if the admin username is not
`admin`.

During the pilot, collect activation, login, and 403-denial metrics without
changing the database:

```powershell
python scripts\pilot_metrics.py --log instance\pilot\server.log
```
