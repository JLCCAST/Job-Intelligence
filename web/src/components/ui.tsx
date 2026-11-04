import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  HelpCircle,
  Info,
  Loader2,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
  MoveRight,
  XCircle,
} from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { Oferta } from "../api";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

export const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;

export const formatoScore = (s: number | null | undefined) => (s == null ? "—" : `${s.toFixed(1)}%`);

export function fechaCorta(valor?: string | null) {
  if (!valor) return "";
  const d = new Date(valor);
  return isNaN(d.getTime()) ? "" : d.toLocaleDateString("es-PE", { day: "2-digit", month: "short", year: "numeric" });
}

// ---------- Encabezado de página ----------

export function Encabezado({ seccion, titulo, descripcion, acciones }: {
  seccion?: string; titulo: string; descripcion?: string; acciones?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
      <div className="max-w-2xl">
        {seccion && <p className="mb-1 text-sm text-ink-3">{seccion} /</p>}
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{titulo}</h1>
        {descripcion && <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{descripcion}</p>}
      </div>
      {acciones && <div className="flex flex-wrap gap-2">{acciones}</div>}
    </header>
  );
}

// ---------- Superficies ----------

export function Tarjeta({ children, className, ...props }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx("rounded-md border border-line bg-surface p-5", className)} {...props}>
      {children}
    </div>
  );
}

export function Seccion({ titulo, extra, children }: { titulo: string; extra?: ReactNode; children: ReactNode }) {
  return (
    <section className="mt-9">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-ink">{titulo}</h2>
        {extra}
      </div>
      {children}
    </section>
  );
}

// ---------- Botones ----------

type Variante = "primario" | "secundario" | "fantasma" | "peligro";

export function Boton({ variante = "secundario", icono: Icono, cargando, children, className, ...props }: {
  variante?: Variante; icono?: LucideIcon; cargando?: boolean;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const estilos: Record<Variante, string> = {
    primario: "bg-primary text-white hover:bg-primary-hover",
    secundario: "border border-line bg-surface text-ink hover:bg-surface-2",
    fantasma: "text-ink-2 hover:bg-surface-2 hover:text-ink",
    peligro: "border border-line bg-surface text-bad hover:bg-bad-soft",
  };
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
        "disabled:cursor-not-allowed disabled:opacity-55",
        estilos[variante],
        className,
      )}
      disabled={cargando || props.disabled}
      {...props}
    >
      {cargando ? <Loader2 className="size-4 animate-spin" /> : Icono && <Icono className="size-4" />}
      {children}
    </button>
  );
}

// ---------- Insignias ----------

type Tono = "ok" | "warn" | "bad" | "info" | "neutro";
const TONOS: Record<Tono, string> = {
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  info: "bg-primary-soft text-primary",
  neutro: "bg-surface-2 text-ink-2",
};

export function Insignia({ tono = "neutro", icono: Icono, children }: { tono?: Tono; icono?: LucideIcon; children: ReactNode }) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-xs font-medium", TONOS[tono])}>
      {Icono && <Icono className="size-3.5" />}
      {children}
    </span>
  );
}

/** Nivel de encaje: el texto acompaña siempre al color (nunca solo color). */
export function nivelEncaje(score: number | null | undefined): { texto: string; tono: Tono; icono: LucideIcon } {
  if (score == null) return { texto: "Sin score", tono: "neutro", icono: HelpCircle };
  if (score >= 75) return { texto: "Encaje alto", tono: "ok", icono: TrendingUp };
  if (score >= 50) return { texto: "Encaje medio", tono: "warn", icono: MoveRight };
  return { texto: "Encaje bajo", tono: "bad", icono: TrendingDown };
}

export function InsigniaEncaje({ score }: { score: number | null | undefined }) {
  const n = nivelEncaje(score);
  return <Insignia tono={n.tono} icono={n.icono}>{n.texto}</Insignia>;
}

/** Match Score: número en monoespaciada con una barra fina debajo. */
export function AnilloScore({ score, tamano = 64 }: { score: number | null; tamano?: number }) {
  const valor = score ?? 0;
  const color = score == null ? "var(--text-3)" : valor >= 75 ? "var(--ok)" : valor >= 50 ? "var(--warn)" : "var(--bad)";
  return (
    <div className="shrink-0" style={{ width: tamano }} aria-label={`Match Score ${formatoScore(score)}`}>
      <p className="font-mono text-xl font-semibold tabular-nums text-ink" style={{ fontSize: tamano > 70 ? 28 : 20 }}>
        {score == null ? "—" : `${Math.round(valor)}%`}
      </p>
      <div className="mt-1 h-[3px] w-full bg-line">
        <div className="h-full" style={{ width: `${valor}%`, background: color }} />
      </div>
    </div>
  );
}

// ---------- Indicadores ----------

export function Indicador({ etiqueta, valor, icono: Icono, ayuda }: { etiqueta: string; valor: ReactNode; icono: LucideIcon; ayuda?: string }) {
  return (
    <Tarjeta className="p-4" title={ayuda}>
      <p className="flex items-center gap-1.5 text-xs font-medium text-ink-2">
        <Icono className="size-3.5 text-ink-3" /> {etiqueta}
      </p>
      <p className="mt-1.5 font-mono text-2xl font-semibold tabular-nums text-ink">{valor}</p>
    </Tarjeta>
  );
}

// ---------- Estados ----------

export function Cargando({ texto = "Cargando..." }: { texto?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-ink-2">
      <Loader2 className="size-5 animate-spin" /> {texto}
    </div>
  );
}

export function Aviso({ tono = "info", titulo, children }: { tono?: Tono; titulo?: string; children?: ReactNode }) {
  const iconos: Record<Tono, LucideIcon> = { ok: CheckCircle2, warn: AlertTriangle, bad: XCircle, info: Info, neutro: Info };
  const Icono = iconos[tono];
  return (
    <div className={cx("flex gap-3 rounded-md px-4 py-3 text-sm", TONOS[tono])} role={tono === "bad" ? "alert" : "status"}>
      <Icono className="mt-0.5 size-4 shrink-0" />
      <div className="leading-relaxed">
        {titulo && <p className="font-semibold">{titulo}</p>}
        {children && <div className={cx(titulo && "mt-0.5", "opacity-90")}>{children}</div>}
      </div>
    </div>
  );
}

export function Vacio({ icono: Icono, titulo, children }: { icono: LucideIcon; titulo: string; children?: ReactNode }) {
  return (
    <Tarjeta className="flex flex-col items-center py-12 text-center">
      <span className="mb-3 flex size-12 items-center justify-center rounded-md bg-surface-2 text-ink-3">
        <Icono className="size-6" />
      </span>
      <p className="font-semibold text-ink">{titulo}</p>
      {children && <div className="mt-1 max-w-md text-sm text-ink-2">{children}</div>}
    </Tarjeta>
  );
}

// ---------- Tarjeta de oferta ----------

export function TarjetaOferta({ oferta, acciones, mostrarEstado = true }: {
  oferta: Oferta; acciones?: ReactNode; mostrarEstado?: boolean;
}) {
  const meta = [oferta.empresa, oferta.fuente, fechaCorta(oferta.fecha_registro)].filter(Boolean).join(" · ");
  return (
    <Tarjeta className="aparecer flex flex-col gap-4 transition hover:border-primary/40 sm:flex-row sm:items-center">
      <AnilloScore score={oferta.match_score} />
      <div className="min-w-0 flex-1">
        <p className="font-semibold leading-snug text-ink">{oferta.puesto}</p>
        <p className="mt-0.5 text-sm text-ink-2">{meta}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <InsigniaEncaje score={oferta.match_score} />
          {mostrarEstado && <Insignia>{oferta.estado}</Insignia>}
          {oferta.url && (
            <a href={oferta.url} target="_blank" rel="noreferrer"
               className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
              Ver oferta <ExternalLink className="size-3" />
            </a>
          )}
        </div>
      </div>
      {acciones && <div className="flex flex-wrap gap-2 sm:justify-end">{acciones}</div>}
    </Tarjeta>
  );
}

// ---------- Formularios ----------

export const claseCampo =
  "w-full rounded-md border border-line bg-surface px-3.5 py-2.5 text-sm text-ink placeholder:text-ink-3 " +
  "focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20";

export function Campo({ etiqueta, ayuda, children }: { etiqueta: string; ayuda?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-ink">{etiqueta}</span>
      {children}
      {ayuda && <span className="mt-1 block text-xs text-ink-3">{ayuda}</span>}
    </label>
  );
}

export function Segmentado<T extends string>({ opciones, valor, onChange, etiqueta }: {
  opciones: T[]; valor: T; onChange: (v: T) => void; etiqueta: string;
}) {
  return (
    <div role="radiogroup" aria-label={etiqueta} className="inline-flex rounded-md border border-line bg-surface p-1">
      {opciones.map((o) => (
        <button
          key={o} role="radio" aria-checked={o === valor} onClick={() => onChange(o)}
          className={cx(
            "rounded px-3 py-1.5 text-sm font-medium transition",
            o === valor ? "bg-primary-soft text-primary" : "text-ink-2 hover:text-ink",
          )}
        >
          {o}
        </button>
      ))}
    </div>
  );
}
