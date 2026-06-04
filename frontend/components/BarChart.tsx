"use client";

import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Title,
  Tooltip,
} from "chart.js";
import { Bar } from "react-chartjs-2";
import type { ChartSpec } from "@/lib/api";

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const BAR_COLORS = [
  "rgba(59,130,246,0.85)",
  "rgba(34,197,94,0.85)",
  "rgba(251,191,36,0.85)",
  "rgba(239,68,68,0.85)",
  "rgba(168,85,247,0.85)",
];

export default function BarChart({ spec }: { spec: ChartSpec }) {
  // Extract unit from title, e.g. "Revenue (US$M)" → "US$M"
  const unit = spec.title.match(/\(([^)]+)\)/)?.[1] ?? "A$M";

  const data = {
    labels: spec.labels,
    datasets: spec.datasets.map((ds, i) => ({
      label: ds.label,
      data: ds.data,
      backgroundColor: BAR_COLORS[i % BAR_COLORS.length],
      borderRadius: 4,
      borderSkipped: false as const,
    })),
  };

  const options = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        position: "top" as const,
        labels: { color: "#94a3b8", font: { size: 12 } },
      },
      title: {
        display: true,
        text: spec.title,
        color: "#c8dcef",
        font: { size: 13, weight: "bold" as const },
        padding: { bottom: 10 },
      },
      tooltip: {
        callbacks: {
          label: (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) => {
            if (ctx.parsed.y === null) return `${ctx.dataset.label ?? ""}: N/A`;
            return `${ctx.dataset.label ?? ""}: ${unit.replace("M", "")}${ctx.parsed.y.toLocaleString()}M`;
          },
        },
      },
    },
    scales: {
      x: {
        ticks: { color: "#8aa0b8" },
        grid: { color: "rgba(255,255,255,0.04)" },
      },
      y: {
        beginAtZero: false,
        ticks: { color: "#8aa0b8" },
        grid: { color: "rgba(255,255,255,0.06)" },
        title: { display: true, text: unit, color: "#6b8099", font: { size: 11 } },
      },
    },
  };

  return (
    <div className="my-3 p-4 rounded-xl bg-[#0d1e33] border border-[#1e3a5f] shadow-sm">
      <Bar data={data} options={options} />
    </div>
  );
}
