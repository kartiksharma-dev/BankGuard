import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { ChartVolumePoint } from '../../types/api';
import { EmptyState } from '../common/EmptyState';
import { BarChart3 } from 'lucide-react';

interface TransactionVolumeChartProps {
  data: ChartVolumePoint[];
  loading?: boolean;
}

export const TransactionVolumeChart: React.FC<TransactionVolumeChartProps> = ({
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
          icon={<BarChart3 className="w-6 h-6 text-slate-500" />}
          title="No volume data recorded"
          description="Transactions processed by BankGuard will plot timeline volume and fraud patterns here."
        />
      </div>
    );
  }

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="colorFraud" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.5} />
              <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
          <XAxis
            dataKey="date"
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
          <Area
            type="monotone"
            dataKey="total"
            name="Total Volume"
            stroke="#10b981"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#colorTotal)"
          />
          <Area
            type="monotone"
            dataKey="fraud"
            name="Fraudulent"
            stroke="#f43f5e"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#colorFraud)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};
