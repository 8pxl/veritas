"use client"

import { useMemo, useEffect, useRef, useState } from "react"
import dynamic from "next/dynamic"
import { mockCompanies } from "../mockData"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { getTruthLeaderboardStatsLeaderboardGet } from "@/lib/client/sdk.gen"
import type { LeaderboardEntry } from "@/lib/client/types.gen"
import { Badge } from "@/components/ui/badge"
import type { ForceGraphMethods } from "react-force-graph-2d"
import { forceCollide } from "d3-force"

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false })

interface GraphNode {
  id: string
  name: string
  val: number
  color: string
  group: string
  role: string
  type: "person" | "company"
  truthIndex: number
}

interface GraphLink {
  source: string | GraphNode
  target: string | GraphNode
}

const NODE_REL_SIZE = 5

const COLORS = [
  "#6366f1",
  "#f59e0b",
  "#10b981",
  "#ef4444",
  "#8b5cf6",
  "#3b82f6",
  "#ec4899",
  "#06b6d4",
]

function nodeRadius(val: number) {
  return Math.sqrt(val) * NODE_REL_SIZE
}

function hex2rgba(hex: string, alpha: number) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

export default function NetworkGraph() {
  const containerRef = useRef<HTMLDivElement>(null)
  const fgRef = useRef<ForceGraphMethods>(undefined)
  const hasSettledRef = useRef(false)
  const [width, setWidth] = useState(800)
  const [data, setData] = useState<LeaderboardEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [usingMock, setUsingMock] = useState(false)

  // Track container width — re-run when loading clears so the div is mounted
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    ro.observe(el)

    setWidth(el.clientWidth)
    return () => ro.disconnect()
  }, [loading])

  // Configure forces after graph loads

  function configureForces() {
    const fg = fgRef.current
    if (!fg) {
      setTimeout(configureForces, 100)
      return
    }
    fg.d3Force("link")?.distance(110).strength(0.5)
    fg.d3Force("charge")?.strength(0)
    fg.d3Force("collide", forceCollide((n: any) => nodeRadius((n as GraphNode).val) + 50))
    fg.d3ReheatSimulation()
  }

  useEffect(() => {
    console.log("Forces configured")
    configureForces()
  }, [loading])

  // Fetch data
  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true)
        const response = await getTruthLeaderboardStatsLeaderboardGet()
        if (response.data && response.data.length > 0) {
          setData(response.data)
          return
        }
        throw new Error("Empty data")
      } catch {
        const mockEntries: LeaderboardEntry[] = []
        mockCompanies.forEach((company) => {
          company.people.forEach((person) => {
            let total = 0, count = 0
            person.videos.forEach((v) =>
              v.analysisData.confidenceData.forEach((p) => { total += p.confidence; count++ })
            )
            mockEntries.push({
              person: {
                id: person.id,
                name: person.name,
                position: person.role,
                organization: {
                  id: parseInt(company.id.replace("c", "")) || 0,
                  name: company.name,
                  url: "",
                },
              },
              truthIndex: count > 0 ? (total / count) / 100 : 0.5,
              trueCount: 0,
              falseCount: 0,
              total: 0,
            })
          })
        })
        setData(mockEntries)
        setUsingMock(true)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const { graphData, orgToColor } = useMemo(() => {
    const nodes: GraphNode[] = []
    const links: GraphLink[] = []
    const orgToColor: Record<string, string> = {}
    const companyAdded = new Set<string>()
    let colorIdx = 0

    data.forEach((entry) => {
      const orgName = entry.person.organization.name
      const orgId = `company-${entry.person.organization.id}`

      if (!orgToColor[orgName]) {
        orgToColor[orgName] = COLORS[colorIdx++ % COLORS.length]
      }
      const color = orgToColor[orgName]
      const truthIndex = entry.truthIndex ?? 0.5

      if (!companyAdded.has(orgId)) {
        nodes.push({
          id: orgId,
          name: orgName,
          role: "Organization",
          val: 300,
          color,
          group: orgName,
          type: "company",
          truthIndex: 1,
        })
        companyAdded.add(orgId)
      }

      nodes.push({
        id: entry.person.id.toString(),
        name: entry.person.name,
        role: entry.person.position || "Individual",
        // Stretch the 0.5–1.0 band so 80% vs 95% looks very different
        val: Math.pow(Math.max(0, (truthIndex - 0.5) / 0.5), 2) * 200 + 4,
        color,
        group: orgName,
        type: "person",
        truthIndex,
      })

      links.push({ source: entry.person.id.toString(), target: orgId })
    })

    return { graphData: { nodes, links }, orgToColor }
  }, [data])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[500px] text-muted-foreground">
        Loading network graph...
      </div>
    )
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-2 text-center relative">
        <CardTitle className="text-xl font-bold">Institutional Trust Network</CardTitle>
        <p className="text-sm text-muted-foreground mt-1">
          Node size reflects truth index. Clusters group people by organization.
        </p>
        {usingMock && (
          <div className="absolute top-4 right-4">
            <Badge variant="outline" className="text-amber-500 border-amber-500/50">
              Mock Data
            </Badge>
          </div>
        )}
      </CardHeader>

      <CardContent className="p-0">
        <div ref={containerRef} className="w-full h-[580px]">
          <ForceGraph2D
            ref={fgRef}
            graphData={graphData}
            width={width}
            height={580}
            nodeRelSize={NODE_REL_SIZE}
            backgroundColor="transparent"
            // Links
            linkColor={() => "rgba(255,255,255,0.08)"}
            linkWidth={1.5}
            linkDirectionalArrowLength={0}
            // Tooltips
            nodeLabel={(node) => {
              const n = node as GraphNode
              const pct = (n.truthIndex * 100).toFixed(0)
              if (n.type === "company") {
                return `<div style="background:rgba(15,15,20,0.9);color:#fff;padding:10px 14px;border-radius:10px;font-size:13px;border:1px solid rgba(255,255,255,0.15);line-height:1.5">
                  <div style="font-weight:700;font-size:14px">${n.name}</div>
                  <div style="opacity:0.5;font-size:11px;margin-top:2px">Organization hub</div>
                </div>`
              }
              return `<div style="background:rgba(15,15,20,0.9);color:#fff;padding:10px 14px;border-radius:10px;font-size:13px;border:1px solid rgba(255,255,255,0.15);line-height:1.6">
                <div style="font-weight:700;font-size:14px">${n.name}</div>
                <div style="opacity:0.7;margin-bottom:6px">${n.role} &middot; ${n.group}</div>
                <div style="display:flex;align-items:center;gap:8px">
                  <div style="flex:1;height:4px;background:rgba(255,255,255,0.1);border-radius:2px;overflow:hidden">
                    <div style="width:${pct}%;height:100%;background:${n.color};border-radius:2px"></div>
                  </div>
                  <span style="font-weight:600;font-size:12px">${pct}%</span>
                </div>
              </div>`
            }}
            // Canvas drawing
            nodeCanvasObjectMode={() => "always"}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const n = node as GraphNode
              const x = node.x!
              const y = node.y!
              const r = nodeRadius(n.val)

              if (n.type === "company") {
                // Glow
                const glow = ctx.createRadialGradient(x, y, r * 0.2, x, y, r * 2.2)
                glow.addColorStop(0, hex2rgba(n.color, 0.18))
                glow.addColorStop(1, hex2rgba(n.color, 0))
                ctx.beginPath()
                ctx.arc(x, y, r * 2.2, 0, 2 * Math.PI)
                ctx.fillStyle = glow
                ctx.fill()

                // Fill
                ctx.beginPath()
                ctx.arc(x, y, r, 0, 2 * Math.PI)
                ctx.fillStyle = hex2rgba(n.color, 0.15)
                ctx.fill()

                // Border ring
                ctx.beginPath()
                ctx.arc(x, y, r, 0, 2 * Math.PI)
                ctx.strokeStyle = n.color
                ctx.lineWidth = 2 / globalScale
                ctx.stroke()

                // Name label inside
                const fontSize = Math.max(11 / globalScale, 2)
                ctx.font = `bold ${fontSize}px Sans-Serif`
                ctx.textAlign = "center"
                ctx.textBaseline = "middle"
                ctx.fillStyle = n.color
                ctx.fillText(n.name, x, y)
              } else {
                // Person circle
                ctx.beginPath()
                ctx.arc(x, y, r, 0, 2 * Math.PI)
                ctx.fillStyle = n.color
                ctx.fill()

                // Truth index arc overlay (white sector showing truthIndex fraction)
                const arcEnd = -Math.PI / 2 + 2 * Math.PI * n.truthIndex
                ctx.beginPath()
                ctx.moveTo(x, y)
                ctx.arc(x, y, r, -Math.PI / 2, arcEnd)
                ctx.closePath()
                ctx.fillStyle = hex2rgba("#ffffff", 0.18)
                ctx.fill()

                // White border
                ctx.beginPath()
                ctx.arc(x, y, r, 0, 2 * Math.PI)
                ctx.strokeStyle = "rgba(255,255,255,0.25)"
                ctx.lineWidth = 1 / globalScale
                ctx.stroke()

                // Name label below node
                const fontSize = Math.max(9 / globalScale, 2)
                ctx.font = `${fontSize}px Sans-Serif`
                ctx.textAlign = "center"
                ctx.textBaseline = "top"
                ctx.fillStyle = "rgba(255,255,255,0.75)"
                ctx.fillText(n.name, x, y + r + 3 / globalScale)
              }
            }}
            // Simulation
            cooldownTicks={1000}
            d3AlphaDecay={0.04}
            d3VelocityDecay={0.75}
            onNodeDrag={(node) => {
              ;(node as any).fx = node.x
              ;(node as any).fy = node.y
            }}
            onNodeDragEnd={(node) => {
              ;(node as any).fx = node.x
              ;(node as any).fy = node.y
            }}
            // onEngineStop={() => {
            //   hasSettledRef.current = true
            //   fgRef.current?.d3Force("charge")?.strength(0)
            //   fgRef.current?.zoomToFit(400, 60)
            // }}
          />
        </div>
      </CardContent>
    </Card>
  )
}
