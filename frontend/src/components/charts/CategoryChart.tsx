import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { ChartCategoryPoint } from '../../types/api';
import { EmptyState } from '../common/EmptyState';
import { Tag } from 'lucide-react';

interface CategoryChartProps {
  data: ChartCategoryPoint[];
  loading?: boolean;
}

export const CategoryChart: React.FC<CategoryChartProps> = ({
  data,
  loading = false,
}) => {
  if (loading) {
    return (
      <div className="h-72 flex items-center justify-center bg-slate-900/40 rounded-xl border border-slate-800">
        <div className="w-8 h-8 border-2 border-slate-700 border-t-emerald-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="h-72 flex items-center justify-center">
        <EmptyState
          icon={<Tag className="w-6 h-6 text-slate-500" />}
          title="No category metrics"
          description="Breakdown of transactions by merchant categories will appear here."
        />
      </div>
    );
  }

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
          <XAxis
            dataKey="category"
            stroke="#94a3b8"
            fontSize={12}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
          />
          <YAxis
            stroke="#94a3b8"
            fontSize={12}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#0f172a',
              borderColor: '#334155',
              borderRadius: '0.5rem',
              color: '#f8fafc',
              fontSize: '12px',
            }}
          />
          <Legend
            verticalAlign="top"
            height={36}
            wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }}
          />
          <Bar dataKey="total" name="Total Transactions" fill="#3b82f6" radius={[4, 4, 0, 0]} />
          <Bar dataKey="fraud" name="Fraud Detected" fill="#ef4444" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
