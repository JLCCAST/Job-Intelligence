import { useQuery } from "@tanstack/react-query";
import { BarChart3, CircleCheck, FileStack, ShieldAlert } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Aviso, Cargando, Encabezado, Indicador, Seccion, Tarjeta, Vacio, plural } from "../components/ui";

const MUESTRA_MINIMA = 10;
// Slots 1 y 2 de la paleta categórica validada.
const AZUL = "#2a78d6";
const NARANJA = "#eb6834";

export default function Analisis() {
  const { data, isLoading } = useQuery({ queryKey: ["analisis"], queryFn: api.analisis });
  if (isLoading || !data) return <Cargando />;

  const top = data.demanda.slice(0, 12).map((d) => ({
    tecnologia: d.tecnologia,
    "La tienes": d.la_tengo ? d.total : 0,
    "Te falta": d.la_tengo ? 0 : d.total,
    obligatoria: d.obligatoria,
    deseable: d.deseable,
  }));
  const total = data.demanda.reduce((a, d) => a + d.total, 0);
  const cubiertos = data.demanda.filter((d) => d.la_tengo).reduce((a, d) => a + d.total, 0);
  const faltantes = data.demanda.filter((d) => !d.la_tengo && d.obligatoria > 0);

  return (
    <div className="aparecer">
      <Encabezado seccion="Tú" titulo="Análisis de tus ofertas" descripcion="Qué te piden más y cuánto de eso ya cubres." />
      {!data.demanda.length ? (
        <Vacio icono={BarChart3} titulo="Aún no hay requisitos registrados">Analiza ofertas para ver qué te piden más.</Vacio>
      ) : (
        <>
          {data.ofertas < MUESTRA_MINIMA && (
            <div className="mb-5"><Aviso tono="warn">Calculado con {plural(data.ofertas, "oferta", "ofertas")}: los resultados son orientativos, no una tendencia.</Aviso></div>
          )}
          <div className="grid gap-4 sm:grid-cols-3">
            <Indicador etiqueta="Ofertas analizadas" valor={data.ofertas} icono={FileStack} />
            <Indicador etiqueta="Requisitos que cubres" valor={`${Math.round((cubiertos / total) * 100)}%`} icono={CircleCheck}
                       ayuda="Sobre todas las veces que una oferta pidió una tecnología" />
            <Indicador etiqueta="Obligatorias que te faltan" valor={faltantes.length} icono={ShieldAlert} />
          </div>

          <Seccion titulo="¿Qué te piden más?">
            <Tarjeta>
              <div style={{ height: Math.max(220, top.length * 34) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={top} layout="vertical" margin={{ left: 8, right: 16 }} barCategoryGap="28%">
                    <CartesianGrid horizontal={false} stroke="var(--border)" />
                    <XAxis type="number" allowDecimals={false} stroke="var(--text-3)" fontSize={12} />
                    <YAxis type="category" dataKey="tecnologia" width={140} stroke="var(--text-2)" fontSize={12} tickLine={false} />
                    <Tooltip
                      cursor={{ fill: "var(--surface-2)" }}
                      contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, color: "var(--text)" }}
                      formatter={(v, nombre) => [v ? `${v} oferta(s)` : "—", nombre]}
                    />
                    <Legend verticalAlign="top" align="left" iconType="circle" wrapperStyle={{ paddingBottom: 12, fontSize: 13 }} />
                    <Bar dataKey="La tienes" stackId="a" fill={AZUL} radius={[0, 4, 4, 0]} />
                    <Bar dataKey="Te falta" stackId="a" fill={NARANJA} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Tarjeta>
          </Seccion>

          {faltantes.length > 0 && (
            <Seccion titulo="Tus brechas obligatorias más frecuentes">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {faltantes.slice(0, 6).map((d) => (
                  <Tarjeta key={d.tecnologia} className="p-4">
                    <p className="font-semibold text-ink">{d.tecnologia}</p>
                    <p className="text-sm text-ink-2">Obligatoria en {plural(d.obligatoria, "oferta", "ofertas")}</p>
                  </Tarjeta>
                ))}
              </div>
            </Seccion>
          )}
        </>
      )}
    </div>
  );
}
