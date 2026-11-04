import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Database, FilePen, FileSearch, Inbox, ListChecks, Send, Target, Clock } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { api } from "../api";
import {
  Aviso, Boton, Cargando, Indicador, Seccion, Tarjeta, TarjetaOferta, Vacio, formatoScore, plural,
} from "../components/ui";

const ACTIVOS = ["Postulada", "Entrevista", "Oferta"];

export default function Inicio() {
  const { data, isLoading, error } = useQuery({ queryKey: ["inicio"], queryFn: api.inicio });
  const navegar = useNavigate();

  if (isLoading) return <Cargando />;
  if (error || !data) return <Aviso tono="bad" titulo="No se pudo cargar">{String(error)}</Aviso>;

  const bandeja = data.ofertas.filter((o) => o.estado === "Registrada")
    .sort((a, b) => (b.match_score ?? 0) - (a.match_score ?? 0));
  const activas = data.ofertas.filter((o) => ACTIVOS.includes(o.estado));
  const scores = data.ofertas.map((o) => o.match_score).filter((s): s is number => s != null);
  const promedio = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
  const nuevas = data.resumen.nuevas.length;

  const hoy = new Date().toLocaleDateString("es-PE", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div className="aparecer">
      {/* Bienvenida: sobria, como el encabezado de cualquier página */}
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
        <div>
          <p className="mb-1 text-sm text-ink-3 first-letter:uppercase">{hoy}</p>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Hola{data.nombre ? `, ${data.nombre}` : ""}</h1>
          <p className="mt-1.5 text-sm text-ink-2">
            Tienes {plural(bandeja.length, "oferta", "ofertas")} en tu bandeja
            {nuevas > 0 && ` (${plural(nuevas, "nueva", "nuevas")} en las últimas 24 horas)`}
            {activas.length ? ` y ${plural(activas.length, "postulación", "postulaciones")} en curso.` : " y ninguna postulación en curso."}
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/analizar" className="inline-flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-2">
            <FileSearch className="size-4" /> Analizar oferta
          </Link>
          <Link to="/bandeja" className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-hover">
            <Inbox className="size-4" /> Revisar bandeja
          </Link>
        </div>
      </header>

      {/* Indicadores */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Indicador etiqueta="Ofertas registradas" valor={data.ofertas.length} icono={Database} />
        <Indicador etiqueta="En tu bandeja" valor={bandeja.length} icono={Inbox} />
        <Indicador etiqueta="Postulaciones activas" valor={activas.length} icono={Send} ayuda="Postulada, Entrevista u Oferta" />
        <Indicador etiqueta="Match Score promedio" valor={formatoScore(promedio)} icono={Target} />
      </div>

      {/* Avisos */}
      {(data.resumen.recordatorios.length > 0 || data.por_revisar > 0) && (
        <div className="mt-6 flex flex-col gap-3">
          {data.resumen.recordatorios.map((r) => (
            <Aviso key={r.job_id} tono="warn" titulo={`${r.puesto} · ${r.empresa}`}>
              <span className="inline-flex items-center gap-1"><Clock className="size-3.5" /> {r.dias} días sin respuesta. Buen momento para hacer seguimiento.</span>
            </Aviso>
          ))}
          {data.por_revisar > 0 && (
            <Tarjeta className="flex flex-wrap items-center justify-between gap-3 p-4">
              <p className="flex items-center gap-2 text-sm text-ink">
                <ListChecks className="size-4 text-primary" />
                <b>{plural(data.por_revisar, "tecnología nueva espera", "tecnologías nuevas esperan")}</b> tu revisión.
              </p>
              <Link to="/revision" className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline">
                Revisar catálogo <ArrowRight className="size-4" />
              </Link>
            </Tarjeta>
          )}
        </div>
      )}

      {/* Mejores ofertas */}
      <Seccion
        titulo="Mejores ofertas por revisar"
        extra={bandeja.length > 3 && (
          <Link to="/bandeja" className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline">
            Ver las {bandeja.length} <ArrowRight className="size-4" />
          </Link>
        )}
      >
        {bandeja.length === 0 ? (
          <Vacio icono={Inbox} titulo="Tu bandeja está vacía">Analiza una oferta o deja que Sabueso traiga nuevas.</Vacio>
        ) : (
          <div className="flex flex-col gap-3">
            {bandeja.slice(0, 3).map((o) => (
              <TarjetaOferta key={o.job_id} oferta={o} mostrarEstado={false} acciones={
                <Boton variante="primario" icono={FilePen} onClick={() => navegar(`/adaptar-cv?job=${o.job_id}`)}>Adaptar mi CV</Boton>
              } />
            ))}
          </div>
        )}
      </Seccion>

    </div>
  );
}
