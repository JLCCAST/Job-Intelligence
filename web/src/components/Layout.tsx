import {
  BarChart3,
  Bot,
  Briefcase,
  Compass,
  FilePen,
  FileSearch,
  Inbox,
  LayoutDashboard,
  ListChecks,
  Menu,
  Moon,
  Sun,
  User,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import { cx } from "./ui";

const GRUPOS: { titulo?: string; enlaces: { a: string; texto: string; icono: LucideIcon }[] }[] = [
  {
    enlaces: [
      { a: "/", texto: "Inicio", icono: LayoutDashboard },
      { a: "/agentes", texto: "Agentes", icono: Bot },
    ],
  },
  {
    titulo: "Ofertas",
    enlaces: [
      { a: "/bandeja", texto: "Bandeja", icono: Inbox },
      { a: "/analizar", texto: "Analizar oferta", icono: FileSearch },
      { a: "/postulaciones", texto: "Postulaciones", icono: Briefcase },
      { a: "/adaptar-cv", texto: "Adaptar CV", icono: FilePen },
    ],
  },
  {
    titulo: "Tú",
    enlaces: [
      { a: "/perfil", texto: "Mi perfil", icono: User },
      { a: "/que-estudiar", texto: "Qué estudiar", icono: Compass },
      { a: "/analisis", texto: "Análisis", icono: BarChart3 },
      { a: "/revision", texto: "Revisión del catálogo", icono: ListChecks },
    ],
  },
];

function useTema() {
  const [oscuro, setOscuro] = useState(() => {
    try {
      const guardado = localStorage.getItem("tema");
      if (guardado) return guardado === "oscuro";
    } catch {
      /* sin almacenamiento */
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });
  useEffect(() => {
    document.documentElement.classList.toggle("dark", oscuro);
    try {
      localStorage.setItem("tema", oscuro ? "oscuro" : "claro");
    } catch {
      /* sin almacenamiento */
    }
  }, [oscuro]);
  return [oscuro, setOscuro] as const;
}

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <img src="/icono.svg" alt="" className="size-6" />
      <span className="text-[15px] font-semibold tracking-tight text-ink">Job-Intelligence</span>
    </div>
  );
}

function Navegacion({ alNavegar }: { alNavegar?: () => void }) {
  return (
    <nav className="flex flex-col gap-6">
      {GRUPOS.map((g, i) => (
        <div key={i}>
          {g.titulo && <p className="mb-1 px-2.5 text-xs font-medium text-ink-3">{g.titulo}</p>}
          <ul className="flex flex-col gap-0.5">
            {g.enlaces.map(({ a, texto, icono: Icono }) => (
              <li key={a}>
                <NavLink
                  to={a} end={a === "/"} onClick={alNavegar}
                  className={({ isActive }) => cx(
                    "flex items-center gap-2.5 rounded px-2.5 py-1.5 text-sm transition",
                    isActive ? "bg-sidebar-2 font-medium text-ink" : "text-sidebar-ink hover:bg-sidebar-2/60 hover:text-ink",
                  )}
                >
                  <Icono className="size-4" /> {texto}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export default function Layout() {
  const [oscuro, setOscuro] = useTema();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const { pathname } = useLocation();

  // Con llaves: un efecto solo puede devolver una función de limpieza (o nada).
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  const botonTema = (
    <button
      onClick={() => setOscuro(!oscuro)}
      className="flex items-center gap-2 rounded px-2.5 py-1.5 text-sm text-sidebar-ink transition hover:bg-sidebar-2/60 hover:text-ink"
      aria-label={oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
    >
      {oscuro ? <Sun className="size-4" /> : <Moon className="size-4" />}
      {oscuro ? "Modo claro" : "Modo oscuro"}
    </button>
  );

  return (
    <div className="min-h-screen lg:pl-60">
      {/* Barra lateral (escritorio) */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-line bg-sidebar px-3 py-5 lg:flex">
        <div className="px-2"><Logo /></div>
        <div className="mt-6 flex-1 overflow-y-auto"><Navegacion /></div>
        <div className="border-t border-line pt-3">
          {botonTema}
          <p className="mt-2 px-2.5 text-xs leading-relaxed text-ink-3">Datos en tu PC y en tu Supabase · Gemini, plan gratuito</p>
        </div>
      </aside>

      {/* Barra superior (móvil) */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-sidebar px-4 py-3 lg:hidden">
        <Logo />
        <button onClick={() => setMenuAbierto(true)} className="rounded p-2 text-ink" aria-label="Abrir menú">
          <Menu className="size-6" />
        </button>
      </header>
      {menuAbierto && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMenuAbierto(false)} />
          <div className="aparecer absolute inset-y-0 left-0 flex w-72 flex-col border-r border-line bg-sidebar px-3 py-5">
            <div className="flex items-center justify-between px-2">
              <Logo />
              <button onClick={() => setMenuAbierto(false)} className="text-ink" aria-label="Cerrar menú"><X className="size-6" /></button>
            </div>
            <div className="mt-8 flex-1 overflow-y-auto"><Navegacion alNavegar={() => setMenuAbierto(false)} /></div>
            {botonTema}
          </div>
        </div>
      )}

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-8 lg:py-10">
        <Outlet />
      </main>
    </div>
  );
}
