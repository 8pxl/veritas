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
import { getTruthLeaderboardStatsLeaderboardGet } from "@/lib/client/sdk.gen"
import type { LeaderboardEntry } from "@/lib/client/types.gen"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const columnHelper = createColumnHelper<LeaderboardEntry>()

function truthColor(value: number) {
  // Lerp from #BF5864 (0%) to #226F54 (100%)
  //0BBA54
  //EC596A
  const r = Math.round(0x0B + (0xEC - 0x0B) * (Math.min(1, value * 2)))
  const g = Math.round(0xBA + (0x59 - 0xBA) * (Math.min(1, value * 2)))
  const b = Math.round(0x54 + (0x6A - 0x54) * (Math.min(1, value * 2)))
  return `rgb(${r}, ${g}, ${b})`
}

const columns = [
  columnHelper.display({
    id: "rank",
    header: "#",
    cell: (info) => info.row.index + 1,
  }),
  columnHelper.accessor((row) => row.person.name, {
    id: "name",
    header: "Name",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor((row) => row.person.position, {
    id: "position",
    header: "Position",
    cell: (info) => info.getValue() ?? "—",
  }),
  columnHelper.accessor((row) => row.person.organization.name, {
    id: "organization",
    header: "Organization",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("truthIndex", {
    header: "Truth Index",
    cell: (info) => {
      const value = info.getValue()
      if (value == null) return "—"
      return (
        <span
          className="font-semibold"
          style={{ color: truthColor(1 - value) }}
        >
          {(value * 100).toFixed(1)}%
        </span>
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
  const [sorting, setSorting] = useState<SortingState>([])

  useEffect(() => {
    async function fetchLeaderboard() {
      setLoading(true)
      const response = await getTruthLeaderboardStatsLeaderboardGet()
      setData(response.data ?? [])
      setLoading(false)
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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        Loading leaderboard...
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
    <div className="w-full overflow-y-auto rounded-lg border bg-card" style={{ maxHeight: "70vh" }}>
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead
                  key={header.id}
                  className={
                    header.column.getCanSort()
                      ? "cursor-pointer select-none"
                      : ""
                  }
                  onClick={header.column.getToggleSortingHandler()}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                      header.column.columnDef.header,
                      header.getContext()
                    )}
                  {header.column.getIsSorted() === "asc"
                    ? " ↑"
                    : header.column.getIsSorted() === "desc"
                      ? " ↓"
                      : ""}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
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
