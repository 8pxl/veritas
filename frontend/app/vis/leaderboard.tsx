"use client"

import { useEffect, useState } from "react"
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  createColumnHelper,
  flexRender,
  type SortingState,
} from "@tanstack/react-table"
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react"
import { getTruthLeaderboardStatsLeaderboardGet } from "@/lib/client/sdk.gen"
import type { LeaderboardEntry } from "@/lib/client/types.gen"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const columnHelper = createColumnHelper<LeaderboardEntry>()

function getTruthLabel(value: number) {
  if (value >= 0.75) return { label: "High", variant: "default" as const }
  if (value >= 0.5) return { label: "Medium", variant: "secondary" as const }
  return { label: "Low", variant: "destructive" as const }
}

const columns = [
  columnHelper.display({
    id: "rank",
    header: "#",
    enableSorting: false,
    cell: (info) => {
      const rank = info.row.index + 1

      if (rank === 1) {
        return <Badge className="min-w-14 justify-center">🥇 {rank}</Badge>
      }
      if (rank === 2) {
        return (
          <Badge variant="secondary" className="min-w-14 justify-center">
            🥈 {rank}
          </Badge>
        )
      }
      if (rank === 3) {
        return (
          <Badge variant="outline" className="min-w-14 justify-center">
            🥉 {rank}
          </Badge>
        )
      }

      return <span className="font-medium tabular-nums">{rank}</span>
    },
  }),
  columnHelper.accessor((row) => row.person.name, {
    id: "name",
    header: "Name",
    cell: (info) => (
      <span
        className="block max-w-[180px] truncate font-medium"
        title={info.getValue()}
      >
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor((row) => row.person.position, {
    id: "position",
    header: "Position",
    cell: (info) => (
      <span
        className="block max-w-[160px] truncate"
        title={info.getValue() ?? "—"}
      >
        {info.getValue() ?? "—"}
      </span>
    ),
  }),
  columnHelper.accessor((row) => row.person.organization.name, {
    id: "organization",
    header: "Organization",
    cell: (info) => (
      <span
        className="block max-w-[180px] truncate"
        title={info.getValue()}
      >
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor("truthIndex", {
    id: "truthIndex",
    header: "Truth Index",
    cell: (info) => {
      const value = info.getValue()
      if (value == null) return "—"

      const percentage = Math.max(0, Math.min(100, value * 100))
      return (
        <div className="min-w-36 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold tabular-nums">{percentage.toFixed(1)}%</span>
          </div>
          <Progress value={percentage} />
        </div>
      )
    },
  }),
  columnHelper.accessor("trueCount", {
    header: "True",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("falseCount", {
    header: "False",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("total", {
    header: "Total",
    cell: (info) => info.getValue(),
  }),
]

export default function Leaderboard() {
  const [data, setData] = useState<LeaderboardEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sorting, setSorting] = useState<SortingState>([
    { id: "truthIndex", desc: true },
  ])

  useEffect(() => {
    async function fetchLeaderboard() {
      setLoading(true)
      setError(null)
      try {
        const response = await getTruthLeaderboardStatsLeaderboardGet()
        setData(response.data ?? [])
      } catch {
        setError("Could not load leaderboard right now.")
      } finally {
        setLoading(false)
      }
    }

    fetchLeaderboard()
  }, [])

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const isNumericColumn = (columnId: string) => {
    return ["truthIndex", "trueCount", "falseCount", "total", "rank"].includes(
      columnId
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        Loading leaderboard...
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        {error}
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        No leaderboard data available.
      </div>
    )
  }

  const rows = table.getRowModel().rows

  return (
    <div
      className="w-full overflow-y-auto rounded-lg border bg-card"
      style={{ maxHeight: "70vh" }}
    >
      <Table>
        <TableHeader className="sticky top-0 z-10 bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead
                  key={header.id}
                  className={
                    [
                      header.column.getCanSort() ? "select-none" : "",
                      isNumericColumn(header.column.id) ? "text-right" : "text-left",
                    ].join(" ")
                  }
                >
                  {header.isPlaceholder ? null : header.column.getCanSort() ? (
                    <button
                      type="button"
                      className="inline-flex w-full items-center justify-between gap-2 rounded-md px-1 py-1 text-left hover:bg-muted/60"
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      <span>
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                      </span>
                      {header.column.getIsSorted() === "asc" ? (
                        <ArrowUp className="h-3.5 w-3.5 text-muted-foreground" />
                      ) : header.column.getIsSorted() === "desc" ? (
                        <ArrowDown className="h-3.5 w-3.5 text-muted-foreground" />
                      ) : (
                        <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground" />
                      )}
                    </button>
                  ) : (
                    flexRender(header.column.columnDef.header, header.getContext())
                  )}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id} className="odd:bg-muted/20">
              {row.getVisibleCells().map((cell) => (
                <TableCell
                  key={cell.id}
                  className={
                    isNumericColumn(cell.column.id)
                      ? "text-right tabular-nums"
                      : "text-left"
                  }
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
