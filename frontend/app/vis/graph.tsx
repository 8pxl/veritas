"use client"

import { useEffect, useState, useMemo, useCallback } from "react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { client } from "@/lib/client/client.gen"
import { mockGraphData } from "@/app/mockData"
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

/* ---------- Types (matches backend TopOrgsRunningAvgResponse) ---------- */

interface RunningAvgPoint {
  date: string
  truthIndex: number
  cumulativeTrue: number
  cumulativeDecided: number
}

interface Organization {
  id: number
  name: string
}

interface OrgRunningAverage {
  organization: Organization
  currentTruthIndex: number
  series: RunningAvgPoint[]
}

interface TopOrgsRunningAvgResponse {
  topN: number
  organizations: OrgRunningAverage[]
}

/* ---------- Colours for the five lines ---------- */

const LINE_COLORS = [
  "#6366f1", // indigo-500
  "#f59e0b", // amber-500
  "#10b981", // emerald-500
  "#ef4444", // red-500
  "#8b5cf6", // violet-500
]

/* ---------- Custom tooltip built with shadcn Card ---------- */

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{
    name: string
    value: number
    color: string
    payload: Record<string, unknown>
  }>
  label?: string
  orgLookup: Map<string, OrgRunningAverage>
}

function CustomTooltipCard({ active, payload, label, orgLookup }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0 || !label) return null

  const dateStr = new Date(label).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  })

  return (
    <Card className="w-64 py-3 shadow-lg border-border/60 bg-popover/95 backdrop-blur-sm">
      <CardHeader className="pb-0 gap-1 px-4 py-0">
        <CardTitle className="text-sm">{dateStr}</CardTitle>
        <CardDescription className="text-xs">Truth Index Snapshot</CardDescription>
      </CardHeader>
      <CardContent className="px-4 pt-2 pb-0 space-y-2">
        {payload.map((entry) => {
          const org = orgLookup.get(entry.name)
          // Find the original data point for this date to show cumulative stats
          const raw = entry.payload as Record<string, unknown>
          const cTrue = raw[`${entry.name}__true`] as number | undefined
          const cDecided = raw[`${entry.name}__decided`] as number | undefined

          return (
            <div key={entry.name} className="flex flex-col gap-0.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="text-xs font-medium truncate max-w-[130px]">
                    {entry.name}
                  </span>
                </div>
                <span className="text-xs font-bold tabular-nums">
                  {Number(entry.value).toFixed(1)}%
                </span>
              </div>
              {cTrue != null && cDecided != null && (
                <span className="ml-[18px] text-[10px] text-muted-foreground">
                  {cTrue} true / {cDecided} decided
                  {org && (
                    <> · current {(org.currentTruthIndex * 100).toFixed(1)}%</>
                  )}
                </span>
              )}
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

/* ---------- Component ---------- */

export default function Graph() {
  const [response, setResponse] = useState<TopOrgsRunningAvgResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [visibleOrgs, setVisibleOrgs] = useState<Set<string>>(new Set())
  const [usingMock, setUsingMock] = useState(false)

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true)
        const res = await client.get<TopOrgsRunningAvgResponse>({
          url: "/stats/top-orgs-running-avg",
          query: { top_n: 5 },
        })
        if (res.data && res.data.organizations.length > 0) {
          setResponse(res.data)
          setVisibleOrgs(new Set(res.data.organizations.map((o) => o.organization.name)))
        } else {
          throw new Error("Empty response")
        }
      } catch (err) {
        console.warn("API unavailable, falling back to mock data:", err)
        setResponse(mockGraphData)
        setVisibleOrgs(new Set(mockGraphData.organizations.map((o) => o.organization.name)))
        setUsingMock(true)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const toggleOrg = useCallback((name: string) => {
    setVisibleOrgs((prev) => {
      const next = new Set(prev)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })
  }, [])

  /* Merge every org's series into a single flat array keyed by date,
     including cumulative stats for the tooltip card. */
  const { chartData, orgNames, orgLookup } = useMemo(() => {
    if (!response || response.organizations.length === 0)
      return { chartData: [], orgNames: [], orgLookup: new Map<string, OrgRunningAverage>() }

    const names = response.organizations.map((o) => o.organization.name)
    const lookup = new Map<string, OrgRunningAverage>(
      response.organizations.map((o) => [o.organization.name, o])
    )

    // Build a date→{orgName: point} index from raw series
    const dateIndex: Record<string, Record<string, RunningAvgPoint>> = {}
    for (const org of response.organizations) {
      for (const pt of org.series) {
        if (!dateIndex[pt.date]) dateIndex[pt.date] = {}
        dateIndex[pt.date][org.organization.name] = pt
      }
    }

    const sortedDates = Object.keys(dateIndex).sort()
    const lastKnown: Record<string, RunningAvgPoint | null> = {}
    const data = sortedDates.map((date) => {
      const row: Record<string, string | number | null> = { date }
      for (const name of names) {
        const pt = dateIndex[date]?.[name]
        if (pt) lastKnown[name] = pt
        const cur = lastKnown[name]
        row[name] = cur ? cur.truthIndex * 100 : null
        // Stash cumulative stats for the tooltip
        row[`${name}__true`] = cur?.cumulativeTrue ?? null
        row[`${name}__decided`] = cur?.cumulativeDecided ?? null
      }
      return row
    })

    return { chartData: data, orgNames: names, orgLookup: lookup }
  }, [response])

  /* ---------- Render ---------- */

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        Loading graph data…
      </div>
    )
  }

  if (error || !response || response.organizations.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        {error ?? "No data available."}
      </div>
    )
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-center text-lg">
          Truth Index — Top {response.topN} Organizations (Running Average)
        </CardTitle>
        {usingMock && (
          <div className="flex justify-center pt-1">
            <Badge variant="outline" className="text-xs text-amber-500 border-amber-500/50">
              Using mock data — API unavailable
            </Badge>
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Toggle chips */}
        <div className="flex flex-wrap items-center justify-center gap-2">
          {orgNames.map((name, i) => {
            const active = visibleOrgs.has(name)
            const color = LINE_COLORS[i % LINE_COLORS.length]
            return (
              <Badge
                key={name}
                variant={active ? "default" : "outline"}
                className="cursor-pointer select-none transition-colors"
                style={
                  active
                    ? { backgroundColor: color, borderColor: color, color: "#fff" }
                    : { borderColor: color, color: color }
                }
                onClick={() => toggleOrg(name)}
              >
                {name}
              </Badge>
            )
          })}
        </div>

        <ResponsiveContainer width="100%" height={420}>
          <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12 }}
              tickFormatter={(v: string) => {
                const d = new Date(v)
                return d.toLocaleDateString("en-US", { month: "short", year: "numeric" })
              }}
              interval="preserveStartEnd"
              minTickGap={60}
            />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(v: number) => `${v}%`}
              tick={{ fontSize: 12 }}
              label={{
                value: "Truth Index",
                angle: -90,
                position: "insideLeft",
                style: { textAnchor: "middle", fontSize: 13 },
              }}
            />
            <Tooltip
              content={<CustomTooltipCard orgLookup={orgLookup} />}
              cursor={{ stroke: "hsl(var(--muted-foreground))", strokeWidth: 1, strokeDasharray: "4 4" }}
              wrapperStyle={{ outline: "none" }}
            />
            {orgNames.map((name, i) => (
              <Line
                key={name}
                type="monotone"
                dataKey={name}
                stroke={LINE_COLORS[i % LINE_COLORS.length]}
                strokeWidth={2}
                dot={false}
                connectNulls
                hide={!visibleOrgs.has(name)}
                activeDot={{ r: 5, strokeWidth: 2 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
