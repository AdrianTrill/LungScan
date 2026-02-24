"use client";

/** Interactive charts component for displaying analysis statistics. */

import { useState } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Nodule } from "@/lib/types";

interface AnalysisChartsProps {
  nodules: Nodule[];
}

const COLORS = {
  low: "#16a34a",      // Green
  medium: "#eab308",   // Yellow
  high: "#f97316",      // Orange
  critical: "#dc2626", // Red
};

export default function AnalysisCharts({ nodules }: AnalysisChartsProps) {
  const [hoveredBar, setHoveredBar] = useState<number | null>(null);

  // Prepare data for malignancy score distribution
  const scoreDistribution = [
    { name: "0-30%", value: nodules.filter(n => n.malignancy_score < 0.3).length, color: COLORS.low },
    { name: "30-60%", value: nodules.filter(n => n.malignancy_score >= 0.3 && n.malignancy_score < 0.6).length, color: COLORS.medium },
    { name: "60-80%", value: nodules.filter(n => n.malignancy_score >= 0.6 && n.malignancy_score < 0.8).length, color: COLORS.high },
    { name: "80-100%", value: nodules.filter(n => n.malignancy_score >= 0.8).length, color: COLORS.critical },
  ].filter(item => item.value > 0);

  // Prepare data for individual nodule scores (bar chart)
  const noduleScores = nodules
    .map((nodule, index) => ({
      name: `Nodule ${index + 1}`,
      score: (nodule.malignancy_score * 100).toFixed(1),
      rawScore: nodule.malignancy_score,
      radius: nodule.radius.toFixed(1),
    }))
    .sort((a, b) => b.rawScore - a.rawScore);

  // Prepare data for size vs score scatter (line chart showing trend)
  const sizeVsScore = nodules
    .map((nodule) => ({
      size: nodule.radius.toFixed(1),
      score: (nodule.malignancy_score * 100).toFixed(1),
      rawSize: nodule.radius,
      rawScore: nodule.malignancy_score,
    }))
    .sort((a, b) => a.rawSize - b.rawSize);

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200">
          <p className="font-semibold text-slate-900">{payload[0].name || payload[0].payload.name}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} className="text-sm" style={{ color: entry.color }}>
              {`${entry.dataKey}: ${entry.value}${entry.dataKey === 'score' ? '%' : 'mm'}`}
            </p>
          ))}
          {payload[0].payload.radius && (
            <p className="text-sm text-slate-600 mt-1">
              Size: {payload[0].payload.radius}mm
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  const CustomPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) => {
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    if (percent < 0.05) return null; // Don't show label if too small

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor={x > cx ? "start" : "end"}
        dominantBaseline="central"
        className="text-xs font-semibold"
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  if (nodules.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500">
        No nodule data available for charts
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-blue-50 to-primary-50 rounded-xl p-4 border border-blue-200">
          <p className="text-sm text-slate-600 mb-1">Total Nodules</p>
          <p className="text-3xl font-bold text-primary-700">{nodules.length}</p>
        </div>
        <div className="bg-gradient-to-br from-emerald-50 to-green-50 rounded-xl p-4 border border-emerald-200">
          <p className="text-sm text-slate-600 mb-1">Average Score</p>
          <p className="text-3xl font-bold text-emerald-700">
            {((nodules.reduce((sum, n) => sum + n.malignancy_score, 0) / nodules.length) * 100).toFixed(1)}%
          </p>
        </div>
        <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-xl p-4 border border-amber-200">
          <p className="text-sm text-slate-600 mb-1">Highest Risk</p>
          <p className="text-3xl font-bold text-amber-700">
            {(Math.max(...nodules.map(n => n.malignancy_score)) * 100).toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Malignancy Score Distribution - Pie Chart */}
        <div className="bg-slate-50 rounded-xl p-6 border border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Risk Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={scoreDistribution}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={CustomPieLabel}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
                onMouseEnter={(_, index) => setHoveredBar(index)}
                onMouseLeave={() => setHoveredBar(null)}
              >
                {scoreDistribution.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.color}
                    opacity={hoveredBar === index ? 1 : hoveredBar === null ? 1 : 0.5}
                    style={{ transition: "opacity 0.2s" }}
                  />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload[0]) {
                    return (
                      <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200">
                        <p className="font-semibold text-slate-900">{payload[0].payload.name}</p>
                        <p className="text-sm text-slate-600">
                          Count: {payload[0].value} nodule{(payload[0].value as number) !== 1 ? 's' : ''}
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Legend
                verticalAlign="bottom"
                height={36}
                formatter={(value) => <span className="text-sm text-slate-700">{value}</span>}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Individual Nodule Scores - Bar Chart */}
        <div className="bg-slate-50 rounded-xl p-6 border border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Nodule Scores</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={noduleScores}
              margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 12, fill: "#64748b" }}
                angle={-45}
                textAnchor="end"
                height={60}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "#64748b" }}
                label={{ value: "Score (%)", angle: -90, position: "insideLeft", style: { textAnchor: "middle", fill: "#64748b" } }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar
                dataKey="score"
                fill="#2563eb"
                radius={[8, 8, 0, 0]}
                onMouseEnter={(_, index) => setHoveredBar(index)}
                onMouseLeave={() => setHoveredBar(null)}
                opacity={hoveredBar !== null ? (data: any, index: number) => hoveredBar === index ? 1 : 0.5 : 1}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Size vs Score Relationship - Line Chart */}
        <div className="bg-slate-50 rounded-xl p-6 border border-slate-200 lg:col-span-2">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Size vs Malignancy Score</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart
              data={sizeVsScore}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                dataKey="size"
                tick={{ fontSize: 12, fill: "#64748b" }}
                label={{ value: "Size (mm)", position: "insideBottom", offset: -5, style: { textAnchor: "middle", fill: "#64748b" } }}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "#64748b" }}
                label={{ value: "Malignancy Score (%)", angle: -90, position: "insideLeft", style: { textAnchor: "middle", fill: "#64748b" } }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#2563eb"
                strokeWidth={3}
                dot={{ fill: "#2563eb", r: 6 }}
                activeDot={{ r: 8, fill: "#1d4ed8" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

