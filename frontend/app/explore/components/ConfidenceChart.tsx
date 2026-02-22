"use client"

import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid,
} from "recharts"

export interface ChartDataPoint {
  label: string
  audio: number | null
  facial: number | null
}

interface ConfidenceChartProps {
  data: ChartDataPoint[]
}

export function ConfidenceChart({ data }: ConfidenceChartProps) {
  if (data.length <= 1) return null

  return (
    <div className="flex flex-col gap-2 rounded-lg border p-4">
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart
          data={data}
          margin={{ top: 4, right: 8, left: -16, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorAudio" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#91dc6e" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#894048" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#eee" strokeDasharray="5 5" />
          <XAxis dataKey="label" hide />
          {/* <YAxis domain={[0, 100]} hide /> */}
          <Tooltip
            contentStyle={{
              fontSize: 11,
              background: "#FFF4E9",
              border: "1px solid #894048",
              borderRadius: 6,
            }}
            formatter={(v) => [`${v ?? ""}%`]}
          />
          <Area
            type="monotone"
            dataKey="audio"
            name="Audio"
            stroke="#91dc6e"
            strokeWidth={2}
            fill="url(#colorAudio)"
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
