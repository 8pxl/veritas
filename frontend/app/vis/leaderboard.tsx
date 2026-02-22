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
      return `${(value * 100).toFixed(1)}%`
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

  return (
    <div className="w-full rounded-lg border bg-card">
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
          {table.getRowModel().rows.map((row) => (
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
