import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  CheckCircle2,
  ChefHat,
  ClipboardCheck,
  Clock3,
  FileText,
  Gauge,
  LogOut,
  PackageCheck,
  ReceiptText,
  Search,
  ShieldCheck,
  Sparkles,
  Truck,
  Warehouse
} from "lucide-react";
import { FormEvent, ReactNode, useMemo, useState } from "react";
import { api, clearAccessToken, hasAccessToken } from "./lib/api";
import type { CommandCard, GlobalIQAnswer, TimelineStep, UniversalRecord, UserSession } from "./types";

type DashboardData = {
  commandCards: CommandCard[];
  timeline: TimelineStep[];
  orders: UniversalRecord[];
  receiving: UniversalRecord[];
  invoices: UniversalRecord[];
  inventory: UniversalRecord[];
  recipes: UniversalRecord[];
  tasks: UniversalRecord[];
};

const MODULES = [
  { key: "orders", label: "Purchasing", icon: Truck },
  { key: "receiving", label: "Dock", icon: PackageCheck },
  { key: "invoices", label: "AP / Invoices", icon: ReceiptText },
  { key: "inventory", label: "Inventory", icon: Warehouse },
  { key: "recipes", label: "Recipes", icon: ChefHat },
  { key: "tasks", label: "Tasks", icon: ClipboardCheck }
] as const;

export function formatMoney(minor: number | undefined) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format((minor ?? 0) / 100);
}

export function titleCase(value: unknown) {
  return String(value ?? "unknown")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function StatusPill({ value }: { value: unknown }) {
  const status = String(value ?? "unknown").toLowerCase();
  const tone = status.includes("exception") || status.includes("blocked") ? "danger" : status.includes("complete") || status.includes("approved") ? "good" : "watch";
  return <span className={`status status--${tone}`}>{titleCase(status)}</span>;
}

function Panel({ title, eyebrow, action, children, className = "" }: { title: string; eyebrow?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel__header">
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2>{title}</h2>
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

function Login({ onLogin }: { onLogin: (session: UserSession) => void }) {
  const [email, setEmail] = useState("owner@bcaz.example");
  const [password, setPassword] = useState("");
  const login = useMutation({ mutationFn: () => api.login(email, password), onSuccess: onLogin });

  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate();
  }

  return (
    <main className="login-shell">
      <section className="login-story" aria-labelledby="product-title">
        <div className="brand-mark" aria-hidden="true"><span>B</span><i>IQ</i></div>
        <p className="eyebrow">Blue Collar Apps Co. / Operator Intelligence</p>
        <h1 id="product-title">THE BACK OFFICE,<br /><em>REBUILT FROM THE TRENCHES.</em></h1>
        <p className="login-story__copy">Purchasing, receiving, invoices, inventory, recipes, production, and operational evidence—connected in one hard-working command system.</p>
        <div className="login-proof">
          <span><ShieldCheck size={18} /> Tenant scoped</span>
          <span><FileText size={18} /> Evidence backed</span>
          <span><Gauge size={18} /> Operator first</span>
        </div>
      </section>

      <section className="login-card" aria-label="Sign in">
        <div>
          <p className="eyebrow">SECURE ACCESS</p>
          <h2>Clock into command.</h2>
          <p>Use the administrator credentials configured for this environment.</p>
        </div>
        <form onSubmit={submit}>
          <label htmlFor="email">Email</label>
          <input id="email" name="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required />
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
          {login.isError && <div className="form-error" role="alert"><AlertTriangle size={17} /> {login.error.message}</div>}
          <button className="button button--primary" type="submit" disabled={login.isPending}>
            {login.isPending ? "Checking credentials…" : "Enter B.O.H IQ"}<ArrowRight size={18} />
          </button>
        </form>
        <p className="login-card__foot">Authorized operators only. Actions are logged to the operational audit trail.</p>
      </section>
    </main>
  );
}

function CommandCardView({ card }: { card: CommandCard }) {
  const queryClient = useQueryClient();
  const action = useMutation({
    mutationFn: (value: string) => api.actOnCommandCard(card.id, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dashboard"] })
  });
  return (
    <article className="command-card">
      <div className="command-card__rank">#{card.rank}</div>
      <div className="command-card__body">
        <div className="command-card__meta"><StatusPill value={card.section} /><span>{Math.round(Number(card.confidence) * 100)}% confidence</span></div>
        <h3>{card.plain_language_issue}</h3>
        <p>{card.recommended_action}</p>
        <dl>
          <div><dt>Impact</dt><dd>{formatMoney(card.dollar_impact_minor)}</dd></div>
          <div><dt>Owner</dt><dd>{card.owner}</dd></div>
          <div><dt>Source</dt><dd>{card.source}</dd></div>
        </dl>
        <div className="button-row">
          {card.actions.map((item) => <button className="button button--quiet" key={item} onClick={() => action.mutate(item)} disabled={action.isPending}>{titleCase(item)}</button>)}
        </div>
      </div>
    </article>
  );
}

function GlobalIQ() {
  const [question, setQuestion] = useState("Why did food cost rise this week?");
  const query = useMutation<GlobalIQAnswer, Error, string>({ mutationFn: api.askGlobalIQ });
  function submit(event: FormEvent) {
    event.preventDefault();
    query.mutate(question);
  }
  return (
    <Panel title="Ask Global IQ" eyebrow="Evidence, not guesses" className="iq-panel">
      <form className="iq-form" onSubmit={submit}>
        <Search size={19} aria-hidden="true" />
        <input value={question} onChange={(event) => setQuestion(event.target.value)} aria-label="Ask Global IQ" placeholder="Ask what changed, why, and what needs attention…" />
        <button className="button button--primary" disabled={query.isPending}>{query.isPending ? "Tracing…" : "Trace evidence"}</button>
      </form>
      {query.isError && <div className="form-error" role="alert"><AlertTriangle size={17} /> {query.error.message}</div>}
      {query.data && (
        <div className="iq-answer">
          <div className="iq-answer__icon"><Sparkles size={20} /></div>
          <div>
            <p>{query.data.answer}</p>
            <div className="citation-row">
              {query.data.citations.map((citation) => <span key={`${citation.domain}-${citation.id}`}>{citation.domain} / {citation.id}</span>)}
              <b>{Math.round(Number(query.data.confidence) * 100)}% confidence</b>
              {query.data.agent && <span className="iq-agent-tag">{titleCase(query.data.agent.replace(/-/g, " "))}</span>}
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}

function RecordsTable({ domain, records }: { domain: string; records: UniversalRecord[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Record</th><th>Location</th><th>Status</th><th>Operational detail</th></tr></thead>
        <tbody>
          {records.map((record) => {
            const name = record.name ?? record.title ?? record.invoice_number ?? record.id;
            const detail = record.vendor_id ?? record.item_id ?? record.recipe_id ?? record.transaction_type ?? domain;
            return <tr key={record.id}><td><strong>{String(name)}</strong><small>{record.id}</small></td><td>{String(record.location_id ?? "Organization-wide")}</td><td><StatusPill value={record.status ?? record.approval_status ?? record.batch_status ?? "active"} /></td><td>{titleCase(detail)}</td></tr>;
          })}
          {!records.length && <tr><td colSpan={4} className="empty-state">No records are available for this operating area.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function Dashboard({ session, onLogout }: { session: UserSession; onLogout: () => void }) {
  const [activeModule, setActiveModule] = useState<(typeof MODULES)[number]["key"]>("orders");
  const dashboard = useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const [commandCards, timeline, orders, receiving, invoices, inventory, recipes, tasks] = await Promise.all([
        api.commandBoard(),
        api.timeline("po_10042").then((value) => value.timeline),
        api.list("orders").then((value) => value.data),
        api.list("receiving").then((value) => value.data),
        api.list("invoices").then((value) => value.data),
        api.list("inventory").then((value) => value.data),
        api.list("recipes").then((value) => value.data),
        api.list("tasks").then((value) => value.data)
      ]);
      return { commandCards, timeline, orders, receiving, invoices, inventory, recipes, tasks };
    }
  });
  const data = dashboard.data;
  const openImpact = useMemo(() => data?.commandCards.reduce((sum, card) => sum + card.dollar_impact_minor, 0) ?? 0, [data]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><div className="brand-mark brand-mark--small"><span>B</span><i>IQ</i></div><div><strong>BCAz B.O.H</strong><small>GLOBAL IQ / COMMAND</small></div></div>
        <div className="topbar__right"><span className="live-indicator"><i /> SYSTEM LIVE</span><div className="operator"><b>{session.name}</b><small>{titleCase(session.roles[0])}</small></div><button className="icon-button" onClick={onLogout} aria-label="Log out"><LogOut size={19} /></button></div>
      </header>

      <aside className="sidebar" aria-label="Operating modules">
        <p className="sidebar__label">OPERATING RAIL</p>
        {MODULES.map((module) => <button key={module.key} className={activeModule === module.key ? "active" : ""} onClick={() => setActiveModule(module.key)}><module.icon size={19} /><span>{module.label}</span></button>)}
        <div className="sidebar__bottom"><ShieldCheck size={18} /><div><b>Tenant lock</b><small>{session.organization_id}</small></div></div>
      </aside>

      <main className="workspace">
        <section className="workspace__lead">
          <div><p className="eyebrow">TODAY'S COMMAND BOARD</p><h1>WHAT NEEDS A HAND<br /><em>RIGHT NOW.</em></h1></div>
          <div className="shift-stamp"><Clock3 size={17} /><span>Live operating view</span><b>PHOENIX / ALL DAY</b></div>
        </section>

        {dashboard.isError && <div className="critical-error" role="alert"><AlertTriangle /><div><b>Command data could not be loaded.</b><p>{dashboard.error.message}</p></div><button className="button button--quiet" onClick={() => dashboard.refetch()}>Retry</button></div>}

        <section className="metrics" aria-label="Operational summary">
          <article><span>OPEN EXCEPTIONS</span><strong>{data?.commandCards.length ?? "—"}</strong><small>requiring ownership</small></article>
          <article><span>DOLLARS EXPOSED</span><strong>{data ? formatMoney(openImpact) : "—"}</strong><small>verified open impact</small></article>
          <article><span>DOCK STATUS</span><strong>{data?.receiving.length ?? "—"}</strong><small>active receiving sessions</small></article>
          <article><span>INVENTORY EVENTS</span><strong>{data?.inventory.length ?? "—"}</strong><small>ledger-backed movements</small></article>
        </section>

        <div className="command-grid">
          <Panel title="Ranked exceptions" eyebrow="Work the costly handoffs first" className="exceptions-panel" action={<span className="panel-count">{data?.commandCards.length ?? 0} OPEN</span>}>
            <div className="command-list">{data?.commandCards.map((card) => <CommandCardView key={card.id} card={card} />)}{dashboard.isLoading && <div className="skeleton">Loading operating evidence…</div>}</div>
          </Panel>

          <Panel title="Procure-to-pay chain" eyebrow="PO 10042 / source-linked">
            <ol className="timeline">{data?.timeline.map((step, index) => <li key={step.step}><span className={step.status === "pending" ? "pending" : "done"}>{step.status === "pending" ? index + 1 : <CheckCircle2 size={18} />}</span><div><b>{step.step}</b><small>{titleCase(step.status)}</small></div></li>)}</ol>
            <div className="source-lock"><ShieldCheck size={18} /><p><b>Evidence lock active.</b><br />Every stage retains its originating record.</p></div>
          </Panel>
        </div>

        <GlobalIQ />

        <Panel title={MODULES.find((module) => module.key === activeModule)?.label ?? activeModule} eyebrow="Current tenant records" action={<span className="panel-count">{data?.[activeModule].length ?? 0} RECORDS</span>}>
          <RecordsTable domain={activeModule} records={data?.[activeModule] ?? []} />
          {activeModule === "recipes" && <div className="liability-note"><AlertTriangle size={18} /><p>Allergen information supports operational review only and never guarantees safety. Verify current labels, methods, and cross-contact controls.</p></div>}
        </Panel>
      </main>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState<UserSession | null>(null);
  const existingSession = useQuery({
    queryKey: ["session"],
    queryFn: api.me,
    enabled: hasAccessToken() && !session,
    retry: false
  });
  const activeSession = session ?? existingSession.data ?? null;
  function logout() {
    clearAccessToken();
    setSession(null);
    window.location.reload();
  }
  if (!activeSession) return <Login onLogin={setSession} />;
  return <Dashboard session={activeSession} onLogout={logout} />;
}

