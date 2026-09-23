import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export function MetricLineChart({ data = [], lines = [], unit = '' }: {
  data?: Array<Record<string, unknown>>
  lines: Array<{ key: string; name: string; color: string }>
  unit?: string
}) {
  if (!data.length) return <div className="h-64 flex items-center justify-center text-sm text-surface-400">Aguardando amostras.</div>
  const time = (value: string) => new Date(value).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  return <div className="h-72"><ResponsiveContainer width="100%" height="100%"><LineChart data={data}>
    <CartesianGrid strokeDasharray="3 3" opacity={0.2} /><XAxis dataKey="timestamp" tickFormatter={time} minTickGap={35} tick={{ fontSize: 11 }} />
    <YAxis tickFormatter={(v) => `${v}${unit}`} tick={{ fontSize: 11 }} /><Tooltip labelFormatter={(v) => time(String(v))} /><Legend />
    {lines.map((line) => <Line key={line.key} type="monotone" dataKey={line.key} name={line.name} stroke={line.color} dot={false} connectNulls />)}
  </LineChart></ResponsiveContainer></div>
}
